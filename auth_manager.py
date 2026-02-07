"""
Entra ID Authentication Manager for Azure CloudOps Agent
Handles user authentication, token validation, and user context management
"""
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient
import logging

logger = logging.getLogger(__name__)

# Entra ID Configuration
TENANT_ID = os.getenv("ENTRA_TENANT_ID") or os.getenv("AZURE_TENANT_ID", "8d7622f8-d815-4120-b5b8-bee841c23a1c")
CLIENT_ID = os.getenv("ENTRA_APP_CLIENT_ID") or os.getenv("AZURE_CLIENT_ID")  # App Registration Client ID
ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
JWKS_URI = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"

security = HTTPBearer()


class AuthManager:
    """Manages Entra ID authentication and user context"""
    
    def __init__(self):
        self.jwks_client = PyJWKClient(JWKS_URI)
        self.client_id = CLIENT_ID
        
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate JWT token from Entra ID
        
        Args:
            token: Bearer token from request header
            
        Returns:
            Decoded token payload with user information
            
        Raises:
            HTTPException: If token is invalid
        """
        try:
            # Get signing key from JWKS
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            
            # Decode and validate token
            # For ID tokens, audience should be our client_id
            # For access tokens, audience might be MS Graph
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=[self.client_id, f"api://{self.client_id}", "00000003-0000-0000-c000-000000000000"],  # Allow our app, our API, or MS Graph
                issuer=ISSUER,
                options={"verify_exp": True}
            )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.error("Token has expired")
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid token: {e}")
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            raise HTTPException(status_code=401, detail="Authentication failed")
    
    def get_user_context(self, token_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract user context from validated token
        
        Args:
            token_payload: Decoded JWT payload
            
        Returns:
            User context dictionary with identity information
        """
        return {
            "user_id": token_payload.get("oid"),  # Object ID (unique user identifier)
            "user_principal_name": token_payload.get("upn") or token_payload.get("preferred_username"),
            "name": token_payload.get("name"),
            "email": token_payload.get("email") or token_payload.get("upn"),
            "tenant_id": token_payload.get("tid"),
            "roles": token_payload.get("roles", []),
            "groups": token_payload.get("groups", []),
            "app_roles": token_payload.get("app_roles", [])
        }
    
    def has_role(self, user_context: Dict[str, Any], required_role: str) -> bool:
        """
        Check if user has required role
        
        Args:
            user_context: User context from get_user_context
            required_role: Role name to check
            
        Returns:
            True if user has role, False otherwise
        """
        return required_role in user_context.get("roles", [])
    
    def has_admin_access(self, user_context: Dict[str, Any]) -> bool:
        """
        Check if user has admin access
        
        Args:
            user_context: User context from get_user_context
            
        Returns:
            True if user is admin, False otherwise
        """
        admin_roles = ["Admin", "CloudOpsAdmin", "InfrastructureAdmin"]
        return any(role in user_context.get("roles", []) for role in admin_roles)


# Global instance
_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """Get or create global AuthManager instance"""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager


# FastAPI Dependency for authentication
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get authenticated user from request
    
    Usage:
        @app.get("/api/protected")
        async def protected_route(user: Dict = Depends(get_current_user)):
            return {"user": user["name"]}
    
    Returns:
        User context dictionary
        
    Raises:
        HTTPException: If authentication fails
    """
    auth_manager = get_auth_manager()
    token = credentials.credentials
    
    # Validate token
    token_payload = auth_manager.validate_token(token)
    
    # Get user context
    user_context = auth_manager.get_user_context(token_payload)
    
    logger.info(f"Authenticated user: {user_context['user_principal_name']}")
    
    return user_context


# Optional authentication for backward compatibility
async def get_current_user_optional(
    request: Request
) -> Optional[Dict[str, Any]]:
    """
    Optional authentication - returns None if no token provided
    Useful for maintaining backward compatibility
    
    Returns:
        User context if authenticated, None otherwise
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    try:
        token = auth_header.split(" ")[1]
        auth_manager = get_auth_manager()
        token_payload = auth_manager.validate_token(token)
        return auth_manager.get_user_context(token_payload)
    except Exception as e:
        logger.warning(f"Optional authentication failed: {e}")
        return None


def generate_auth_url(redirect_uri: str) -> str:
    """
    Generate Entra ID login URL for frontend
    
    Args:
        redirect_uri: URL to redirect after login
        
    Returns:
        Authorization URL for user login
    """
    auth_url = (
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize?"
        f"client_id={CLIENT_ID}&"
        f"response_type=token&"
        f"redirect_uri={redirect_uri}&"
        f"scope=openid profile email User.Read&"
        f"response_mode=fragment"
    )
    return auth_url
