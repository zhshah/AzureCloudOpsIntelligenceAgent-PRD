"""
Azure Cost Intelligence Agent - Main Application
Provides conversational AI interface for Azure cost management and resource queries
"""

from fastapi import FastAPI, HTTPException, Request, Header, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv
import json
import uuid
import io
from datetime import datetime, timedelta

from azure_cost_manager import AzureCostManager
from azure_resource_manager import AzureResourceManager
from entra_id_manager import EntraIDManager
from openai_agent import OpenAIAgent
from auth_manager import get_auth_manager, get_current_user, get_current_user_optional

# Load environment variables
load_dotenv()

# Cached credential singleton - avoid recreating DefaultAzureCredential on every API call
_cached_credential = None
def get_cached_credential():
    global _cached_credential
    if _cached_credential is None:
        from azure.identity import DefaultAzureCredential
        _cached_credential = DefaultAzureCredential()
    return _cached_credential

app = FastAPI(
    title="Azure Cost Intelligence Agent",
    description="AI-powered Azure cost and resource management",
    version="1.0.0"
)

# Query results cache for CSV export (stores full results)
# Format: {query_id: {"data": [...], "timestamp": datetime, "query_type": str}}
query_results_cache: Dict[str, Dict] = {}

# Initialize managers
cost_manager = AzureCostManager()
resource_manager = AzureResourceManager()
entra_manager = EntraIDManager()
ai_agent = OpenAIAgent(cost_manager, resource_manager, entra_manager)
auth_manager = get_auth_manager()

# Share the query cache with the agent
ai_agent.query_cache = query_results_cache


def resolve_mg_subscriptions(mg_id: str) -> List[str]:
    """Resolve all subscription IDs under a management group (recursively)"""
    try:
        from azure.mgmt.managementgroups import ManagementGroupsAPI
        mg_client = ManagementGroupsAPI(get_cached_credential())
        
        subscription_ids = []
        
        def collect_subs(group_id, depth=0):
            if depth > 5:
                return
            try:
                mg = mg_client.management_groups.get(group_id, expand="children")
                if mg.children:
                    for child in mg.children:
                        if child.type == "/subscriptions":
                            subscription_ids.append(child.name)
                        elif child.type == "/providers/Microsoft.Management/managementGroups":
                            collect_subs(child.name, depth + 1)
            except Exception as e:
                print(f"Error resolving MG {group_id}: {e}")
        
        collect_subs(mg_id)
        print(f"📁 Resolved MG '{mg_id}' → {len(subscription_ids)} subscriptions: {subscription_ids}")
        return subscription_ids
    except Exception as e:
        print(f"Error resolving management group subscriptions: {e}")
        return []


class ChatMessage(BaseModel):
    message: str
    conversation_history: Optional[List[Dict[str, str]]] = []
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    subscription_context: Optional[str] = None  # Selected subscription ID or 'all'
    subscription_name: Optional[str] = None  # Selected subscription name
    all_subscriptions: Optional[bool] = False  # Flag to query all subscriptions


class ChatResponse(BaseModel):
    response: str
    conversation_history: List[Dict[str, str]]


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """
    Serve the main chat interface.
    Authentication is handled client-side after MSAL redirect.
    The JavaScript in index.html will redirect to login if needed.
    """
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/login.html", response_class=HTMLResponse)
async def read_login():
    """Serve the login page"""
    with open("static/login.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/auth-config")
