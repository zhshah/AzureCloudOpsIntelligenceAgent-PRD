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
        if request.subscription_context and request.subscription_context.lower() not in ['all', 'none', 'loading']:
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
        from azure.identity import DefaultAzureCredential
        import requests as http_requests
        
        credential = DefaultAzureCredential()
        
        # Handle special values
        if subscription_id in ['all', 'current', 'none', 'loading']:
            subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        
        if not subscription_id:
            return {"error": "No subscription ID provided", "score": None}
        
        # Remove mg: prefix if management group
        if subscription_id.startswith('mg:'):
            return {"error": "Security score requires a subscription, not management group", "score": None}
        
        # Get access token
        token = credential.get_token("https://management.azure.com/.default")
        
        # Use REST API directly for secure scores (more reliable than SDK)
        api_url = f"https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.Security/secureScores?api-version=2020-01-01"
        
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }
        
        response = http_requests.get(api_url, headers=headers, timeout=15)
        
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
