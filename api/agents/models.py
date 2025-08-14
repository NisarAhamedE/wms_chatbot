from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Text, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

Base = declarative_base()

# Enums
class AgentType(str, Enum):
    FUNCTIONAL = "functional"
    TECHNICAL = "technical"
    CONFIGURATION = "configuration"
    RELATIONSHIPS = "relationships"
    NOTES_REMARKS = "notes_remarks"

class AgentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"

class ConversationStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"

# Database Models
class WMSAgent(Base):
    __tablename__ = "wms_agents"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    agent_id = Column(String(50), unique=True, index=True, nullable=False)  # e.g., "wave_functional"
    category = Column(String(50), nullable=False)  # WMS category
    agent_type = Column(String(20), nullable=False)  # AgentType
    
    # Agent configuration
    description = Column(Text, nullable=False)
    system_prompt = Column(Text, nullable=False)
    capabilities = Column(JSON)  # List of capabilities
    keywords = Column(JSON)  # Keywords this agent responds to
    
    # LLM Configuration
    model_name = Column(String(100), default="gpt-3.5-turbo")
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=1000)
    
    # Agent behavior
    context_window = Column(Integer, default=4000)
    memory_enabled = Column(Boolean, default=True)
    tool_access = Column(JSON)  # Available tools/functions
    
    # Metadata
    version = Column(String(20), default="1.0")
    status = Column(String(20), default=AgentStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Usage statistics
    total_conversations = Column(Integer, default=0)
    total_messages = Column(Integer, default=0)
    avg_response_time = Column(Float, default=0.0)
    satisfaction_score = Column(Float, default=0.0)
    
    # Relationships
    conversations = relationship("AgentConversation", back_populates="agent")
    messages = relationship("AgentMessage", back_populates="agent")

class AgentConversation(Base):
    __tablename__ = "agent_conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("wms_agents.id"), nullable=False)
    
    # Conversation metadata
    title = Column(String(200))
    status = Column(String(20), default=ConversationStatus.ACTIVE)
    context_files = Column(JSON)  # Associated file IDs
    
    # Statistics
    message_count = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    duration_seconds = Column(Integer, default=0)
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    last_message_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    
    # Relationships
    agent = relationship("WMSAgent", back_populates="conversations")
    messages = relationship("AgentMessage", back_populates="conversation")

class AgentMessage(Base):
    __tablename__ = "agent_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("agent_conversations.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("wms_agents.id"), nullable=False)
    
    # Message content
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    
    # Message metadata
    token_count = Column(Integer)
    response_time = Column(Float)  # in seconds
    confidence_score = Column(Float)
    
    # Context and sources
    context_used = Column(JSON)  # Context that was used
    sources = Column(JSON)  # Source files/documents
    tools_used = Column(JSON)  # Tools that were called
    
    # User feedback
    user_rating = Column(Integer)  # 1-5 rating
    user_feedback = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    conversation = relationship("AgentConversation", back_populates="messages")
    agent = relationship("WMSAgent", back_populates="messages")

class AgentTool(Base):
    __tablename__ = "agent_tools"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    tool_id = Column(String(50), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=False)
    
    # Tool configuration
    function_schema = Column(JSON, nullable=False)
    allowed_agents = Column(JSON)  # Agent IDs that can use this tool
    
    # Tool metadata
    category = Column(String(50))
    version = Column(String(20), default="1.0")
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Pydantic Models
class AgentResponse(BaseModel):
    id: int
    name: str
    agent_id: str
    category: str
    agent_type: str
    description: str
    capabilities: List[str]
    status: str
    total_conversations: int = 0
    avg_response_time: float = 0.0
    satisfaction_score: float = 0.0
    last_used: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ConversationRequest(BaseModel):
    title: Optional[str] = None
    agent_id: str
    context_files: List[str] = []

class ConversationResponse(BaseModel):
    id: int
    session_id: str
    agent_id: int
    title: Optional[str]
    status: str
    message_count: int
    started_at: datetime
    last_message_at: Optional[datetime]
    context_files: List[str] = []
    
    class Config:
        from_attributes = True

class MessageRequest(BaseModel):
    content: str
    conversation_id: Optional[int] = None
    session_id: Optional[str] = None
    agent_id: str
    context_files: List[str] = []
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    token_count: Optional[int]
    response_time: Optional[float]
    confidence_score: Optional[float]
    context_used: List[str] = []
    sources: List[str] = []
    tools_used: List[str] = []
    created_at: datetime
    
    class Config:
        from_attributes = True

