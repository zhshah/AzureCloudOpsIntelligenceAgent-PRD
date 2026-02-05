"""
Azure Cost Intelligence Agent - Main Application
Provides conversational AI interface for Azure cost management and resource queries
"""

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta

from azure_cost_manager import AzureCostManager
from azure_resource_manager import AzureResourceManager
from openai_agent import OpenAIAgent
from auth_manager import get_auth_manager

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Azure Cost Intelligence Agent",
    description="AI-powered Azure cost and resource management",
    version="1.0.0"
)

# Initialize managers
cost_manager = AzureCostManager()
resource_manager = AzureResourceManager()
ai_agent = OpenAIAgent(cost_manager, resource_manager)
auth_manager = get_auth_manager()


class ChatMessage(BaseModel):
    message: str
    conversation_history: Optional[List[Dict[str, str]]] = []
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    subscription_context: Optional[str] = None  # Selected subscription ID
    subscription_name: Optional[str] = None  # Selected subscription name


class ChatResponse(BaseModel):
    response: str
    conversation_history: List[Dict[str, str]]


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main chat interface"""
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


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatMessage, authorization: Optional[str] = Header(None)):
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
        if request.subscription_context:
            # Add subscription context to the message for AI to use
            context_info = f"\n\n[SYSTEM CONTEXT: User has selected subscription '{request.subscription_name}' (ID: {request.subscription_context}) in the UI. Use this subscription automatically for queries unless user explicitly requests a different one.]"
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
async def get_subscriptions():
    """Get available Azure subscriptions"""
    try:
        subscriptions = await resource_manager.get_subscriptions()
        # Return subscriptions in correct format for frontend
        return subscriptions if isinstance(subscriptions, list) else []
    except Exception as e:
        print(f"Error fetching subscriptions: {e}")
        # Return empty array on error so UI doesn't break
        return []


class ExecuteApprovedRequest(BaseModel):
    requestId: str
    command: str
    resourceName: str
    resourceType: str


@app.post("/api/execute-approved")
async def execute_approved_command(request: ExecuteApprovedRequest):
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


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
