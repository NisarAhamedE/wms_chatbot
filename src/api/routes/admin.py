"""
Admin API Routes
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any

from ..models import APIResponse, PerformanceMetrics
from ..auth import get_current_user, UserContext, require_role

router = APIRouter()


@router.get("/metrics", response_model=PerformanceMetrics)
async def get_system_metrics(
    user_context: UserContext = Depends(require_role(['admin_user', 'management_user']))
):
    """Get system performance metrics"""
    try:
        # Mock metrics - would gather from actual monitoring
        metrics = PerformanceMetrics(
            requests_per_minute=125.5,
            average_response_time=0.234,
            error_rate=0.01,
            active_sessions=45,
            database_connections=8,
            memory_usage_mb=512.3,
            cpu_usage_percent=15.7
        )
        
        return metrics
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users")
async def get_users(
    user_context: UserContext = Depends(require_role(['admin_user']))
):
    """Get system users"""
    try:
        # Mock user data
        users = [
            {"user_id": "user1", "role": "end_user", "last_active": "2024-01-15T10:30:00"},
            {"user_id": "admin1", "role": "admin_user", "last_active": "2024-01-15T11:45:00"}
        ]
        
        return APIResponse(
            success=True,
            data={"users": users, "total_count": len(users)},
            message="Users retrieved successfully"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))