class AgentConfigUpdate(BaseModel):
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=4000)
    system_prompt: Optional[str] = None
    capabilities: Optional[List[str]] = None
    tool_access: Optional[List[str]] = None
    status: Optional[AgentStatus] = None

class AgentPerformanceStats(BaseModel):
    agent_id: str
    agent_name: str
    total_conversations: int
    total_messages: int
    avg_response_time: float
    satisfaction_score: float
    usage_trend: List[Dict[str, Any]]
    top_keywords: List[str]
    error_rate: float

class ConversationSummary(BaseModel):
    session_id: str
    title: str
    agent_name: str
    category: str
    message_count: int
    duration_minutes: int
    satisfaction: Optional[float]
    key_topics: List[str]
    outcome: Optional[str]

# WMS Agent Definitions
WMS_AGENT_DEFINITIONS = {
    "wave_management": {
        "category": "Wave Management",
        "agents": [
            {
                "type": "functional",
                "name": "Wave Planning Specialist",
                "description": "Expert in wave planning strategies, release optimization, and workload balancing",
                "capabilities": [
                    "Wave planning and optimization",
                    "Release strategy recommendations", 
                    "Workload balancing analysis",
                    "Resource allocation planning",
                    "Performance metrics analysis"
                ],
                "keywords": ["wave", "planning", "release", "workload", "optimization", "strategy"],
                "system_prompt": """You are a Wave Management Functional Specialist with deep expertise in warehouse wave planning and optimization. You help users understand and implement effective wave management strategies, optimize release timing, and balance workloads across warehouse operations. Focus on practical, actionable advice based on industry best practices."""
            },
            {
                "type": "technical",
                "name": "Wave Systems Architect",
                "description": "Technical expert in wave management systems, algorithms, and integrations",
                "capabilities": [
                    "System architecture design",
                    "Algorithm optimization",
                    "Integration planning",
                    "Performance tuning",
                    "Technical troubleshooting"
                ],
                "keywords": ["algorithm", "system", "integration", "performance", "technical", "architecture"],
                "system_prompt": """You are a Wave Management Technical Specialist focused on the technical aspects of wave management systems. You provide expertise on algorithms, system architecture, integrations, and technical optimization of wave processing capabilities."""
            },
            {
                "type": "configuration",
                "name": "Wave Configuration Expert",
                "description": "Specialist in wave management system configuration and parameter optimization",
                "capabilities": [
                    "System configuration",
                    "Parameter optimization",
                    "Rule setup and management",
                    "Configuration validation",
                    "Best practice implementation"
                ],
                "keywords": ["configuration", "parameters", "rules", "setup", "optimization"],
                "system_prompt": """You are a Wave Management Configuration Specialist who helps users configure wave management systems, optimize parameters, and implement best practice configurations for optimal wave processing performance."""
            },
            {
                "type": "relationships",
                "name": "Wave Integration Coordinator",
                "description": "Expert in wave management relationships with other WMS modules and external systems",
                "capabilities": [
                    "Module integration analysis",
                    "Cross-functional coordination",
                    "Dependency management",
                    "Process flow optimization",
                    "System relationship mapping"
                ],
                "keywords": ["integration", "coordination", "dependencies", "relationships", "modules"],
                "system_prompt": """You are a Wave Management Integration Specialist focused on how wave management integrates with other WMS modules and external systems. You help optimize cross-functional processes and manage system dependencies."""
            },
            {
                "type": "notes_remarks",
                "name": "Wave Documentation Specialist",
                "description": "Specialist in wave management documentation, training, and knowledge management",
                "capabilities": [
                    "Documentation creation",
                    "Training material development",
                    "Best practice documentation",
                    "Process documentation",
                    "Knowledge base management"
                ],
                "keywords": ["documentation", "training", "notes", "procedures", "knowledge"],
                "system_prompt": """You are a Wave Management Documentation Specialist who helps create comprehensive documentation, training materials, and knowledge bases for wave management processes and procedures."""
            }
        ]
    },
    "allocation": {
        "category": "Allocation",
        "agents": [
            {
                "type": "functional",
                "name": "Inventory Allocation Strategist",
                "description": "Expert in inventory allocation strategies, demand planning, and stock optimization",
                "capabilities": [
                    "Allocation strategy development",
                    "Demand forecasting analysis",
                    "Stock optimization",
                    "Priority management",
                    "Resource allocation planning"
                ],
                "keywords": ["allocation", "inventory", "demand", "stock", "optimization", "priority"],
                "system_prompt": """You are an Allocation Functional Specialist with expertise in inventory allocation strategies and demand planning. You help optimize stock allocation, manage priorities, and develop effective allocation strategies for efficient warehouse operations."""
            },
            {
                "type": "technical",
                "name": "Allocation Systems Engineer",
                "description": "Technical expert in allocation algorithms, system design, and optimization",
                "capabilities": [
                    "Allocation algorithm design",
                    "System optimization",
                    "Performance analysis",
                    "Technical implementation",
                    "Integration architecture"
                ],
                "keywords": ["algorithm", "technical", "system", "optimization", "performance"],
                "system_prompt": """You are an Allocation Technical Specialist focused on the technical implementation of allocation systems. You provide expertise on algorithms, system design, and technical optimization of allocation processes."""
            },
            {
                "type": "configuration",
                "name": "Allocation Rules Manager",
                "description": "Specialist in allocation rules configuration and parameter management",
                "capabilities": [
                    "Rules configuration",
                    "Parameter management",
                    "Priority setup",
                    "Constraint management",
                    "Configuration optimization"
                ],
                "keywords": ["rules", "configuration", "parameters", "constraints", "setup"],
                "system_prompt": """You are an Allocation Configuration Specialist who helps configure allocation rules, manage parameters, and optimize allocation system settings for maximum efficiency."""
            },
            {
                "type": "relationships",
                "name": "Allocation Integration Manager",
                "description": "Expert in allocation relationships with procurement, sales, and other systems",
                "capabilities": [
                    "Cross-system integration",
                    "Process coordination",
                    "Data flow management",
                    "Dependency analysis",
                    "Integration optimization"
                ],
                "keywords": ["integration", "procurement", "sales", "coordination", "dependencies"],
                "system_prompt": """You are an Allocation Integration Specialist focused on how allocation processes integrate with procurement, sales, and other business systems. You optimize cross-functional workflows and manage system dependencies."""
            },
            {
                "type": "notes_remarks",
                "name": "Allocation Process Documenter",
                "description": "Specialist in allocation process documentation and procedure management",
                "capabilities": [
                    "Process documentation",
                    "Procedure development",
                    "Training material creation",
                    "Best practice capture",
                    "Knowledge management"
                ],
                "keywords": ["documentation", "procedures", "training", "processes", "knowledge"],
                "system_prompt": """You are an Allocation Documentation Specialist who creates comprehensive documentation for allocation processes, develops training materials, and maintains knowledge bases for allocation procedures."""
            }
        ]
    }
    # Additional categories would be defined similarly...
}