async def get_auth_config():
    """
    Return authentication configuration for the frontend.
    This allows dynamic configuration without hardcoding values in the UI.
    """
    client_id = os.getenv("ENTRA_APP_CLIENT_ID", "")
    tenant_id = os.getenv("ENTRA_TENANT_ID", "")
    
    if not client_id or not tenant_id:
        raise HTTPException(
            status_code=500,
            detail="Authentication not configured. Please set ENTRA_APP_CLIENT_ID and ENTRA_TENANT_ID environment variables."
        )
    
    return {
        "clientId": client_id,
        "tenantId": tenant_id,
        "authority": f"https://login.microsoftonline.com/{tenant_id}"
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatMessage,
    req: Request = None,
    authorization: Optional[str] = Header(None)
):
    """
    Process chat messages and return AI responses
    Extract user context from Authorization header for deployment requests
    """
    try:
        # Extract user context from Authorization token if available
        user_email = request.user_email or os.getenv("USER_EMAIL", "admin@example.com")
        user_name = request.user_name or os.getenv("USER_NAME", "Admin User")
        
        if authorization and authorization.startswith("Bearer "):
            try:
                token = authorization.replace("Bearer ", "")
                token_payload = auth_manager.validate_token(token)
                user_context = auth_manager.get_user_context(token_payload)
                user_email = user_context.get("email", user_email)
                user_name = user_context.get("name", user_name)
            except Exception as auth_error:
                # Log but don't fail - use fallback values
                print(f"⚠️ Auth token validation failed: {auth_error}")
        
        # Set user context for deployment operations
        ai_agent.set_user_context(user_email, user_name)
        
        # Enhance user message with subscription context if provided
        enhanced_message = request.message
        if request.subscription_context and request.subscription_context.startswith('mg:'):
            # Management Group selected - resolve child subscriptions
            mg_id = request.subscription_context[3:]  # Strip 'mg:' prefix
            mg_sub_ids = resolve_mg_subscriptions(mg_id)
            if mg_sub_ids:
                sub_list = ', '.join(mg_sub_ids)
                context_info = f"\n\n[SYSTEM CONTEXT: User has selected Management Group '{request.subscription_name}'. This MG contains {len(mg_sub_ids)} subscription(s). Pass ALL these subscription IDs in the subscriptions parameter when calling functions: [{sub_list}]. Include subscription name in output for multi-subscription results. Do NOT pass the management group ID as a subscription - only use the actual subscription GUIDs listed above.]"
                enhanced_message = request.message + context_info
            else:
                # Fallback: couldn't resolve MG subscriptions
                context_info = "\n\n[SYSTEM CONTEXT: User selected a Management Group but no child subscriptions could be resolved. Query across ALL accessible subscriptions. Do NOT pass any specific subscription IDs - leave the subscriptions parameter empty or omit it.]"
                enhanced_message = request.message + context_info
        elif request.subscription_context and request.subscription_context.lower() not in ['all', 'none', 'loading']:
            # Single subscription selected - add context for AI to use
            context_info = f"\n\n[SYSTEM CONTEXT: User has selected subscription '{request.subscription_name}' (ID: {request.subscription_context}) in the UI. Use this subscription ID automatically for all queries. Pass this ID in the subscriptions parameter when calling functions.]"
            enhanced_message = request.message + context_info
        elif request.all_subscriptions or (request.subscription_context and request.subscription_context.lower() == 'all'):
            # All subscriptions selected - tell AI to query all accessible subscriptions
            context_info = "\n\n[SYSTEM CONTEXT: User has selected 'All Subscriptions' context. Query across ALL accessible Azure subscriptions. Do NOT pass any specific subscription IDs to functions - leave the subscriptions parameter empty or omit it to query all. Include subscription name/ID in the output columns for multi-subscription results.]"
            enhanced_message = request.message + context_info
        else:
            # No subscription context provided - use default from environment
            default_sub_id = os.getenv("AZURE_SUBSCRIPTION_ID")
            if default_sub_id:
                context_info = f"\n\n[SYSTEM CONTEXT: No subscription selected in UI. Using default subscription (ID: {default_sub_id}). Pass this ID in the subscriptions parameter when calling functions. Do NOT use literal string 'subscription_context' - use the actual subscription ID provided.]"
                enhanced_message = request.message + context_info
        
        response, updated_history = await ai_agent.process_message(
            enhanced_message,
            request.conversation_history
        )
        
        return ChatResponse(
            response=response,
            conversation_history=updated_history
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/subscriptions")
async def get_subscriptions(req: Request = None):
    """Get available Azure subscriptions"""
    try:
        subscriptions = await resource_manager.get_subscriptions()
        # Return subscriptions in correct format for frontend
        return subscriptions if isinstance(subscriptions, list) else []
    except Exception as e:
        print(f"Error fetching subscriptions: {e}")
        # Return empty array on error so UI doesn't break
        return []


@app.get("/api/subscriptions-hierarchy")
async def get_subscriptions_hierarchy(req: Request = None):
    """Get subscriptions with management group hierarchy for context selector"""
    try:
        result = await resource_manager.get_subscriptions_with_hierarchy()
        return result
    except Exception as e:
        print(f"Error fetching subscriptions hierarchy: {e}")
        return {"subscriptions": [], "managementGroups": [], "error": str(e)}


@app.get("/api/security-score/{subscription_id}")
async def get_security_score(
    subscription_id: str,
    req: Request = None
):
    """Get Microsoft Defender for Cloud secure score for a subscription"""
    try:
        import requests as http_requests
        
        credential = get_cached_credential()
        
        # Handle special values
        if subscription_id in ['all', 'current', 'none', 'loading']:
            subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        
        if not subscription_id:
            return {"error": "No subscription ID provided", "score": None}
        
        # Resolve management group to first child subscription for security score
        if subscription_id.startswith('mg:'):
            mg_subs = resolve_mg_subscriptions(subscription_id[3:])
            if mg_subs:
                subscription_id = mg_subs[0]  # Use first subscription for security score
            else:
                return {"error": "No subscriptions found under management group", "score": None}
        
        # Get access token
        token = credential.get_token("https://management.azure.com/.default")
        
        # Use REST API directly for secure scores (more reliable than SDK)
        api_url = f"https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.Security/secureScores?api-version=2020-01-01"
        
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }
        
        response = http_requests.get(api_url, headers=headers, timeout=45)
        
        print(f"🛡️ Security Score API Response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            scores = data.get("value", [])
            
            if scores:
                # Usually there's one score called 'ascScore'
                main_score = scores[0]
                properties = main_score.get("properties", {})
                current_score = properties.get("score", {}).get("current", 0)
                max_score = properties.get("score", {}).get("max", 100)
                percentage = properties.get("score", {}).get("percentage", 0) * 100
                
                print(f"🛡️ Security Score: {percentage}% (current: {current_score}, max: {max_score})")
                
                return {
                    "score": round(percentage, 1),
                    "current": current_score,
                    "max": max_score,
                    "subscriptionId": subscription_id
                }
            else:
                return {"score": None, "error": "No security score data - Defender for Cloud may not be enabled"}
        elif response.status_code == 403:
            return {"score": None, "error": "Access denied - ensure Security Reader role is assigned"}
        elif response.status_code == 404:
            return {"score": None, "error": "Defender for Cloud not enabled for this subscription"}
        else:
            print(f"🛡️ Security Score API Error: {response.text}")
            return {"score": None, "error": f"API error: {response.status_code}"}
            
    except Exception as e:
        print(f"Error fetching security score: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "score": None}


@app.get("/api/resource-count/{subscription_id}")
async def get_resource_count(subscription_id: str, req: Request = None):
    """Get total resource count directly via Azure Resource Graph - fast, no OpenAI"""
    try:
        import requests as http_requests
        
        credential = get_cached_credential()
        
        if subscription_id in ['all', 'current', 'none', 'loading']:
            subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        
        if not subscription_id:
            return {"count": None, "error": "No subscription ID"}
        
        # Resolve management group to child subscriptions
        mg_resolved = False
        if subscription_id.startswith('mg:'):
            mg_subs = resolve_mg_subscriptions(subscription_id[3:])
            if mg_subs:
                sub_list = mg_subs
                mg_resolved = True
            else:
                fallback = os.getenv('AZURE_SUBSCRIPTION_ID')
                sub_list = [fallback] if fallback else []
        else:
            sub_list = [subscription_id]
        
        if not sub_list:
            return {"count": None, "error": "No subscriptions resolved"}
        
        token = credential.get_token("https://management.azure.com/.default")
        
        api_url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2021-03-01"
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }
        body = {
            "subscriptions": sub_list,
            "query": "Resources | summarize totalCount=count()"
        }
        
        response = http_requests.post(api_url, headers=headers, json=body, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            records = data.get("data", [])
            if isinstance(records, list) and len(records) > 0:
                total = records[0].get("totalCount", 0)
            else:
                rows = records.get("rows", []) if isinstance(records, dict) else []
                total = rows[0][0] if rows else 0
            return {"count": total, "subscriptionId": subscription_id if not mg_resolved else f"mg:{len(sub_list)} subscriptions"}
        else:
            return {"count": None, "error": f"API error: {response.status_code}"}
            
    except Exception as e:
        print(f"Error fetching resource count: {e}")
        import traceback
        traceback.print_exc()
        return {"count": None, "error": str(e)}


@app.get("/api/public-access-exposure/{subscription_id}")
async def get_public_access_exposure(subscription_id: str, req: Request = None):
    """Get count of resources with public access exposure - VMs with public IPs + PaaS with public access"""
    try:
        import requests as http_requests
        
        credential = get_cached_credential()
        
        if subscription_id in ['all', 'current', 'none', 'loading']:
            subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        
        if not subscription_id:
            return {"count": None, "error": "No subscription ID"}
        
        # Resolve management group to child subscriptions
        if subscription_id.startswith('mg:'):
            mg_subs = resolve_mg_subscriptions(subscription_id[3:])
            if mg_subs:
                sub_list = mg_subs
            else:
                fallback = os.getenv('AZURE_SUBSCRIPTION_ID')
                sub_list = [fallback] if fallback else []
        else:
            sub_list = [subscription_id]
        
        if not sub_list:
            return {"count": None, "error": "No subscriptions resolved"}
        
        token = credential.get_token("https://management.azure.com/.default")
        
        api_url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2021-03-01"
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }
        
        # Query 1: VMs with public IP addresses
        vm_query = """
        Resources
        | where type =~ 'microsoft.network/publicipaddresses'
        | where isnotempty(properties.ipConfiguration.id)
        | project pipId = id, pipName = name, attachedTo = tostring(properties.ipConfiguration.id)
        | summarize vmPublicIPs = count()
        """
        
        # Query 2: PaaS services with public access enabled
        paas_query = """
        Resources
        | where (
            (type =~ 'microsoft.storage/storageaccounts' and properties.networkAcls.defaultAction =~ 'Allow')
            or (type =~ 'microsoft.sql/servers' and properties.publicNetworkAccess =~ 'Enabled')
            or (type =~ 'microsoft.dbforpostgresql/flexibleservers' and properties.network.publicNetworkAccess =~ 'Enabled')
            or (type =~ 'microsoft.dbformysql/flexibleservers' and properties.network.publicNetworkAccess =~ 'Enabled')
            or (type =~ 'microsoft.documentdb/databaseaccounts' and properties.publicNetworkAccess =~ 'Enabled')
            or (type =~ 'microsoft.web/sites' and properties.publicNetworkAccess != 'Disabled')
            or (type =~ 'microsoft.keyvault/vaults' and properties.networkAcls.defaultAction =~ 'Allow')
            or (type =~ 'microsoft.containerregistry/registries' and properties.publicNetworkAccess =~ 'Enabled')
            or (type =~ 'microsoft.cognitiveservices/accounts' and properties.publicNetworkAccess =~ 'Enabled')
        )
        | summarize paasPublicAccess = count()
        """
        
        total_exposed = 0
        breakdown = {}
        
        # Execute VM public IP query
        body1 = {"subscriptions": sub_list, "query": vm_query}
        resp1 = http_requests.post(api_url, headers=headers, json=body1, timeout=20)
        if resp1.status_code == 200:
            data1 = resp1.json().get("data", {})
            if isinstance(data1, list) and len(data1) > 0:
                vm_count = data1[0].get("vmPublicIPs", 0)
            else:
                rows = data1.get("rows", []) if isinstance(data1, dict) else []
                vm_count = rows[0][0] if rows else 0
            total_exposed += vm_count
            breakdown["publicIPs"] = vm_count
        
        # Execute PaaS public access query
        body2 = {"subscriptions": sub_list, "query": paas_query}
        resp2 = http_requests.post(api_url, headers=headers, json=body2, timeout=20)
        if resp2.status_code == 200:
            data2 = resp2.json().get("data", {})
            if isinstance(data2, list) and len(data2) > 0:
                paas_count = data2[0].get("paasPublicAccess", 0)
            else:
                rows = data2.get("rows", []) if isinstance(data2, dict) else []
                paas_count = rows[0][0] if rows else 0
            total_exposed += paas_count
            breakdown["paasPublicAccess"] = paas_count
        
        return {
            "count": total_exposed,
            "breakdown": breakdown,
            "subscriptionId": subscription_id
        }
            
    except Exception as e:
        print(f"Error fetching public access exposure: {e}")
        import traceback
        traceback.print_exc()
        return {"count": None, "error": str(e)}


@app.get("/api/export-csv/{query_id}")
async def export_csv(
    query_id: str,
    req: Request = None
):
    """
    Export full query results as CSV
    This endpoint returns ALL data from the cached query, not just what's displayed
    """
    try:
        # Clean up old cache entries (older than 1 hour)
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        expired_keys = [k for k, v in query_results_cache.items() 
                       if v.get("timestamp", datetime.min) < cutoff_time]
        for key in expired_keys:
            del query_results_cache[key]
        
        # Check if query exists in cache
        if query_id not in query_results_cache:
            raise HTTPException(status_code=404, detail="Query results not found or expired. Please run the query again.")
        
        cached = query_results_cache[query_id]
        data = cached.get("data", [])
        query_type = cached.get("query_type", "azure_export")
        
        if not data:
            raise HTTPException(status_code=404, detail="No data found for this query")
        
        # Generate CSV content
        output = io.StringIO()
        
        # Add BOM for Excel UTF-8 compatibility
        output.write('\ufeff')
        
        # Write headers (first row)
        if data:
            headers = list(data[0].keys()) if isinstance(data[0], dict) else []
            output.write(','.join(headers) + '\n')
            
            # Write data rows
            for row in data:
                if isinstance(row, dict):
                    row_values = []
                    for h in headers:
                        val = str(row.get(h, ''))
                        # Escape quotes and wrap if contains comma, quote, or newline
                        if ',' in val or '"' in val or '\n' in val:
                            val = '"' + val.replace('"', '""') + '"'
                        row_values.append(val)
                    output.write(','.join(row_values) + '\n')
        
        # Generate filename with timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"{query_type}_{timestamp}.csv"
        
        # Return as streaming response
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'X-Total-Rows': str(len(data))
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error exporting CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/query-info/{query_id}")
async def get_query_info(
    query_id: str,
    req: Request = None
):
    """Get information about a cached query (row count, type, etc.)"""
    if query_id not in query_results_cache:
        return {"exists": False, "total_rows": 0}
    
    cached = query_results_cache[query_id]
    return {
        "exists": True,
        "total_rows": len(cached.get("data", [])),
        "query_type": cached.get("query_type", "unknown"),
        "timestamp": cached.get("timestamp", "").isoformat() if cached.get("timestamp") else None
    }


# ═══════════════════════════════════════════════════════════════
# ARCHITECTURE DIAGRAM ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/diagram/{diagram_id}")
async def get_diagram_image(diagram_id: str):
    """
    Serve a generated architecture diagram as a PNG image.
    Diagrams are cached in the AI agent's diagram_cache.
    """
    import base64

    # Check agent's diagram cache
    if not hasattr(ai_agent, 'diagram_cache') or diagram_id not in ai_agent.diagram_cache:
        raise HTTPException(status_code=404, detail="Diagram not found or expired. Please regenerate.")

    cached = ai_agent.diagram_cache[diagram_id]
    image_data = base64.b64decode(cached["base64_image"])

    return StreamingResponse(
        io.BytesIO(image_data),
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="azure_diagram_{diagram_id}.png"',
            "Cache-Control": "public, max-age=3600"
        }
    )


