"""
Content Processing API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import List, Optional
import tempfile
import os

from ...processing.text_pipeline import get_text_processor, MediaType
from ..models import (
    ContentUploadRequest, ContentProcessingResult, ContentSearchRequest,
    ContentSearchResult, APIResponse
)
from ..auth import get_current_user, UserContext

router = APIRouter()


@router.post("/upload", response_model=ContentProcessingResult)
async def upload_and_process_content(
    file: UploadFile = File(...),
    content_type: str = Form(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    user_context: UserContext = Depends(get_current_user)
):
    """Upload and process multi-modal content"""
    try:
        processor = get_text_processor()
        
        # Parse tags
        tag_list = tags.split(',') if tags else []
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        try:
            # Process content
            result = await processor.process_content(
                content=tmp_path,
                media_type=MediaType(content_type.lower()),
                user_context={
                    'user_id': user_context.user_id,
                    'user_role': user_context.role,
                    'description': description,
                    'tags': tag_list
                }
            )
            
            return ContentProcessingResult(
                content_id=result.content.content_id if result.content else "unknown",
                success=result.success,
                extracted_text=result.content.extracted_text if result.content else "",
                categories=result.wms_categories,
                entities=result.extracted_entities,
                confidence=result.confidence,
                processing_time=result.processing_time,
                warnings=result.warnings,
                errors=result.errors
            )
            
        finally:
            # Clean up temporary file
            os.unlink(tmp_path)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=List[ContentSearchResult])
async def search_content(
    request: ContentSearchRequest,
    user_context: UserContext = Depends(get_current_user)
):
    """Search processed content"""
    try:
        processor = get_text_processor()
        
        results = await processor.search_processed_content(
            query=request.query,
            categories=request.categories,
            limit=request.limit
        )
        
        formatted_results = []
        for result in results:
            if result.get('confidence', 0) >= request.min_confidence:
                formatted_results.append(ContentSearchResult(
                    content_id=result['content_id'],
                    content_type=result['content_type'],
                    extracted_text_preview=result['extracted_text'],
                    categories=result['categories'],
                    confidence=result['confidence'].get('overall', 0.0),
                    relevance_score=result['certainty'],
                    created_at=datetime.utcnow()  # Would be from storage
                ))
        
        return formatted_results
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))