# Generate all 80 agents (16 categories × 5 agents each)
def generate_all_wms_agents():
    """Generate complete WMS agent definitions for all 16 categories."""
    
    categories = [
        "Wave Management", "Allocation", "Locating and Putaway", "Picking",
        "Cycle Counting", "Replenishment", "Labor Management", "Yard Management",
        "Slotting", "Cross-Docking", "Returns Management", "Inventory Management",
        "Order Management", "Task Management", "Reports and Analytics", "Other"
    ]
    
    agent_types = [
        {"type": "functional", "suffix": "Specialist"},
        {"type": "technical", "suffix": "Engineer"},
        {"type": "configuration", "suffix": "Manager"},
        {"type": "relationships", "suffix": "Coordinator"},
        {"type": "notes_remarks", "suffix": "Documenter"}
    ]
    
    all_agents = {}
    
    for category in categories:
        category_key = category.lower().replace(" ", "_").replace("-", "_")
        all_agents[category_key] = {
            "category": category,
            "agents": []
        }
        
        for agent_type in agent_types:
            agent_name = f"{category} {agent_type['suffix']}"
            agent_id = f"{category_key}_{agent_type['type']}"
            
            agent_def = {
                "type": agent_type["type"],
                "name": agent_name,
                "agent_id": agent_id,
                "description": f"Expert in {category.lower()} {agent_type['type']} aspects",
                "capabilities": [
                    f"{category} expertise",
                    f"{agent_type['type'].title()} knowledge",
                    "Best practice guidance",
                    "Problem solving",
                    "Process optimization"
                ],
                "keywords": [category.lower(), agent_type["type"], "wms", "warehouse"],
                "system_prompt": f"""You are a {category} {agent_type['suffix']} with deep expertise in warehouse management systems. You specialize in the {agent_type['type']} aspects of {category.lower()} and help users optimize their warehouse operations through expert guidance and best practices."""
            }
            
            all_agents[category_key]["agents"].append(agent_def)
    
    return all_agents

# Initialize all WMS agents
ALL_WMS_AGENTS = generate_all_wms_agents()