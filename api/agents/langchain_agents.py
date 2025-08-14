import os
import json
import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import logging

# LangChain imports
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain.agents.format_scratchpad import format_to_openai_functions
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.memory import ConversationBufferWindowMemory
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema.runnable import RunnablePassthrough
from langchain.tools import BaseTool, tool
from langchain.pydantic_v1 import BaseModel, Field

# LLM imports
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Local imports
from .models import WMSAgent, AgentConversation, AgentMessage, ALL_WMS_AGENTS
from ..files.models import FileMetadata
from ..database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_MODEL = os.getenv("DEFAULT_LLM_MODEL", "gpt-3.5-turbo")
VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", "./vector_store")

class WMSCallbackHandler(BaseCallbackHandler):
    """Custom callback handler for WMS agents to track performance and usage."""
    
    def __init__(self, agent_id: str, conversation_id: int):
        self.agent_id = agent_id
        self.conversation_id = conversation_id
        self.start_time = None
        self.total_tokens = 0
        self.tools_used = []
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs):
        """Called when LLM starts."""
        self.start_time = datetime.utcnow()
    
    def on_llm_end(self, response, **kwargs):
        """Called when LLM ends."""
        if hasattr(response, 'llm_output') and response.llm_output:
            token_usage = response.llm_output.get('token_usage', {})
            self.total_tokens += token_usage.get('total_tokens', 0)
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs):
        """Called when a tool starts."""
        tool_name = serialized.get('name', 'unknown_tool')
        self.tools_used.append(tool_name)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        end_time = datetime.utcnow()
        response_time = (end_time - self.start_time).total_seconds() if self.start_time else 0
        
        return {
            "response_time": response_time,
            "total_tokens": self.total_tokens,
            "tools_used": self.tools_used
        }

