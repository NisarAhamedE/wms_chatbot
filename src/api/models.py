"""
API Models and Schemas
Pydantic models for request/response validation.
"""

from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """User roles in the system"""
    END_USER = "end_user"
    OPERATIONS_USER = "operations_user"
    ADMIN_USER = "admin_user"
    MANAGEMENT_USER = "management_user"
    CEO_USER = "ceo_user"


class MediaType(str, Enum):
    """Supported media types"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"


class ProcessingStatus(str, Enum):
    """Content processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Base Response Models
class APIResponse(BaseModel):
    """Standard API response format"""
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Error response format"""
    success: bool = False
    error: str
    error_code: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Chat API Models
class ChatMessage(BaseModel):
    """Individual chat message"""
    role: str = Field(..., regex="^(user|assistant|system)$")
    content: str = Field(..., min_length=1, max_length=10000)
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    """Chat request payload"""
    message: str = Field(..., min_length=1, max_length=10000, description="User message")
    user_id: str = Field(..., min_length=1, max_length=100)
    user_role: UserRole = Field(default=UserRole.END_USER)
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    preferred_category: Optional[str] = None
    preferred_sub_category: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "message": "Show me all orders from today",
                "user_id": "user123",
                "user_role": "operations_user",
                "session_id": "session456"
            }
        }


class ChatResponse(BaseModel):
    """Chat response payload"""
    response: str
    agent_info: Dict[str, Any]
    processing_time: float
    session_id: str
    confidence: Optional[float] = None
    suggestions: Optional[List[str]] = None
    data_quality: Optional[Dict[str, Any]] = None
    performance_info: Optional[Dict[str, Any]] = None


class ChatHistory(BaseModel):
    """Chat conversation history"""
    session_id: str
    messages: List[ChatMessage]
    created_at: datetime
    updated_at: datetime
    user_id: str
    metadata: Optional[Dict[str, Any]] = None


# Operational Database Models
class DatabaseConnectionRequest(BaseModel):
    """Database connection configuration"""
    server: str = Field(..., description="Database server address")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password", min_length=8)
    port: int = Field(default=1433, ge=1, le=65535)
    
    class Config:
        schema_extra = {
            "example": {
                "server": "wms-sql-server.company.com",
                "database": "WMS_Production",
                "username": "wms_readonly",
                "password": "secure_password123",
                "port": 1433
            }
        }


class OperationalQueryRequest(BaseModel):
    """Operational database query request"""
    query: str = Field(..., min_length=1, max_length=5000, description="Natural language query")
    category: Optional[str] = None
    max_rows: Optional[int] = Field(default=1000, ge=1, le=50000)
    include_performance_analysis: bool = Field(default=True)
    
    class Config:
        schema_extra = {
            "example": {
                "query": "Show me all orders with status pending from this week",
                "category": "orders",
                "max_rows": 1000,
                "include_performance_analysis": true
            }
        }


class QueryExecutionResult(BaseModel):
    """Query execution result"""
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    row_count: int = 0
    execution_time: float = 0.0
    query_used: str = ""
    data_quality: Optional[Dict[str, Any]] = None
    performance: Optional[Dict[str, Any]] = None
    warnings: List[str] = Field(default_factory=list)


class SchemaExtractionRequest(BaseModel):
    """Schema extraction request"""
    include_sample_data: bool = Field(default=True)
    sample_size: int = Field(default=5, ge=1, le=20)
    force_refresh: bool = Field(default=False)


class IndexRecommendation(BaseModel):
    """Database index recommendation"""
    table_name: str
    columns: List[str]
    index_type: str
    priority: str
    reason: str
    estimated_benefit: str
    sql_create_statement: str


# Content Processing Models
class ContentUploadRequest(BaseModel):
    """Content upload metadata"""
    content_type: MediaType
    filename: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    user_id: str
    
    class Config:
        schema_extra = {
            "example": {
                "content_type": "image",
                "filename": "warehouse_layout.jpg",
                "description": "Warehouse floor plan",
                "tags": ["layout", "locations"],
                "user_id": "user123"
            }
        }


class ContentProcessingResult(BaseModel):
    """Content processing result"""
    content_id: str
    success: bool
    extracted_text: str = ""
    categories: List[str] = Field(default_factory=list)
    entities: Dict[str, List[str]] = Field(default_factory=dict)
    confidence: float = 0.0
    processing_time: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class ContentSearchRequest(BaseModel):
    """Content search request"""
    query: str = Field(..., min_length=1, max_length=1000)
    categories: Optional[List[str]] = None
    content_types: Optional[List[MediaType]] = None
    limit: int = Field(default=10, ge=1, le=100)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ContentSearchResult(BaseModel):
    """Content search result"""
    content_id: str
    content_type: str
    extracted_text_preview: str
    categories: List[str]
    confidence: float
    relevance_score: float
    created_at: datetime


# Admin API Models
class SystemHealthCheck(BaseModel):
    """System health check result"""
    status: str
    components: Dict[str, Dict[str, Any]]
    timestamp: datetime
    uptime_seconds: float


class UserManagementRequest(BaseModel):
    """User management request"""
    user_id: str
    user_role: UserRole
    permissions: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class ConfigurationUpdate(BaseModel):
    """System configuration update"""
    component: str
    settings: Dict[str, Any]
    restart_required: bool = False


class PerformanceMetrics(BaseModel):
    """System performance metrics"""
    requests_per_minute: float
    average_response_time: float
    error_rate: float
    active_sessions: int
    database_connections: int
    memory_usage_mb: float
    cpu_usage_percent: float


class AuditLogEntry(BaseModel):
    """Audit log entry"""
    user_id: str
    action: str
    resource: str
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Streaming Response Models
class StreamingChatChunk(BaseModel):
    """Streaming chat response chunk"""
    chunk_id: str
    content: str
    is_final: bool = False
    metadata: Optional[Dict[str, Any]] = None


# Batch Processing Models
class BatchProcessingRequest(BaseModel):
    """Batch processing request"""
    items: List[Dict[str, Any]]
    processing_type: str
    priority: str = Field(default="normal", regex="^(low|normal|high|urgent)$")
    callback_url: Optional[str] = None


class BatchProcessingStatus(BaseModel):
    """Batch processing status"""
    batch_id: str
    status: ProcessingStatus
    total_items: int
    processed_items: int
    failed_items: int
    progress_percentage: float
    estimated_completion: Optional[datetime] = None
    results_available: bool = False


# WebSocket Models
class WebSocketMessage(BaseModel):
    """WebSocket message format"""
    type: str = Field(..., regex="^(chat|notification|status|error)$")
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class NotificationMessage(BaseModel):
    """System notification message"""
    notification_id: str
    user_id: str
    title: str
    message: str
    priority: str = Field(default="normal", regex="^(low|normal|high|urgent)$")
    read: bool = False
    expires_at: Optional[datetime] = None


# Validation Models
class ConstraintViolationModel(BaseModel):
    """LLM constraint violation"""
    constraint_type: str
    severity: str
    description: str
    suggested_fix: str
    context: Optional[Dict[str, Any]] = None


class ValidationResult(BaseModel):
    """Content validation result"""
    is_valid: bool
    severity: Optional[str] = None
    violations: List[ConstraintViolationModel] = Field(default_factory=list)
    corrected_content: Optional[str] = None


# Pagination Models
class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: Optional[str] = None
    sort_order: str = Field(default="desc", regex="^(asc|desc)$")


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""
    items: List[Any]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool