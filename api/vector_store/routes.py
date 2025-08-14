from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user_token
from ..files.models import FileMetadata
from .weaviate_client import weaviate_manager

router = APIRouter(prefix="/vector-store", tags=["vector-store"])

# Pydantic Models
class VectorSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    categories: Optional[List[str]] = None
    file_types: Optional[List[str]] = None
    limit: int = Field(10, ge=1, le=50)

class VectorSearchResult(BaseModel):
    content: str
    file_id: str
    file_name: str
    chunk_index: int
    category: str
    file_type: str
    uploaded_at: str
    keywords: List[str]
    distance: float
    certainty: float

class VectorSearchResponse(BaseModel):
    results: List[VectorSearchResult]
    total_results: int
    search_time: float
    query: str

class KnowledgeEntry(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=10000)
    category: str
    subcategory: Optional[str] = None
    tags: List[str] = []
    source: str = "manual"

class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    category: Optional[str] = None
    limit: int = Field(5, ge=1, le=20)

class KnowledgeSearchResult(BaseModel):
    title: str
    content: str
    category: str
    subcategory: str
    tags: List[str]
    source: str
    distance: float
    certainty: float

class KnowledgeSearchResponse(BaseModel):
    results: List[KnowledgeSearchResult]
    total_results: int
    search_time: float

class VectorStoreStats(BaseModel):
    filecontent_count: int
    wmsknowledge_count: int
    conversationcontext_count: int
    is_healthy: bool
    schemas_created: bool

class FileVectorizationRequest(BaseModel):
    file_ids: List[str]
    force_reprocess: bool = False

class FileVectorizationResponse(BaseModel):
    success: bool
    processed_files: int
    failed_files: int
    total_chunks: int
    errors: List[str]

@router.get("/health")
async def health_check():
    """Check vector store health."""
    is_healthy = weaviate_manager.is_healthy()
    
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "weaviate_connected": is_healthy,
        "embeddings_available": weaviate_manager.embeddings is not None,
        "schemas_created": weaviate_manager.schemas_created
    }

@router.get("/stats", response_model=VectorStoreStats)
async def get_vector_store_stats(
    token_data: dict = Depends(get_current_user_token)
):
    """Get vector store statistics."""
    stats = await weaviate_manager.get_stats()
    
    return VectorStoreStats(
        filecontent_count=stats.get("filecontent_count", 0),
        wmsknowledge_count=stats.get("wmsknowledge_count", 0),
        conversationcontext_count=stats.get("conversationcontext_count", 0),
        is_healthy=weaviate_manager.is_healthy(),
        schemas_created=weaviate_manager.schemas_created
    )

@router.post("/search", response_model=VectorSearchResponse)
async def search_vector_content(
    request: VectorSearchRequest,
    token_data: dict = Depends(get_current_user_token)
):
    """Search content in vector store."""
    if not weaviate_manager.is_healthy():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector store is not available"
        )
    
    import time
    start_time = time.time()
    
    # Search with user filtering
    results = await weaviate_manager.search_content(
        query=request.query,
        user_id=token_data["user_id"],
        categories=request.categories,
        file_types=request.file_types,
        limit=request.limit
    )
    
    search_time = time.time() - start_time
    
    # Convert to response format
    search_results = [
        VectorSearchResult(**result) for result in results
    ]
    
    return VectorSearchResponse(
        results=search_results,
        total_results=len(search_results),
        search_time=search_time,
        query=request.query
    )

@router.post("/files/vectorize", response_model=FileVectorizationResponse)
async def vectorize_files(
    request: FileVectorizationRequest,
    background_tasks: BackgroundTasks,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Vectorize specific files."""
    if not weaviate_manager.is_healthy():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector store is not available"
        )
    
    # Verify user owns all files
    files = db.query(FileMetadata).filter(
        FileMetadata.id.in_(request.file_ids),
        FileMetadata.uploaded_by == token_data["user_id"]
    ).all()
    
    if len(files) != len(request.file_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Some files not found or access denied"
        )
    
    # Start vectorization in background
    background_tasks.add_task(
        vectorize_files_background,
        files,
        request.force_reprocess
    )
    
    return FileVectorizationResponse(
        success=True,
        processed_files=len(files),
        failed_files=0,
        total_chunks=0,  # Will be updated in background
        errors=[]
    )

@router.delete("/files/{file_id}")
async def delete_file_vectors(
    file_id: str,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Delete vectors for a specific file."""
    if not weaviate_manager.is_healthy():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector store is not available"
        )
    
    # Verify user owns the file
    file_metadata = db.query(FileMetadata).filter(
        FileMetadata.id == file_id,
        FileMetadata.uploaded_by == token_data["user_id"]
    ).first()
    
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Delete vectors
    success = await weaviate_manager.delete_file_content(file_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete vectors"
        )
    
    return {"message": "Vectors deleted successfully"}

