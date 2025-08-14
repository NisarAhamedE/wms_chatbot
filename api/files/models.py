from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Text, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

Base = declarative_base()

# Enums
class FileStatus(str, Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class FileSource(str, Enum):
    UPLOAD = "upload"
    SCREENSHOT = "screenshot"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"

class ProcessingStage(str, Enum):
    VALIDATION = "validation"
    TEXT_EXTRACTION = "text_extraction"
    CATEGORIZATION = "categorization"
    SUMMARIZATION = "summarization"
    VECTORIZATION = "vectorization"
    STORAGE = "storage"

# Database Models
class FileMetadata(Base):
    __tablename__ = "file_metadata"
    
    id = Column(String(36), primary_key=True, index=True)  # UUID
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_path = Column(String(500), nullable=False)
    
    # Upload information
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    source = Column(String(20), nullable=False)  # FileSource
    
    # Processing status
    status = Column(String(20), default=FileStatus.UPLOADING)
    processing_progress = Column(Float, default=0.0)
    processing_stage = Column(String(50))
    
    # Content information
    extracted_text = Column(Text)
    summary = Column(Text)
    keywords = Column(JSON)  # List of extracted keywords
    categories = Column(JSON)  # List of assigned categories
    tags = Column(JSON)  # User-defined tags
    
    # Analysis results
    confidence_score = Column(Float)
    language = Column(String(10))
    page_count = Column(Integer)  # For documents
    duration = Column(Float)  # For audio/video files
    
    # Metadata
    metadata = Column(JSON)  # Additional file metadata
    processing_log = Column(JSON)  # Processing history
    error_message = Column(Text)
    
    # Timestamps
    processing_started_at = Column(DateTime(timezone=True))
    processing_completed_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    upload_chunks = relationship("FileUploadChunk", back_populates="file_metadata")
    processing_tasks = relationship("FileProcessingTask", back_populates="file_metadata")

class FileUploadChunk(Base):
    __tablename__ = "file_upload_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String(36), ForeignKey("file_metadata.id"), nullable=False)
    chunk_number = Column(Integer, nullable=False)
    chunk_size = Column(Integer, nullable=False)
    chunk_hash = Column(String(64), nullable=False)  # SHA-256 hash
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    file_metadata = relationship("FileMetadata", back_populates="upload_chunks")

class FileProcessingTask(Base):
    __tablename__ = "file_processing_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String(36), ForeignKey("file_metadata.id"), nullable=False)
    task_type = Column(String(50), nullable=False)  # ProcessingStage
    status = Column(String(20), default="pending")
    
    # Task details
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    processing_time = Column(Float)  # in seconds
    
    # Results
    result_data = Column(JSON)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # Priority and scheduling
    priority = Column(Integer, default=0)
    scheduled_at = Column(DateTime(timezone=True))
    
    # Relationship
    file_metadata = relationship("FileMetadata", back_populates="processing_tasks")

class FileCategory(Base):
    __tablename__ = "file_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey("file_categories.id"))
    
    # WMS specific fields
    wms_category = Column(String(100))  # Maps to WMS categories
    processing_rules = Column(JSON)  # Category-specific processing rules
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    # Self-referential relationship for hierarchy
    children = relationship("FileCategory", backref="parent", remote_side=[id])

# Pydantic Models
class FileUploadRequest(BaseModel):
    filename: str
    file_size: int
    mime_type: str
    category: Optional[str] = None
    tags: List[str] = []
    source: FileSource = FileSource.UPLOAD

class FileUploadResponse(BaseModel):
    file_id: str
    upload_url: str
    chunk_size: int
    total_chunks: int

class FileMetadataResponse(BaseModel):
    id: str
    filename: str
    original_name: str
    file_type: str
    file_size: int
    mime_type: str
    uploaded_by: int
    uploaded_at: datetime
    source: str
    status: str
    processing_progress: float
    processing_stage: Optional[str]
    extracted_text: Optional[str]
    summary: Optional[str]
    keywords: List[str] = []
    categories: List[str] = []
    tags: List[str] = []
    confidence_score: Optional[float]
    language: Optional[str]
    page_count: Optional[int]
    duration: Optional[float]
    error_message: Optional[str]
    
    class Config:
        from_attributes = True

class FileListRequest(BaseModel):
    page: int = 1
    limit: int = 25
    category: Optional[List[str]] = None
    file_type: Optional[List[str]] = None
    status: Optional[List[str]] = None
    search_term: Optional[str] = None
    sort_by: str = "uploaded_at"
    sort_order: str = "desc"
    date_range: Optional[Dict[str, str]] = None

class FileListResponse(BaseModel):
    files: List[FileMetadataResponse]
    total_count: int
    current_page: int
    total_pages: int
    has_next: bool
    has_prev: bool

class FileProcessingRequest(BaseModel):
    file_id: str
    extract_text: bool = True
    categorize: bool = True
    generate_summary: bool = True
    extract_keywords: bool = True
    force_reprocess: bool = False

class FileProcessingResponse(BaseModel):
    file_id: str
    status: str
    progress: float
    stage: Optional[str]
    results: Optional[Dict[str, Any]]
    error: Optional[str]

class BulkActionRequest(BaseModel):
    file_ids: List[str]
    action: str  # delete, reprocess, categorize, export, archive
    params: Optional[Dict[str, Any]] = None

class BulkActionResponse(BaseModel):
    success: bool
    message: str
    processed_count: int
    failed_count: int
    results: List[Dict[str, Any]]

class FileExportRequest(BaseModel):
    file_ids: Optional[List[str]] = None
    format: str  # json, csv, excel, pdf
    include_content: bool = False
    include_metadata: bool = True
    filters: Optional[FileListRequest] = None

class FileExportResponse(BaseModel):
    download_url: str
    filename: str
    expires_at: datetime

class ProcessingStatsResponse(BaseModel):
    total_files: int
    processing_files: int
    completed_files: int
    failed_files: int
    categorized_files: int
    extracted_text_files: int
    vectorized_files: int
    storage_used: int  # in bytes
    storage_limit: int  # in bytes
    processing_queue: int
    avg_processing_time: float

class FileSearchRequest(BaseModel):
    query: str
    categories: Optional[List[str]] = None
    file_types: Optional[List[str]] = None
    semantic_search: bool = False
    limit: int = 50

class FileSearchResponse(BaseModel):
    files: List[FileMetadataResponse]
    total_count: int
    search_time: float
    suggestions: List[str] = []

class FileContentRequest(BaseModel):
    file_id: str
    page: Optional[int] = None
    format: str = "text"  # text, html, markdown

class FileContentResponse(BaseModel):
    content: str
    format: str
    page_count: Optional[int]
    current_page: Optional[int]
    metadata: FileMetadataResponse

class FilePreviewResponse(BaseModel):
    preview_url: str
    preview_type: str  # image, pdf, text
    thumbnail_url: Optional[str]

class CategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    parent_id: Optional[int]
    wms_category: Optional[str]
    file_count: int = 0
    
    class Config:
        from_attributes = True

class WMSCategoryConfig(BaseModel):
    name: str
    description: str
    processing_rules: Dict[str, Any]
    keywords: List[str]
    file_types: List[str]

# WMS Categories Configuration
WMS_CATEGORIES = [
    {
        "name": "Wave Management",
        "description": "Wave planning, release strategies, workload balancing",
        "keywords": ["wave", "release", "planning", "workload", "batch"],
        "file_types": ["pdf", "doc", "xls", "txt"]
    },
    {
        "name": "Allocation",
        "description": "Inventory allocation, reservations, demand planning",
        "keywords": ["allocation", "reserve", "demand", "inventory", "stock"],
        "file_types": ["pdf", "doc", "xls", "csv"]
    },
    {
        "name": "Locating and Putaway",
        "description": "Storage location management, putaway strategies",
        "keywords": ["location", "putaway", "storage", "bin", "rack"],
        "file_types": ["pdf", "doc", "jpg", "png"]
    },
    {
        "name": "Picking",
        "description": "Order picking operations, pick path optimization",
        "keywords": ["picking", "order", "pick", "path", "zone"],
        "file_types": ["pdf", "doc", "xls", "jpg"]
    },
    {
        "name": "Cycle Counting",
        "description": "Inventory accuracy, cycle counting procedures",
        "keywords": ["cycle", "count", "accuracy", "inventory", "audit"],
        "file_types": ["pdf", "doc", "xls", "csv"]
    },
    {
        "name": "Replenishment",
        "description": "Stock replenishment strategies, min/max levels",
        "keywords": ["replenishment", "restock", "minimum", "maximum", "level"],
        "file_types": ["pdf", "doc", "xls", "csv"]
    },
    {
        "name": "Labor Management",
        "description": "Workforce optimization, productivity tracking",
        "keywords": ["labor", "workforce", "productivity", "performance", "scheduling"],
        "file_types": ["pdf", "doc", "xls", "csv"]
    },
    {
        "name": "Yard Management",
        "description": "Dock and yard operations, trailer management",
        "keywords": ["yard", "dock", "trailer", "appointment", "gate"],
        "file_types": ["pdf", "doc", "jpg", "png"]
    },
    {
        "name": "Slotting",
        "description": "Optimal product placement, slotting optimization",
        "keywords": ["slotting", "placement", "optimization", "velocity", "cube"],
        "file_types": ["pdf", "doc", "xls", "csv"]
    },
    {
        "name": "Cross-Docking",
        "description": "Direct transfer operations, cross-dock flows",
        "keywords": ["cross-dock", "transfer", "flow", "direct", "staging"],
        "file_types": ["pdf", "doc", "jpg", "png"]
    },
    {
        "name": "Returns Management",
        "description": "Return processing, reverse logistics",
        "keywords": ["returns", "reverse", "rma", "refund", "exchange"],
        "file_types": ["pdf", "doc", "xls", "jpg"]
    },
    {
        "name": "Inventory Management",
        "description": "Stock level monitoring, inventory control",
        "keywords": ["inventory", "stock", "control", "tracking", "adjustment"],
        "file_types": ["pdf", "doc", "xls", "csv"]
    },
    {
        "name": "Order Management",
        "description": "Order lifecycle management, order processing",
        "keywords": ["order", "processing", "fulfillment", "lifecycle", "status"],
        "file_types": ["pdf", "doc", "xls", "csv"]
    },
    {
        "name": "Task Management",
        "description": "Work task coordination, task assignment",
        "keywords": ["task", "assignment", "coordination", "work", "queue"],
        "file_types": ["pdf", "doc", "xls", "jpg"]
    },
    {
        "name": "Reports and Analytics",
        "description": "Business intelligence, reporting, KPIs",
        "keywords": ["report", "analytics", "kpi", "dashboard", "metrics"],
        "file_types": ["pdf", "doc", "xls", "csv", "ppt"]
    },
    {
        "name": "Other",
        "description": "General WMS functionality and miscellaneous documents",
        "keywords": ["general", "misc", "other", "documentation", "training"],
        "file_types": ["pdf", "doc", "txt", "jpg", "png", "mp4", "mp3"]
    }
]