@app.get("/api/diagram-download/{diagram_id}")
async def download_diagram(diagram_id: str, format: str = "png"):
    """
    Download a generated architecture diagram in PNG, JPEG, or SVG format.
    Query param: ?format=png|jpeg|svg (default: png)
    """
    import base64

    if not hasattr(ai_agent, 'diagram_cache') or diagram_id not in ai_agent.diagram_cache:
        raise HTTPException(status_code=404, detail="Diagram not found or expired. Please regenerate.")

    cached = ai_agent.diagram_cache[diagram_id]
    image_data = base64.b64decode(cached["base64_image"])
    title_slug = cached.get("title", "azure_architecture").replace(" ", "_").lower()[:50]
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    fmt = format.lower().strip()

    if fmt == "jpeg" or fmt == "jpg":
        # Convert PNG to JPEG using Pillow
        try:
            from PIL import Image
            png_image = Image.open(io.BytesIO(image_data))
            # JPEG doesn't support transparency, so paste onto white background
            if png_image.mode in ('RGBA', 'LA') or (png_image.mode == 'P' and 'transparency' in png_image.info):
                background = Image.new('RGB', png_image.size, (255, 255, 255))
                if png_image.mode == 'P':
                    png_image = png_image.convert('RGBA')
                background.paste(png_image, mask=png_image.split()[-1])
                png_image = background
            elif png_image.mode != 'RGB':
                png_image = png_image.convert('RGB')
            jpeg_buffer = io.BytesIO()
            png_image.save(jpeg_buffer, format='JPEG', quality=95)
            jpeg_buffer.seek(0)
            return StreamingResponse(
                jpeg_buffer,
                media_type="image/jpeg",
                headers={
                    "Content-Disposition": f'attachment; filename="{title_slug}_{timestamp}.jpg"',
                    "X-Image-Size-KB": str(round(jpeg_buffer.getbuffer().nbytes / 1024, 1))
                }
            )
        except ImportError:
            # Pillow not installed, fall back to PNG
            pass

    if fmt == "svg":
        # SVG conversion: embed PNG as base64 inside an SVG wrapper
        b64_str = cached["base64_image"]
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(image_data))
            w, h = img.size
        except ImportError:
            w, h = 1200, 800  # default fallback
        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <title>{cached.get("title", "Azure Architecture Diagram")}</title>
  <image width="{w}" height="{h}" xlink:href="data:image/png;base64,{b64_str}"/>
