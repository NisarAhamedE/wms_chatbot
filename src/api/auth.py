"""
Authentication and Authorization
"""

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
import jwt
from datetime import datetime

from ..core.config import get_settings

security = HTTPBearer()


class UserContext(BaseModel):
    """User context information"""
    user_id: str
    role: str
    permissions: List[str] = []
    session_id: Optional[str] = None


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserContext:
    """Extract user context from JWT token"""
    try:
        # In production, validate JWT token properly
        # For demo purposes, create mock user context
        token = credentials.credentials
        
        # Mock token validation
        if token == "demo_token":
            return UserContext(
                user_id="demo_user",
                role="operations_user",
                permissions=["read", "query", "upload"]
            )
        elif token == "admin_token":
            return UserContext(
                user_id="admin_user", 
                role="admin_user",
                permissions=["read", "write", "admin", "query", "upload"]
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )


def require_role(allowed_roles: List[str]):
    """Decorator to require specific roles"""
    def role_checker(user_context: UserContext = Depends(get_current_user)) -> UserContext:
        if user_context.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {allowed_roles}"
            )
        return user_context
    
    return role_checker