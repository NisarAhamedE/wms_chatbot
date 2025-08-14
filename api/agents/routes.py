from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from ..database import get_db
from ..auth import get_current_user_token
from .models import (
    WMSAgent, AgentConversation, AgentMessage, AgentResponse,
    ConversationRequest, ConversationResponse, MessageRequest, MessageResponse,
    AgentConfigUpdate, AgentPerformanceStats, ConversationSummary,
    ALL_WMS_AGENTS, AgentStatus, ConversationStatus
)
from .langchain_agents import agent_manager

router = APIRouter(prefix="/agents", tags=["agents"])

@router.get("/", response_model=List[AgentResponse])
async def get_agents(
    category: Optional[str] = None,
    agent_type: Optional[str] = None,
    active_only: bool = True,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Get list of available WMS agents."""
    query = db.query(WMSAgent)
    
    if category:
        query = query.filter(WMSAgent.category == category)
    
    if agent_type:
        query = query.filter(WMSAgent.agent_type == agent_type)
    
    if active_only:
        query = query.filter(WMSAgent.status == AgentStatus.ACTIVE)
    
    agents = query.order_by(WMSAgent.category, WMSAgent.agent_type).all()
    
    # Add usage statistics
    response_agents = []
    for agent in agents:
        agent_data = AgentResponse.from_orm(agent)
        
        # Get last used timestamp
        last_message = db.query(AgentMessage).filter(
            AgentMessage.agent_id == agent.id
        ).order_by(desc(AgentMessage.created_at)).first()
        
        if last_message:
            agent_data.last_used = last_message.created_at
        
        response_agents.append(agent_data)
    
    return response_agents

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Get specific agent information."""
    agent = db.query(WMSAgent).filter(WMSAgent.agent_id == agent_id).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    return AgentResponse.from_orm(agent)

@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    request: ConversationRequest,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Create a new conversation with an agent."""
    # Verify agent exists
    agent = db.query(WMSAgent).filter(WMSAgent.agent_id == request.agent_id).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # Generate session ID
    import uuid
    session_id = str(uuid.uuid4())
    
    # Create conversation
    conversation = AgentConversation(
        session_id=session_id,
        user_id=token_data["user_id"],
        agent_id=agent.id,
        title=request.title or f"Chat with {agent.name}",
        context_files=request.context_files
    )
    
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    # Update agent statistics
    agent.total_conversations += 1
    db.commit()
    
    return ConversationResponse.from_orm(conversation)

@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(
    limit: int = 50,
    offset: int = 0,
    agent_id: Optional[str] = None,
    status: Optional[str] = None,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Get user's conversations."""
    query = db.query(AgentConversation).filter(
        AgentConversation.user_id == token_data["user_id"]
    )
    
    if agent_id:
        agent = db.query(WMSAgent).filter(WMSAgent.agent_id == agent_id).first()
        if agent:
            query = query.filter(AgentConversation.agent_id == agent.id)
    
    if status:
        query = query.filter(AgentConversation.status == status)
    
    conversations = query.order_by(
        desc(AgentConversation.last_message_at),
        desc(AgentConversation.started_at)
    ).offset(offset).limit(limit).all()
    
    return [ConversationResponse.from_orm(conv) for conv in conversations]

@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Get specific conversation."""
    conversation = db.query(AgentConversation).filter(
        and_(
            AgentConversation.id == conversation_id,
            AgentConversation.user_id == token_data["user_id"]
        )
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    return ConversationResponse.from_orm(conversation)

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Delete a conversation."""
    conversation = db.query(AgentConversation).filter(
        and_(
            AgentConversation.id == conversation_id,
            AgentConversation.user_id == token_data["user_id"]
        )
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Delete all messages in conversation
    db.query(AgentMessage).filter(
        AgentMessage.conversation_id == conversation_id
    ).delete()
    
    # Delete conversation
    db.delete(conversation)
    db.commit()
    
    return {"message": "Conversation deleted successfully"}

@router.post("/messages", response_model=MessageResponse)
async def send_message(
    request: MessageRequest,
    background_tasks: BackgroundTasks,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Send a message to an agent."""
    # Get or create conversation
    conversation = None
    
    if request.conversation_id:
        conversation = db.query(AgentConversation).filter(
            and_(
                AgentConversation.id == request.conversation_id,
                AgentConversation.user_id == token_data["user_id"]
            )
        ).first()
    
    elif request.session_id:
        conversation = db.query(AgentConversation).filter(
            and_(
                AgentConversation.session_id == request.session_id,
                AgentConversation.user_id == token_data["user_id"]
            )
        ).first()
    
    if not conversation:
        # Create new conversation
        agent = db.query(WMSAgent).filter(WMSAgent.agent_id == request.agent_id).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        import uuid
        conversation = AgentConversation(
            session_id=str(uuid.uuid4()),
            user_id=token_data["user_id"],
            agent_id=agent.id,
            title=f"Chat with {agent.name}",
            context_files=request.context_files
        )
        
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    # Create user message
    user_message = AgentMessage(
        conversation_id=conversation.id,
        agent_id=conversation.agent_id,
        role="user",
        content=request.content
    )
    
    db.add(user_message)
    db.commit()
    db.refresh(user_message)
    
    # Update conversation statistics
    conversation.message_count += 1
    conversation.last_message_at = datetime.utcnow()
    db.commit()
    
    # Process message with agent in background
    background_tasks.add_task(
        process_agent_message,
        request.agent_id,
        request.content,
        token_data["user_id"],
        conversation.id,
        request.context_files or []
    )
    
    return MessageResponse.from_orm(user_message)

@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: int,
    limit: int = 100,
    offset: int = 0,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Get messages from a conversation."""
    # Verify conversation belongs to user
    conversation = db.query(AgentConversation).filter(
        and_(
            AgentConversation.id == conversation_id,
            AgentConversation.user_id == token_data["user_id"]
        )
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    messages = db.query(AgentMessage).filter(
        AgentMessage.conversation_id == conversation_id
    ).order_by(AgentMessage.created_at).offset(offset).limit(limit).all()
    
    return [MessageResponse.from_orm(msg) for msg in messages]

@router.put("/messages/{message_id}/feedback")
async def update_message_feedback(
    message_id: int,
    rating: Optional[int] = None,
    feedback: Optional[str] = None,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Update message feedback (rating and comments)."""
    # Get message and verify ownership
    message = db.query(AgentMessage).join(AgentConversation).filter(
        and_(
            AgentMessage.id == message_id,
            AgentConversation.user_id == token_data["user_id"]
        )
    ).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Update feedback
    if rating is not None:
        if rating < 1 or rating > 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rating must be between 1 and 5"
            )
        message.user_rating = rating
    
    if feedback is not None:
        message.user_feedback = feedback
    
    db.commit()
    
    return {"message": "Feedback updated successfully"}

@router.get("/suggest", response_model=Dict[str, Any])
async def suggest_agent(
    message: str,
    category: Optional[str] = None,
    token_data: dict = Depends(get_current_user_token)
):
    """Suggest the best agent for a given message."""
    suggested_agent_id = agent_manager.suggest_agent(message, category)
    
    # Get agent details from memory
    available_agents = agent_manager.get_available_agents(category)
    suggested_agent = next(
        (agent for agent in available_agents if agent["agent_id"] == suggested_agent_id),
        None
    )
    
    return {
        "suggested_agent_id": suggested_agent_id,
        "suggested_agent": suggested_agent,
        "confidence": 0.8,  # Would calculate based on keyword matching
        "reasoning": f"Based on your message content, this agent specializes in the relevant area."
    }

@router.get("/categories", response_model=List[Dict[str, Any]])
async def get_agent_categories(
    token_data: dict = Depends(get_current_user_token)
):
    """Get all agent categories with their agents."""
    categories = []
    
    for category_key, category_data in ALL_WMS_AGENTS.items():
        agents = agent_manager.get_available_agents(category_data["category"])
        
        categories.append({
            "category": category_data["category"],
            "category_key": category_key,
            "description": f"Agents specialized in {category_data['category'].lower()}",
            "agent_count": len(agents),
            "agents": agents
        })
    
    return categories

@router.get("/performance/stats", response_model=List[AgentPerformanceStats])
async def get_agent_performance(
    days: int = 30,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Get agent performance statistics."""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get agent statistics
    agent_stats = db.query(
        WMSAgent.agent_id,
        WMSAgent.name,
        WMSAgent.total_conversations,
        WMSAgent.total_messages,
        WMSAgent.avg_response_time,
        WMSAgent.satisfaction_score
    ).all()
    
    performance_stats = []
    
    for stat in agent_stats:
        # Get usage trend (simplified)
        trend_data = [
            {"date": (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d"), "usage": max(0, 10 - i)}
            for i in range(7)
        ]
        
        performance_stats.append(AgentPerformanceStats(
            agent_id=stat.agent_id,
            agent_name=stat.name,
            total_conversations=stat.total_conversations,
            total_messages=stat.total_messages,
            avg_response_time=stat.avg_response_time,
            satisfaction_score=stat.satisfaction_score,
            usage_trend=trend_data,
            top_keywords=["warehouse", "management", "optimization"],  # Would calculate from actual data
            error_rate=0.05  # Would calculate from actual data
        ))
    
    return performance_stats

@router.put("/agents/{agent_id}/config", response_model=AgentResponse)
async def update_agent_config(
    agent_id: str,
    config: AgentConfigUpdate,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Update agent configuration (admin only)."""
    # In production, would check admin permissions
    user_role = token_data.get("role", "user")
    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    agent = db.query(WMSAgent).filter(WMSAgent.agent_id == agent_id).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # Update configuration
    if config.temperature is not None:
        agent.temperature = config.temperature
    
    if config.max_tokens is not None:
        agent.max_tokens = config.max_tokens
    
    if config.system_prompt is not None:
        agent.system_prompt = config.system_prompt
    
    if config.capabilities is not None:
        agent.capabilities = config.capabilities
    
    if config.tool_access is not None:
        agent.tool_access = config.tool_access
    
    if config.status is not None:
        agent.status = config.status
    
    agent.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(agent)
    
    return AgentResponse.from_orm(agent)

# Background task function
async def process_agent_message(
    agent_id: str,
    message: str,
    user_id: int,
    conversation_id: int,
    context_files: List[str]
):
    """Process message with agent and store response."""
    try:
        # Get agent response
        response_data = await agent_manager.chat_with_agent(
            agent_id=agent_id,
            message=message,
            user_id=user_id,
            conversation_id=conversation_id,
            context_files=context_files
        )
        
        # Store agent response in database
        db = next(get_db())
        
        agent = db.query(WMSAgent).filter(WMSAgent.agent_id == agent_id).first()
        
        if agent:
            agent_message = AgentMessage(
                conversation_id=conversation_id,
                agent_id=agent.id,
                role="assistant",
                content=response_data["response"],
                token_count=response_data.get("token_count"),
                response_time=response_data.get("response_time"),
                confidence_score=response_data.get("confidence"),
                context_used=context_files,
                sources=response_data.get("sources", []),
                tools_used=response_data.get("tools_used", [])
            )
            
            db.add(agent_message)
            
            # Update agent statistics
            agent.total_messages += 1
            if response_data.get("response_time"):
                # Update average response time
                total_time = agent.avg_response_time * (agent.total_messages - 1)
                agent.avg_response_time = (total_time + response_data["response_time"]) / agent.total_messages
            
            # Update conversation
            conversation = db.query(AgentConversation).filter(
                AgentConversation.id == conversation_id
            ).first()
            
            if conversation:
                conversation.message_count += 1
                conversation.last_message_at = datetime.utcnow()
                if response_data.get("token_count"):
                    conversation.total_tokens += response_data["token_count"]
            
            db.commit()
        
    except Exception as e:
        logger.error(f"Error processing agent message: {e}")
    finally:
        db.close()