from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import os
from datetime import datetime

# Import routers
from .auth.routes import router as auth_router
from .files.routes import router as files_router
from .agents.routes import router as agents_router
from .vector_store.routes import router as vector_router
from .database.connection import db_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting WMS Chatbot API...")
    await db_manager.initialize()
    logger.info("Database connections initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down WMS Chatbot API...")
    await db_manager.close()
    logger.info("Database connections closed")

# Create FastAPI app
app = FastAPI(
    title="WMS Chatbot API",
    description="Enterprise Warehouse Management AI Assistant with 80 specialized agents",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

# Include routers
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(files_router, prefix="/api/v1/files", tags=["File Management"])
app.include_router(agents_router, prefix="/api/v1/agents", tags=["AI Agents"])
app.include_router(vector_router, prefix="/api/v1/vector", tags=["Vector Store"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "WMS Chatbot API",
        "version": "1.0.0",
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connections
        db_status = await db_manager.test_connections()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "api": "operational",
                "postgresql": "operational" if db_status.get("postgresql") else "error",
                "mssql": "operational" if db_status.get("mssql") else "not_configured"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )

@app.get("/api/v1/stats")
async def get_statistics():
    """Get system statistics"""
    from .vector_store.weaviate_client import weaviate_manager
    
    try:
        # Get vector store stats
        vector_stats = await weaviate_manager.get_statistics()
        
        # Get database stats
        db_stats = await db_manager.execute_pg_query("""
            SELECT 
                (SELECT COUNT(*) FROM users) as total_users,
                (SELECT COUNT(*) FROM conversations) as total_conversations,
                (SELECT COUNT(*) FROM messages) as total_messages,
                (SELECT COUNT(*) FROM file_uploads) as total_files,
                (SELECT COUNT(*) FROM agent_logs) as total_agent_calls
        """)
        
        return {
            "database": db_stats[0] if db_stats else {},
            "vector_store": vector_stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)