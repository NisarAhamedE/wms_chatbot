import os
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from pathlib import Path
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func

from ..database import get_db
from ..auth import get_current_user_token
from .models import (
    FileMetadata, FileUploadRequest, FileUploadResponse, FileMetadataResponse,
    FileListRequest, FileListResponse, FileProcessingRequest, FileProcessingResponse,
    BulkActionRequest, BulkActionResponse, FileExportRequest, FileExportResponse,
    ProcessingStatsResponse, FileSearchRequest, FileSearchResponse,
    FileContentRequest, FileContentResponse, FilePreviewResponse,
    CategoryResponse, FileStatus, WMS_CATEGORIES
)
from .processing import file_processor

router = APIRouter(prefix="/files", tags=["files"])

# Configuration
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "100")) * 1024 * 1024  # 100MB default
ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'csv',
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff',
    'mp3', 'wav', 'ogg', 'flac', 'm4a',
    'mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv'
}

@router.post("/upload", response_model=List[FileMetadataResponse])
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form("[]"),
    source: str = Form("upload"),
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Upload multiple files."""
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files can be uploaded at once"
        )
    
    uploaded_files = []
    
    for file in files:
        try:
            # Validate file
            if file.size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File {file.filename} is too large. Maximum size: {MAX_FILE_SIZE // 1024 // 1024}MB"
                )
            
            file_ext = Path(file.filename).suffix.lower().lstrip('.')
            if file_ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File type .{file_ext} is not allowed"
                )
            
            # Generate unique file ID and path
            file_id = str(uuid.uuid4())
            safe_filename = f"{file_id}_{file.filename}"
            file_path = UPLOAD_DIR / safe_filename
            
            # Save file
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            # Create file metadata
            file_metadata = FileMetadata(
                id=file_id,
                filename=safe_filename,
                original_name=file.filename,
                file_type=file_ext,
                file_size=file.size,
                mime_type=file.content_type or "application/octet-stream",
                file_path=str(file_path),
                uploaded_by=token_data["user_id"],
                source=source,
                status=FileStatus.UPLOADING,
                categories=[category] if category else [],
                tags=eval(tags) if tags != "[]" else []
            )
            
            db.add(file_metadata)
            db.commit()
            db.refresh(file_metadata)
            
            uploaded_files.append(FileMetadataResponse.from_orm(file_metadata))
            
            # Start processing in background
            background_tasks.add_task(process_file_background, file_id)
            
        except Exception as e:
            # Clean up file if it was created
            if 'file_path' in locals() and file_path.exists():
                file_path.unlink()
            
            if isinstance(e, HTTPException):
                raise e
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error uploading file {file.filename}: {str(e)}"
                )
    
    return uploaded_files

@router.get("/", response_model=FileListResponse)
async def get_files(
    page: int = 1,
    limit: int = 25,
    category: Optional[str] = None,
    file_type: Optional[str] = None,
    status: Optional[str] = None,
    search_term: Optional[str] = None,
    sort_by: str = "uploaded_at",
    sort_order: str = "desc",
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Get paginated list of files."""
    # Build query
    query = db.query(FileMetadata).filter(
        FileMetadata.uploaded_by == token_data["user_id"]
    )
    
    # Apply filters
    if category:
        query = query.filter(FileMetadata.categories.contains([category]))
    
    if file_type:
        query = query.filter(FileMetadata.file_type == file_type)
    
    if status:
        query = query.filter(FileMetadata.status == status)
    
    if search_term:
        search_filter = or_(
            FileMetadata.original_name.ilike(f"%{search_term}%"),
            FileMetadata.extracted_text.ilike(f"%{search_term}%"),
            FileMetadata.summary.ilike(f"%{search_term}%")
        )
        query = query.filter(search_filter)
    
    # Apply sorting
    sort_column = getattr(FileMetadata, sort_by, FileMetadata.uploaded_at)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))
    
    # Get total count
    total_count = query.count()
    
    # Apply pagination
    offset = (page - 1) * limit
    files = query.offset(offset).limit(limit).all()
    
    # Calculate pagination info
    total_pages = (total_count + limit - 1) // limit
    has_next = page < total_pages
    has_prev = page > 1
    
    return FileListResponse(
        files=[FileMetadataResponse.from_orm(file) for file in files],
        total_count=total_count,
        current_page=page,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )

@router.get("/{file_id}", response_model=FileMetadataResponse)
async def get_file(
    file_id: str,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Get file metadata by ID."""
    file_metadata = db.query(FileMetadata).filter(
        and_(
            FileMetadata.id == file_id,
            FileMetadata.uploaded_by == token_data["user_id"]
        )
    ).first()
    
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return FileMetadataResponse.from_orm(file_metadata)

@router.put("/{file_id}", response_model=FileMetadataResponse)
async def update_file(
    file_id: str,
    categories: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Update file metadata."""
    file_metadata = db.query(FileMetadata).filter(
        and_(
            FileMetadata.id == file_id,
            FileMetadata.uploaded_by == token_data["user_id"]
        )
    ).first()
    
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Update metadata
    if categories is not None:
        file_metadata.categories = categories
    
    if tags is not None:
        file_metadata.tags = tags
    
    file_metadata.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(file_metadata)
    
    return FileMetadataResponse.from_orm(file_metadata)

@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Delete a file."""
    file_metadata = db.query(FileMetadata).filter(
        and_(
            FileMetadata.id == file_id,
            FileMetadata.uploaded_by == token_data["user_id"]
        )
    ).first()
    
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Delete physical file
    file_path = Path(file_metadata.file_path)
    if file_path.exists():
        file_path.unlink()
    
    # Delete from database
    db.delete(file_metadata)
    db.commit()
    
    return {"message": "File deleted successfully"}

@router.post("/{file_id}/process", response_model=FileProcessingResponse)
async def process_file(
    file_id: str,
    background_tasks: BackgroundTasks,
    request: FileProcessingRequest,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Trigger file processing."""
    file_metadata = db.query(FileMetadata).filter(
        and_(
            FileMetadata.id == file_id,
            FileMetadata.uploaded_by == token_data["user_id"]
        )
    ).first()
    
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Check if already processing
    if file_metadata.status == FileStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is already being processed"
        )
    
    # Start processing in background
    background_tasks.add_task(process_file_background, file_id)
    
    return FileProcessingResponse(
        file_id=file_id,
        status="processing",
        progress=0.0,
        stage="validation"
    )

