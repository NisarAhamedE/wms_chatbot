"""
FastAPI Main Application
Enterprise-grade WMS Chatbot API with comprehensive endpoints.
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse, JSONResponse
from contextlib import asynccontextmanager
import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from ..core.config import get_settings
from ..core.logging import setup_logging, get_correlation_id
from ..database.connection import get_database_manager
from ..database.vector_store import get_weaviate_manager
from .routes import (
    chat_router, 
    operational_db_router, 
    content_processing_router,
    admin_router,
    health_router
)
from .middleware import RequestLoggingMiddleware, RateLimitMiddleware
from .auth import get_current_user, UserContext
from .models import APIResponse, ErrorResponse


# Application lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown"""
    # Startup
    logger = logging.getLogger(__name__)
    logger.info("Starting WMS Chatbot API...")
    
    # Initialize core components
    try:
        # Initialize database connections
        db_manager = get_database_manager()
        await db_manager.initialize()
        
        # Initialize vector database
        vector_manager = get_weaviate_manager()
        await vector_manager.initialize()
        
        # Verify system health
        await verify_system_health()
        
        logger.info("WMS Chatbot API started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down WMS Chatbot API...")
    
    try:
        # Close database connections
        await db_manager.close_all()
        
        logger.info("WMS Chatbot API shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


async def verify_system_health():
    """Verify system components are healthy"""
    # This would check database connections, external services, etc.
    pass


# Create FastAPI application
app = FastAPI(
    title="WMS Chatbot API",
    description="Enterprise Warehouse Management System Chatbot with Multi-Modal Processing",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Security
security = HTTPBearer()

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)

# Include routers
app.include_router(health_router, prefix="/health", tags=["Health"])
app.include_router(chat_router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(operational_db_router, prefix="/api/v1/operational-db", tags=["Operational Database"])
app.include_router(content_processing_router, prefix="/api/v1/content", tags=["Content Processing"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["Administration"])


# Root endpoint
@app.get("/", response_model=APIResponse)
async def root():
    """Root endpoint with API information"""
    return APIResponse(
        success=True,
        data={
            "name": "WMS Chatbot API",
            "version": "1.0.0",
            "description": "Enterprise Warehouse Management System Chatbot",
            "features": [
                "Multi-modal content processing (text, image, audio, video)",
                "Operational database integration",
                "80 specialized WMS agents",
                "Real-time query execution",
                "Performance optimization",
                "LLM constraint validation"
            ],
            "endpoints": {
                "chat": "/api/v1/chat",
                "operational_db": "/api/v1/operational-db", 
                "content_processing": "/api/v1/content",
                "health": "/health",
                "docs": "/docs"
            }
        },
        message="WMS Chatbot API is running"
    )


# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            success=False,
            error=exc.detail,
            error_code=exc.status_code,
            correlation_id=get_correlation_id(),
            timestamp=datetime.utcnow().isoformat()
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger = logging.getLogger(__name__)
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            success=False,
            error="Internal server error",
            error_code=500,
            correlation_id=get_correlation_id(),
            timestamp=datetime.utcnow().isoformat()
        ).dict()
    )


# Setup logging
if __name__ == "__main__":
    setup_logging()
    
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
        log_level="info"
    )