@router.post("/knowledge", response_model=Dict[str, Any])
async def add_knowledge_entry(
    entry: KnowledgeEntry,
    token_data: dict = Depends(get_current_user_token)
):
    """Add WMS knowledge entry to vector store."""
    if not weaviate_manager.is_healthy():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector store is not available"
        )
    
    # Check if user has admin role for adding knowledge
    user_role = token_data.get("role", "user")
    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to add knowledge entries"
        )
    
    success = await weaviate_manager.add_wms_knowledge(
        title=entry.title,
        content=entry.content,
        category=entry.category,
        subcategory=entry.subcategory,
        tags=entry.tags,
        source=entry.source
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add knowledge entry"
        )
    
    return {
        "success": True,
        "message": "Knowledge entry added successfully"
    }

@router.post("/knowledge/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    request: KnowledgeSearchRequest,
    token_data: dict = Depends(get_current_user_token)
):
    """Search WMS knowledge base."""
    if not weaviate_manager.is_healthy():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector store is not available"
        )
    
    import time
    start_time = time.time()
    
    results = await weaviate_manager.search_knowledge(
        query=request.query,
        category=request.category,
        limit=request.limit
    )
    
    search_time = time.time() - start_time
    
    # Convert to response format
    knowledge_results = [
        KnowledgeSearchResult(**result) for result in results
    ]
    
    return KnowledgeSearchResponse(
        results=knowledge_results,
        total_results=len(knowledge_results),
        search_time=search_time
    )

@router.get("/similar-conversations")
async def get_similar_conversations(
    query: str,
    agent_id: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 3,
    token_data: dict = Depends(get_current_user_token)
):
    """Get similar conversations for context."""
    if not weaviate_manager.is_healthy():
        return {"results": [], "message": "Vector store not available"}
    
    results = await weaviate_manager.get_similar_conversations(
        query=query,
        agent_id=agent_id,
        category=category,
        limit=limit
    )
    
    return {
        "results": results,
        "total_results": len(results)
    }

@router.post("/rebuild-index")
async def rebuild_vector_index(
    background_tasks: BackgroundTasks,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Rebuild entire vector index (admin only)."""
    user_role = token_data.get("role", "user")
    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    if not weaviate_manager.is_healthy():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector store is not available"
        )
    
    # Get all files that have extracted text
    files = db.query(FileMetadata).filter(
        FileMetadata.extracted_text.isnot(None),
        FileMetadata.extracted_text != ""
    ).all()
    
    # Start rebuild in background
    background_tasks.add_task(rebuild_index_background, files)
    
    return {
        "message": f"Index rebuild started for {len(files)} files",
        "estimated_time_minutes": len(files) * 0.1  # Rough estimate
    }

@router.post("/test-embeddings")
async def test_embeddings(
    text: str = "This is a test query for WMS warehouse management",
    token_data: dict = Depends(get_current_user_token)
):
    """Test embeddings generation (admin only)."""
    user_role = token_data.get("role", "user")
    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    if not weaviate_manager.embeddings:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embeddings model not available"
        )
    
    try:
        embedding = weaviate_manager.embeddings.embed_query(text)
        
        return {
            "success": True,
            "text": text,
            "embedding_dimension": len(embedding),
            "embedding_sample": embedding[:5],  # First 5 dimensions
            "model_info": {
                "type": type(weaviate_manager.embeddings).__name__,
                "available": True
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "model_info": {
                "type": type(weaviate_manager.embeddings).__name__,
                "available": False
            }
        }

# Background task functions
async def vectorize_files_background(files: List[FileMetadata], force_reprocess: bool = False):
    """Background task to vectorize files."""
    import logging
    logger = logging.getLogger(__name__)
    
    processed = 0
    failed = 0
    total_chunks = 0
    
    for file_metadata in files:
        try:
            result = await weaviate_manager.add_file_content(file_metadata, force_reprocess)
            
            if result.get("success"):
                processed += 1
                total_chunks += result.get("chunks_added", 0)
                logger.info(f"Vectorized file {file_metadata.id}: {result.get('chunks_added', 0)} chunks")
            else:
                failed += 1
                logger.error(f"Failed to vectorize file {file_metadata.id}: {result.get('error')}")
                
        except Exception as e:
            failed += 1
            logger.error(f"Error vectorizing file {file_metadata.id}: {e}")
    
    logger.info(f"Vectorization complete: {processed} processed, {failed} failed, {total_chunks} total chunks")

async def rebuild_index_background(files: List[FileMetadata]):
    """Background task to rebuild entire vector index."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Starting index rebuild for {len(files)} files")
    
    # Clear existing data (in production, might want to keep backup)
    # This is a simplified approach
    
    # Vectorize all files
    await vectorize_files_background(files, force_reprocess=True)
    
    logger.info("Index rebuild completed")