class FileSearchTool(BaseTool):
    """Tool for searching uploaded files by content."""
    
    name = "file_search"
    description = "Search through uploaded files by content, filename, or metadata"
    
    class InputSchema(BaseModel):
        query: str = Field(description="Search query to find relevant files")
        user_id: int = Field(description="User ID to filter files")
        limit: int = Field(default=5, description="Maximum number of files to return")
    
    def _run(self, query: str, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Search files synchronously."""
        try:
            db = next(get_db())
            
            # Search in file metadata, content, and filenames
            files = db.query(FileMetadata).filter(
                FileMetadata.uploaded_by == user_id
            ).filter(
                FileMetadata.original_name.ilike(f"%{query}%") |
                FileMetadata.extracted_text.ilike(f"%{query}%") |
                FileMetadata.summary.ilike(f"%{query}%")
            ).limit(limit).all()
            
            results = []
            for file in files:
                results.append({
                    "file_id": file.id,
                    "filename": file.original_name,
                    "summary": file.summary[:200] + "..." if file.summary and len(file.summary) > 200 else file.summary,
                    "categories": file.categories,
                    "uploaded_at": file.uploaded_at.isoformat()
                })
            
            return results
            
        except Exception as e:
            logger.error(f"File search error: {e}")
            return []
        finally:
            db.close()
    
    async def _arun(self, query: str, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Search files asynchronously."""
        return self._run(query, user_id, limit)

class DatabaseQueryTool(BaseTool):
    """Tool for querying database information (read-only)."""
    
    name = "database_query"
    description = "Execute read-only SQL queries on connected databases for WMS analysis"
    
    class InputSchema(BaseModel):
        query: str = Field(description="SQL query to execute (SELECT only)")
        connection_id: Optional[str] = Field(description="Database connection ID")
    
    def _run(self, query: str, connection_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute database query synchronously."""
        try:
            # Validate that query is read-only
            query_upper = query.upper().strip()
            if not query_upper.startswith('SELECT'):
                return {"error": "Only SELECT queries are allowed"}
            
            # Limit query to prevent large result sets
            if 'LIMIT' not in query_upper:
                query += ' LIMIT 100'
            
            # In production, would use actual database connection
            return {
                "columns": ["column1", "column2"],
                "data": [["sample", "data"]],
                "row_count": 1,
                "message": "Sample database query result"
            }
            
        except Exception as e:
            logger.error(f"Database query error: {e}")
            return {"error": str(e)}
    
    async def _arun(self, query: str, connection_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute database query asynchronously."""
        return self._run(query, connection_id)

class WMSKnowledgeTool(BaseTool):
    """Tool for accessing WMS knowledge base and best practices."""
    
    name = "wms_knowledge"
    description = "Access WMS knowledge base for best practices, procedures, and expert guidance"
    
    class InputSchema(BaseModel):
        topic: str = Field(description="WMS topic to get information about")
        category: Optional[str] = Field(description="Specific WMS category")
    
    def _run(self, topic: str, category: Optional[str] = None) -> Dict[str, Any]:
        """Get WMS knowledge synchronously."""
        try:
            # In production, would query actual knowledge base
            knowledge_base = {
                "wave_planning": "Wave planning involves grouping orders into waves based on priority, delivery requirements, and resource availability...",
                "allocation": "Inventory allocation determines which specific inventory should fulfill which orders based on FIFO, FEFO, or other strategies...",
                "picking": "Picking strategies include zone picking, batch picking, wave picking, and cluster picking, each optimized for different scenarios...",
                "cycle_counting": "Cycle counting is a continuous inventory auditing procedure where a subset of inventory is counted on a rotating schedule..."
            }
            
            topic_key = topic.lower().replace(" ", "_")
            info = knowledge_base.get(topic_key, f"General WMS information about {topic}")
            
            return {
                "topic": topic,
                "category": category,
                "information": info,
                "best_practices": [
                    "Follow standard operating procedures",
                    "Maintain data accuracy",
                    "Regular system monitoring",
                    "Continuous process improvement"
                ]
            }
            
        except Exception as e:
            logger.error(f"Knowledge base error: {e}")
            return {"error": str(e)}
    
    async def _arun(self, topic: str, category: Optional[str] = None) -> Dict[str, Any]:
        """Get WMS knowledge asynchronously."""
        return self._run(topic, category)

class WMSAgentManager:
    """Main class for managing WMS agents and conversations."""
    
    def __init__(self):
        self.agents: Dict[str, Any] = {}
        self.conversations: Dict[str, ConversationBufferWindowMemory] = {}
        self.vector_store = None
        self.embeddings = None
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model_name=DEFAULT_MODEL,
            temperature=0.7,
            openai_api_key=OPENAI_API_KEY
        ) if OPENAI_API_KEY else None
        
        # Initialize tools
        self.tools = [
            FileSearchTool(),
            DatabaseQueryTool(),
            WMSKnowledgeTool()
        ]
        
        # Load all WMS agents
        self.load_agents()
    
    def load_agents(self):
        """Load all WMS agents from configuration."""
        try:
            for category_key, category_data in ALL_WMS_AGENTS.items():
                for agent_def in category_data["agents"]:
                    agent_id = agent_def["agent_id"]
                    self.agents[agent_id] = self.create_agent(agent_def)
            
            logger.info(f"Loaded {len(self.agents)} WMS agents")
            
        except Exception as e:
            logger.error(f"Error loading agents: {e}")
    
    def create_agent(self, agent_def: Dict[str, Any]) -> Dict[str, Any]:
        """Create a LangChain agent from definition."""
        try:
            # Create agent prompt template
            prompt = ChatPromptTemplate.from_messages([
                ("system", agent_def["system_prompt"]),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad")
            ])
            
            # Create agent with tools
            if self.llm:
                agent = create_openai_functions_agent(
                    llm=self.llm,
                    tools=self.tools,
                    prompt=prompt
                )
                
                agent_executor = AgentExecutor(
                    agent=agent,
                    tools=self.tools,
                    verbose=True,
                    memory=ConversationBufferWindowMemory(
                        k=10,
                        memory_key="chat_history",
                        return_messages=True
                    )
                )
            else:
                # Fallback when no LLM is available
                agent_executor = None
            
            return {
                "definition": agent_def,
                "executor": agent_executor,
                "prompt": prompt,
                "created_at": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error creating agent {agent_def.get('agent_id')}: {e}")
            return {
                "definition": agent_def,
                "executor": None,
                "prompt": None,
                "created_at": datetime.utcnow(),
                "error": str(e)
            }
    
    async def chat_with_agent(
        self,
        agent_id: str,
        message: str,
        user_id: int,
        conversation_id: Optional[int] = None,
        context_files: List[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Send a message to a specific agent and get response."""
        try:
            if agent_id not in self.agents:
                raise ValueError(f"Agent {agent_id} not found")
            
            agent_data = self.agents[agent_id]
            agent_executor = agent_data["executor"]
            
            if not agent_executor:
                # Fallback response when LLM is not available
                return {
                    "response": f"I'm the {agent_data['definition']['name']}. I would help you with {agent_data['definition']['description']}, but I'm currently in simulation mode.",
                    "agent_id": agent_id,
                    "agent_name": agent_data['definition']['name'],
                    "confidence": 0.8,
                    "sources": [],
                    "tools_used": [],
                    "response_time": 0.5,
                    "token_count": 50
                }
            
            # Create callback handler for tracking
            callback_handler = WMSCallbackHandler(agent_id, conversation_id or 0)
            
            # Prepare context from files
            context = ""
            if context_files:
                context = await self.get_file_context(context_files, user_id)
            
            # Enhance input with context
            enhanced_input = message
            if context:
                enhanced_input = f"Context from uploaded files:\n{context}\n\nUser question: {message}"
            
            # Get response from agent
            try:
                response = await agent_executor.ainvoke(
                    {"input": enhanced_input},
                    callbacks=[callback_handler]
                )
                
                # Get metrics
                metrics = callback_handler.get_metrics()
                
                return {
                    "response": response["output"],
                    "agent_id": agent_id,
                    "agent_name": agent_data['definition']['name'],
                    "confidence": 0.9,  # Would calculate based on response
                    "sources": context_files or [],
                    "tools_used": metrics["tools_used"],
                    "response_time": metrics["response_time"],
                    "token_count": metrics["total_tokens"]
                }
                
            except Exception as e:
                logger.error(f"Agent execution error: {e}")
                return {
                    "response": f"I apologize, but I encountered an error while processing your request. As a {agent_data['definition']['name']}, I'm here to help with {agent_data['definition']['description']}. Please try rephrasing your question.",
                    "agent_id": agent_id,
                    "agent_name": agent_data['definition']['name'],
                    "confidence": 0.5,
                    "sources": [],
                    "tools_used": [],
                    "response_time": 1.0,
                    "token_count": 30,
                    "error": str(e)
                }
            
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise e
    
    async def get_file_context(self, file_ids: List[str], user_id: int) -> str:
        """Get context from uploaded files."""
        try:
            db = next(get_db())
            
            files = db.query(FileMetadata).filter(
                FileMetadata.id.in_(file_ids),
                FileMetadata.uploaded_by == user_id
            ).all()
            
            context_parts = []
            for file in files:
                file_context = f"File: {file.original_name}"
                if file.summary:
                    file_context += f"\nSummary: {file.summary}"
                if file.extracted_text:
                    # Limit context to avoid token limits
                    text_excerpt = file.extracted_text[:500] + "..." if len(file.extracted_text) > 500 else file.extracted_text
                    file_context += f"\nContent excerpt: {text_excerpt}"
                
                context_parts.append(file_context)
            
            return "\n\n---\n\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Error getting file context: {e}")
            return ""
        finally:
            db.close()
    
    def get_agent_by_category(self, category: str, agent_type: str = "functional") -> Optional[str]:
        """Get agent ID by category and type."""
        category_key = category.lower().replace(" ", "_").replace("-", "_")
        agent_id = f"{category_key}_{agent_type}"
        
        return agent_id if agent_id in self.agents else None
    
    def get_available_agents(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of available agents, optionally filtered by category."""
        agents = []
        
        for agent_id, agent_data in self.agents.items():
            agent_def = agent_data["definition"]
            
            if category and agent_def.get("category", "").lower() != category.lower():
                continue
            
            agents.append({
                "agent_id": agent_id,
                "name": agent_def["name"],
                "category": agent_def.get("category", ""),
                "type": agent_def["type"],
                "description": agent_def["description"],
                "capabilities": agent_def["capabilities"],
                "keywords": agent_def["keywords"]
            })
        
        return agents
    
    def suggest_agent(self, message: str, category: Optional[str] = None) -> str:
        """Suggest the most appropriate agent for a message."""
        message_lower = message.lower()
        
        # Score agents based on keyword matching
        agent_scores = {}
        
        for agent_id, agent_data in self.agents.items():
            agent_def = agent_data["definition"]
            
            # Filter by category if specified
            if category and agent_def.get("category", "").lower() != category.lower():
                continue
            
            score = 0
            
            # Check keywords
            for keyword in agent_def["keywords"]:
                if keyword.lower() in message_lower:
                    score += 2
            
            # Check capabilities
            for capability in agent_def["capabilities"]:
                if any(word in message_lower for word in capability.lower().split()):
                    score += 1
            
            agent_scores[agent_id] = score
        
        # Return agent with highest score, default to functional if no match
        if agent_scores:
            best_agent = max(agent_scores, key=agent_scores.get)
            if agent_scores[best_agent] > 0:
                return best_agent
        
        # Default fallback
        if category:
            return self.get_agent_by_category(category, "functional")
        
        return "wave_management_functional"  # Default agent
    
    async def cleanup(self):
        """Cleanup resources."""
        self.conversations.clear()
        if self.vector_store:
            # Clean up vector store resources
            pass

# Initialize global agent manager
agent_manager = WMSAgentManager()