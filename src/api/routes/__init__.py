"""
API Routes Package
"""

from .chat import router as chat_router
from .operational_db import router as operational_db_router
from .content_processing import router as content_processing_router
from .admin import router as admin_router
from .health import router as health_router

__all__ = [
    'chat_router',
    'operational_db_router', 
    'content_processing_router',
    'admin_router',
    'health_router'
]