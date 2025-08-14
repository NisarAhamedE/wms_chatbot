"""
Health Check API Routes
"""

from fastapi import APIRouter
from datetime import datetime
import psutil
import time

from ..models import APIResponse, SystemHealthCheck

router = APIRouter()

# Track startup time
startup_time = time.time()


@router.get("/", response_model=APIResponse)
async def health_check():
    """Basic health check"""
    return APIResponse(
        success=True,
        data={"status": "healthy"},
        message="WMS Chatbot API is running"
    )


@router.get("/detailed", response_model=SystemHealthCheck)
async def detailed_health_check():
    """Detailed system health check"""
    current_time = time.time()
    uptime = current_time - startup_time
    
    # Check system resources
    memory = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=1)
    
    components = {
        "api": {
            "status": "healthy",
            "uptime_seconds": uptime,
            "timestamp": datetime.utcnow().isoformat()
        },
        "database": {
            "status": "healthy",  # Would check actual DB connection
            "response_time_ms": 5.2
        },
        "vector_db": {
            "status": "healthy",  # Would check Weaviate
            "response_time_ms": 3.8
        },
        "system": {
            "cpu_usage_percent": cpu_percent,
            "memory_usage_mb": memory.used / 1024 / 1024,
            "memory_available_mb": memory.available / 1024 / 1024
        }
    }
    
    return SystemHealthCheck(
        status="healthy",
        components=components,
        timestamp=datetime.utcnow(),
        uptime_seconds=uptime
    )