</svg>'''
        return StreamingResponse(
            io.BytesIO(svg_content.encode('utf-8')),
            media_type="image/svg+xml",
            headers={
                "Content-Disposition": f'attachment; filename="{title_slug}_{timestamp}.svg"'
            }
        )

    # Default: PNG
    return StreamingResponse(
        io.BytesIO(image_data),
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="{title_slug}_{timestamp}.png"',
            "X-Image-Size-KB": str(cached.get("image_size_kb", 0))
        }
    )


class ExecuteApprovedRequest(BaseModel):
    requestId: str
    command: str
    resourceName: str
    resourceType: str


@app.post("/api/execute-approved")
async def execute_approved_command(
    request: ExecuteApprovedRequest,
    req: Request = None
):
    """
    Execute an approved Azure CLI command from Logic App
    This endpoint is called by the Logic App after approval
    """
    try:
        import subprocess
        import shlex
        
        print(f"🟢 EXECUTING APPROVED COMMAND")
        print(f"   Request ID: {request.requestId}")
        print(f"   Resource: {request.resourceName}")
        print(f"   Type: {request.resourceType}")
        print(f"   Command: {request.command}")
        
        # Execute the CLI command
        result = subprocess.run(
            request.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            print(f"✅ Command executed successfully")
            print(f"   Output: {result.stdout}")
            return {
                "status": "success",
                "requestId": request.requestId,
                "output": result.stdout,
                "message": f"Resource {request.resourceName} deployed successfully"
            }
        else:
            print(f"❌ Command failed with exit code {result.returncode}")
            print(f"   Error: {result.stderr}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "failed",
                    "requestId": request.requestId,
                    "error": result.stderr,
                    "message": f"Failed to deploy {request.resourceName}"
                }
            )
            
    except subprocess.TimeoutExpired:
        return JSONResponse(
            status_code=408,
            content={
                "status": "timeout",
                "requestId": request.requestId,
                "error": "Command execution timed out after 5 minutes"
            }
        )
    except Exception as e:
        print(f"❌ Exception during execution: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "requestId": request.requestId,
                "error": str(e)
            }
        )


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount Icons folder for Azure service icons
import os.path
if os.path.exists("Icons"):
    app.mount("/Icons", StaticFiles(directory="Icons"), name="icons")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