@router.get("/{file_id}/processing-status", response_model=FileProcessingResponse)
async def get_processing_status(
    file_id: str,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Get file processing status."""
    file_metadata = db.query(FileMetadata).filter(
        and_(
            FileMetadata.id == file_id,
            FileMetadata.uploaded_by == token_data["user_id"]
        )
    ).first()
    
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return FileProcessingResponse(
        file_id=file_id,
        status=file_metadata.status.value,
        progress=file_metadata.processing_progress,
        stage=file_metadata.processing_stage,
        error=file_metadata.error_message
    )

@router.post("/bulk-action", response_model=BulkActionResponse)
async def bulk_action(
    request: BulkActionRequest,
    background_tasks: BackgroundTasks,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Perform bulk actions on files."""
    # Verify all files belong to user
    files = db.query(FileMetadata).filter(
        and_(
            FileMetadata.id.in_(request.file_ids),
            FileMetadata.uploaded_by == token_data["user_id"]
        )
    ).all()
    
    if len(files) != len(request.file_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Some files not found or access denied"
        )
    
    results = []
    processed_count = 0
    failed_count = 0
    
    for file_metadata in files:
        try:
            if request.action == "delete":
                # Delete physical file
                file_path = Path(file_metadata.file_path)
                if file_path.exists():
                    file_path.unlink()
                
                # Delete from database
                db.delete(file_metadata)
                
                results.append({
                    "file_id": file_metadata.id,
                    "success": True,
                    "message": "File deleted"
                })
                processed_count += 1
            
            elif request.action == "reprocess":
                # Start reprocessing
                background_tasks.add_task(process_file_background, file_metadata.id)
                
                results.append({
                    "file_id": file_metadata.id,
                    "success": True,
                    "message": "Reprocessing started"
                })
                processed_count += 1
            
            elif request.action == "categorize":
                category = request.params.get("category") if request.params else None
                if category:
                    file_metadata.categories = [category]
                    file_metadata.updated_at = datetime.utcnow()
                    
                    results.append({
                        "file_id": file_metadata.id,
                        "success": True,
                        "message": f"Categorized as {category}"
                    })
                    processed_count += 1
                else:
                    results.append({
                        "file_id": file_metadata.id,
                        "success": False,
                        "error": "Category not specified"
                    })
                    failed_count += 1
            
            else:
                results.append({
                    "file_id": file_metadata.id,
                    "success": False,
                    "error": f"Unknown action: {request.action}"
                })
                failed_count += 1
                
        except Exception as e:
            results.append({
                "file_id": file_metadata.id,
                "success": False,
                "error": str(e)
            })
            failed_count += 1
    
    db.commit()
    
    return BulkActionResponse(
        success=failed_count == 0,
        message=f"Processed {processed_count} files, {failed_count} failed",
        processed_count=processed_count,
        failed_count=failed_count,
        results=results
    )

@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Download a file."""
    file_metadata = db.query(FileMetadata).filter(
        and_(
            FileMetadata.id == file_id,
            FileMetadata.uploaded_by == token_data["user_id"]
        )
    ).first()
    
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    file_path = Path(file_metadata.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Physical file not found"
        )
    
    return FileResponse(
        path=str(file_path),
        filename=file_metadata.original_name,
        media_type=file_metadata.mime_type
    )

@router.get("/{file_id}/content", response_model=FileContentResponse)
async def get_file_content(
    file_id: str,
    page: Optional[int] = None,
    format: str = "text",
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Get file content as text."""
    file_metadata = db.query(FileMetadata).filter(
        and_(
            FileMetadata.id == file_id,
            FileMetadata.uploaded_by == token_data["user_id"]
        )
    ).first()
    
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    content = file_metadata.extracted_text or ""
    
    return FileContentResponse(
        content=content,
        format=format,
        page_count=file_metadata.page_count,
        current_page=page,
        metadata=FileMetadataResponse.from_orm(file_metadata)
    )

@router.get("/stats", response_model=ProcessingStatsResponse)
async def get_processing_stats(
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Get file processing statistics."""
    user_id = token_data["user_id"]
    
    # Get counts by status
    total_files = db.query(FileMetadata).filter(FileMetadata.uploaded_by == user_id).count()
    
    processing_files = db.query(FileMetadata).filter(
        and_(
            FileMetadata.uploaded_by == user_id,
            FileMetadata.status == FileStatus.PROCESSING
        )
    ).count()
    
    completed_files = db.query(FileMetadata).filter(
        and_(
            FileMetadata.uploaded_by == user_id,
            FileMetadata.status == FileStatus.COMPLETED
        )
    ).count()
    
    failed_files = db.query(FileMetadata).filter(
        and_(
            FileMetadata.uploaded_by == user_id,
            FileMetadata.status == FileStatus.FAILED
        )
    ).count()
    
    # Get categorized files count
    categorized_files = db.query(FileMetadata).filter(
        and_(
            FileMetadata.uploaded_by == user_id,
            FileMetadata.categories.isnot(None),
            FileMetadata.categories != []
        )
    ).count()
    
    # Get files with extracted text
    extracted_text_files = db.query(FileMetadata).filter(
        and_(
            FileMetadata.uploaded_by == user_id,
            FileMetadata.extracted_text.isnot(None),
            FileMetadata.extracted_text != ""
        )
    ).count()
    
    # Calculate storage used
    storage_used = db.query(func.sum(FileMetadata.file_size)).filter(
        FileMetadata.uploaded_by == user_id
    ).scalar() or 0
    
    return ProcessingStatsResponse(
        total_files=total_files,
        processing_files=processing_files,
        completed_files=completed_files,
        failed_files=failed_files,
        categorized_files=categorized_files,
        extracted_text_files=extracted_text_files,
        vectorized_files=completed_files,  # Simplified
        storage_used=storage_used,
        storage_limit=1024 * 1024 * 1024 * 10,  # 10GB limit
        processing_queue=processing_files,
        avg_processing_time=30.0  # Placeholder
    )

@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Get available file categories."""
    categories = []
    
    for i, category in enumerate(WMS_CATEGORIES):
        # Count files in this category for the user
        file_count = db.query(FileMetadata).filter(
            and_(
                FileMetadata.uploaded_by == token_data["user_id"],
                FileMetadata.categories.contains([category["name"]])
            )
        ).count()
        
        categories.append(CategoryResponse(
            id=i + 1,
            name=category["name"],
            description=category["description"],
            wms_category=category["name"],
            file_count=file_count
        ))
    
    return categories

@router.post("/search", response_model=FileSearchResponse)
async def search_files(
    request: FileSearchRequest,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Search files by content."""
    start_time = datetime.utcnow()
    
    # Build query
    query = db.query(FileMetadata).filter(
        FileMetadata.uploaded_by == token_data["user_id"]
    )
    
    # Text search
    if request.query:
        search_filter = or_(
            FileMetadata.original_name.ilike(f"%{request.query}%"),
            FileMetadata.extracted_text.ilike(f"%{request.query}%"),
            FileMetadata.summary.ilike(f"%{request.query}%"),
            FileMetadata.keywords.contains([request.query])
        )
        query = query.filter(search_filter)
    
    # Category filter
    if request.categories:
        category_filters = []
        for category in request.categories:
            category_filters.append(FileMetadata.categories.contains([category]))
        query = query.filter(or_(*category_filters))
    
    # File type filter
    if request.file_types:
        query = query.filter(FileMetadata.file_type.in_(request.file_types))
    
    # Apply limit
    files = query.order_by(desc(FileMetadata.uploaded_at)).limit(request.limit).all()
    
    # Calculate search time
    search_time = (datetime.utcnow() - start_time).total_seconds()
    
    return FileSearchResponse(
        files=[FileMetadataResponse.from_orm(file) for file in files],
        total_count=len(files),
        search_time=search_time,
        suggestions=[]  # Could implement search suggestions
    )

# Background task function
async def process_file_background(file_id: str):
    """Background task for file processing."""
    try:
        db = next(get_db())
        await file_processor.process_file(file_id, db)
    except Exception as e:
        logger.error(f"Background processing failed for file {file_id}: {e}")
    finally:
        db.close()