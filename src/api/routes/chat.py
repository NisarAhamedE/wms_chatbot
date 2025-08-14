"""
Chat API Routes
Handles conversational interactions with WMS agents.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Dict, List, Optional, Any
import asyncio
import json
import uuid
from datetime import datetime

from ...core.logging import LoggerMixin
from ...agents.base import WMSAgentOrchestrator, WMSContext
from ...core.llm_constraints import validate_llm_response
from ..models import (
    ChatRequest, ChatResponse, ChatHistory, ChatMessage,
    APIResponse, StreamingChatChunk
)
from ..auth import get_current_user, UserContext


class ChatService(LoggerMixin):
    """Chat service for managing conversations"""
    
    def __init__(self):
        super().__init__()
        self.orchestrator = WMSAgentOrchestrator()
        self.active_sessions = {}  # In-memory storage for demo
    
    async def process_chat_message(self, request: ChatRequest, 
                                 user_context: UserContext) -> ChatResponse:
        """Process a chat message through the agent system"""
        start_time = datetime.utcnow()
        
        try:
            # Create or get session
            session_id = request.session_id or str(uuid.uuid4())
            
            # Create WMS context
            wms_context = WMSContext(
                user_id=request.user_id,
                user_role=request.user_role.value,
                session_id=session_id
            )
            
            # Add message to conversation history
            wms_context.add_message("user", request.message, request.context)
            
            # Route to appropriate agent
            agent_response = await self.orchestrator.route_query(
                query=request.message,
                context=wms_context,
                preferred_category=request.preferred_category,
                preferred_sub_category=request.preferred_sub_category
            )
            
            # Validate response with constraint system
            validation_context = {
                'user_role': request.user_role.value,
                'query_result': agent_response,
                'session_id': session_id
            }
            
            validation_result = await validate_llm_response(
                response=agent_response.get('response', ''),
                context=validation_context
            )
            
            # Handle validation failures
            if not validation_result['is_valid']:
                self.log_warning("Response failed validation", 
                               violations=[v.description for v in validation_result['violations']])
                
                # Use fallback response or corrections
                if validation_result.get('corrected_response'):
                    agent_response['response'] = validation_result['corrected_response']
                else:
                    agent_response['response'] = "I apologize, but I cannot provide that information. Please rephrase your question."
            
            # Add response to conversation history
            wms_context.add_message("assistant", agent_response['response'])
            
            # Store session
            self.active_sessions[session_id] = wms_context
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Extract performance and quality information
            data_quality = agent_response.get('metadata', {}).get('result_quality')
            performance_info = agent_response.get('metadata', {}).get('performance_analysis')
            
            return ChatResponse(
                response=agent_response['response'],
                agent_info={
                    'agent_id': agent_response.get('agent_id', 'unknown'),
                    'category': agent_response.get('category', 'unknown'),
                    'sub_category': agent_response.get('sub_category', 'unknown')
                },
                processing_time=processing_time,
                session_id=session_id,
                confidence=agent_response.get('confidence'),
                suggestions=agent_response.get('suggestions', []),
                data_quality=data_quality,
                performance_info=performance_info
            )
            
        except Exception as e:
            self.log_error(f"Chat processing failed: {e}")
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return ChatResponse(
                response="I apologize, but I encountered an error processing your request. Please try again.",
                agent_info={'agent_id': 'error', 'category': 'system', 'sub_category': 'error'},
                processing_time=processing_time,
                session_id=request.session_id or str(uuid.uuid4()),
                confidence=0.0
            )
    
    async def get_chat_history(self, session_id: str, user_id: str) -> Optional[ChatHistory]:
        """Get chat history for a session"""
        if session_id not in self.active_sessions:
            return None
        
        context = self.active_sessions[session_id]
        
        if context.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied to session")
        
        messages = []
        for msg in context.conversation_history:
            messages.append(ChatMessage(
                role=msg['role'],
                content=msg['content'],
                timestamp=datetime.fromtimestamp(msg['timestamp']),
                metadata=msg.get('metadata')
            ))
        
        return ChatHistory(
            session_id=session_id,
            messages=messages,
            created_at=datetime.fromtimestamp(context.created_at),
            updated_at=datetime.utcnow(),
            user_id=user_id
        )
    
    async def stream_chat_response(self, request: ChatRequest, 
                                 user_context: UserContext):
        """Stream chat response in chunks"""
        try:
            # Process message normally first
            response = await self.process_chat_message(request, user_context)
            
            # Split response into chunks for streaming
            response_text = response.response
            chunk_size = 50  # Characters per chunk
            
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i + chunk_size]
                is_final = (i + chunk_size) >= len(response_text)
                
                chunk_data = StreamingChatChunk(
                    chunk_id=f"{response.session_id}_{i // chunk_size}",
                    content=chunk,
                    is_final=is_final,
                    metadata={
                        'agent_info': response.agent_info,
                        'processing_time': response.processing_time
                    } if is_final else None
                )
                
                yield f"data: {chunk_data.json()}\n\n"
                await asyncio.sleep(0.05)  # Small delay for realistic streaming
        
        except Exception as e:
            error_chunk = StreamingChatChunk(
                chunk_id="error",
                content=f"Error: {str(e)}",
                is_final=True
            )
            yield f"data: {error_chunk.json()}\n\n"


# Create router and service
router = APIRouter()
chat_service = ChatService()


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    user_context: UserContext = Depends(get_current_user)
):
    """Send a message to the WMS chatbot"""
    try:
        response = await chat_service.process_chat_message(request, user_context)
        return response
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream")
async def stream_message(
    message: str,
    user_id: str,
    user_role: str = "end_user",
    session_id: Optional[str] = None,
    user_context: UserContext = Depends(get_current_user)
):
    """Stream a chat response"""
    try:
        request = ChatRequest(
            message=message,
            user_id=user_id,
            user_role=user_role,
            session_id=session_id
        )
        
        return StreamingResponse(
            chat_service.stream_chat_response(request, user_context),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{session_id}", response_model=ChatHistory)
async def get_chat_history(
    session_id: str,
    user_context: UserContext = Depends(get_current_user)
):
    """Get chat history for a session"""
    try:
        history = await chat_service.get_chat_history(session_id, user_context.user_id)
        
        if not history:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return history
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/{session_id}")
async def clear_chat_history(
    session_id: str,
    user_context: UserContext = Depends(get_current_user)
):
    """Clear chat history for a session"""
    try:
        if session_id in chat_service.active_sessions:
            context = chat_service.active_sessions[session_id]
            
            if context.user_id != user_context.user_id:
                raise HTTPException(status_code=403, detail="Access denied to session")
            
            del chat_service.active_sessions[session_id]
        
        return APIResponse(
            success=True,
            message=f"Chat history cleared for session {session_id}"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=List[Dict[str, Any]])
async def get_user_sessions(
    user_context: UserContext = Depends(get_current_user)
):
    """Get all active sessions for the user"""
    try:
        user_sessions = []
        
        for session_id, context in chat_service.active_sessions.items():
            if context.user_id == user_context.user_id:
                last_message = ""
                if context.conversation_history:
                    last_message = context.conversation_history[-1]['content'][:100]
                
                user_sessions.append({
                    'session_id': session_id,
                    'created_at': datetime.fromtimestamp(context.created_at),
                    'message_count': len(context.conversation_history),
                    'last_message_preview': last_message
                })
        
        return user_sessions
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents", response_model=Dict[str, Any])
async def get_available_agents():
    """Get information about available agents"""
    try:
        agents_info = {
            'total_agents': len(chat_service.orchestrator.agent_registry),
            'categories': {},
            'agent_list': []
        }
        
        # Group agents by category
        for agent_id, agent_path in chat_service.orchestrator.agent_registry.items():
            category, sub_category = agent_id.split('.', 1)
            
            if category not in agents_info['categories']:
                agents_info['categories'][category] = []
            
            agents_info['categories'][category].append(sub_category)
            
            agents_info['agent_list'].append({
                'agent_id': agent_id,
                'category': category,
                'sub_category': sub_category,
                'description': f"{category.replace('_', ' ').title()} - {sub_category.replace('_', ' ').title()}"
            })
        
        return agents_info
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback")
async def submit_feedback(
    session_id: str,
    message_index: int,
    rating: int,
    feedback_text: Optional[str] = None,
    user_context: UserContext = Depends(get_current_user)
):
    """Submit feedback for a chat interaction"""
    try:
        if session_id not in chat_service.active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        context = chat_service.active_sessions[session_id]
        
        if context.user_id != user_context.user_id:
            raise HTTPException(status_code=403, detail="Access denied to session")
        
        if rating < 1 or rating > 5:
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        
        # Store feedback (in production, save to database)
        feedback_data = {
            'session_id': session_id,
            'message_index': message_index,
            'rating': rating,
            'feedback_text': feedback_text,
            'user_id': user_context.user_id,
            'timestamp': datetime.utcnow()
        }
        
        chat_service.log_info(
            "User feedback received",
            feedback_data=feedback_data
        )
        
        return APIResponse(
            success=True,
            message="Feedback submitted successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))