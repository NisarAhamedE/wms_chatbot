"""
Base classes for WMS agents with LangChain integration.
Provides the foundation for all 80 specialized WMS agents.
"""

import json
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, Union

from langchain.agents import Agent, AgentExecutor
from langchain.memory import ConversationBufferMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.tools import BaseTool
from langchain_core.language_models import BaseLanguageModel
from langchain_openai import AzureChatOpenAI

from ..core.config import get_azure_openai_settings, get_agent_settings
from ..core.logging import LoggerMixin, get_correlation_id
from ..database.connection import get_database_manager
from ..database.vector_store import get_weaviate_manager


class WMSContext:
    """Context object for sharing state between agents"""
    
    def __init__(self, user_id: str, user_role: str, session_id: str = None):
        self.user_id = user_id
        self.user_role = user_role
        self.session_id = session_id or str(uuid.uuid4())
        self.correlation_id = get_correlation_id()
        self.conversation_history = []
        self.shared_data = {}
        self.created_at = time.time()
    
    def add_message(self, role: str, content: str, metadata: Dict = None):
        """Add message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": time.time()
        })
    
    def get_context_summary(self) -> str:
        """Get summarized context for agent consumption"""
        return json.dumps({
            "user_role": self.user_role,
            "session_id": self.session_id,
            "conversation_length": len(self.conversation_history),
            "shared_data_keys": list(self.shared_data.keys())
        })


class WMSBaseTool(BaseTool, LoggerMixin):
    """Base class for all WMS tools with database integration"""
    
    def __init__(self, category: str, sub_category: str, **kwargs):
        super().__init__(**kwargs)
        self.category = category
        self.sub_category = sub_category
        self.db_manager = get_database_manager()
        self.vector_manager = get_weaviate_manager()
    
    def _run(self, query: str, context: WMSContext = None) -> str:
        """Execute the tool with proper logging and error handling"""
        start_time = time.time()
        
        try:
            self.log_info(
                f"Tool execution started: {self.name}",
                category=self.category,
                sub_category=self.sub_category,
                query_length=len(query),
                user_id=context.user_id if context else None
            )
            
            result = self._execute(query, context)
            execution_time = time.time() - start_time
            
            self.log_info(
                f"Tool execution completed: {self.name}",
                execution_time=execution_time,
                result_length=len(str(result))
            )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.log_error(
                f"Tool execution failed: {self.name}",
                error=str(e),
                execution_time=execution_time
            )
            return f"Error executing {self.name}: {str(e)}"
    
    @abstractmethod
    def _execute(self, query: str, context: WMSContext = None) -> str:
        """Implement the actual tool logic"""
        pass


class WMSBaseAgent(LoggerMixin, ABC):
    """Base class for all WMS agents with standardized functionality"""
    
    def __init__(self, category: str, sub_category: str, tools: List[WMSBaseTool] = None):
        super().__init__()
        self.category = category
        self.sub_category = sub_category
        self.tools = tools or []
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="output"
        )
        
        # Initialize LLM
        self.llm = self._initialize_llm()
        
        # Database connections
        self.db_manager = get_database_manager()
        self.vector_manager = get_weaviate_manager()
        
        # Agent-specific configuration
        self.agent_config = self._get_agent_config()
        
        self.log_info(
            f"Initialized WMS agent: {self.category}.{self.sub_category}",
            tools_count=len(self.tools)
        )
    
    def _initialize_llm(self) -> BaseLanguageModel:
        """Initialize Azure OpenAI LLM with proper configuration"""
        azure_settings = get_azure_openai_settings()
        agent_settings = get_agent_settings()
        
        return AzureChatOpenAI(
            azure_deployment=azure_settings.deployment_chat,
            openai_api_version=azure_settings.api_version,
            azure_endpoint=str(azure_settings.endpoint),
            api_key=azure_settings.api_key,
            temperature=agent_settings.llm_temperature,
            max_tokens=agent_settings.llm_max_tokens,
            model_name=azure_settings.model_name
        )
    
    def _get_agent_config(self) -> Dict[str, Any]:
        """Get agent-specific configuration"""
        return {
            "category": self.category,
            "sub_category": self.sub_category,
            "specialization": self._get_specialization(),
            "capabilities": self._get_capabilities(),
            "permissions": self._get_permissions()
        }
    
    @abstractmethod
    def _get_specialization(self) -> str:
        """Define what this agent specializes in"""
        pass
    
    @abstractmethod
    def _get_capabilities(self) -> List[str]:
        """Define what this agent can do"""
        pass
    
    def _get_permissions(self) -> List[str]:
        """Define what permissions this agent needs"""
        return ["read", "query"]
    
    async def process_query(self, query: str, context: WMSContext) -> Dict[str, Any]:
        """Main entry point for processing user queries"""
        start_time = time.time()
        
        try:
            self.log_info(
                f"Processing query in {self.category}.{self.sub_category}",
                query_length=len(query),
                user_role=context.user_role,
                session_id=context.session_id
            )
            
            # Check permissions
            if not self._check_permissions(context):
                return {
                    "success": False,
                    "error": "Insufficient permissions",
                    "category": self.category,
                    "sub_category": self.sub_category
                }
            
            # Validate query
            validation_result = await self._validate_query(query, context)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": validation_result["reason"],
                    "category": self.category,
                    "sub_category": self.sub_category
                }
            
            # Route to appropriate handler
            result = await self._route_query(query, context)
            
            # Post-process result
            processed_result = await self._post_process_result(result, context)
            
            execution_time = time.time() - start_time
            
            # Add metadata
            processed_result.update({
                "category": self.category,
                "sub_category": self.sub_category,
                "execution_time": execution_time,
                "agent_id": f"{self.category}.{self.sub_category}",
                "timestamp": time.time()
            })
            
            self.log_info(
                f"Query processed successfully",
                execution_time=execution_time,
                success=processed_result.get("success", True)
            )
            
            return processed_result
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.log_error(
                f"Query processing failed",
                error=str(e),
                execution_time=execution_time
            )
            
            return {
                "success": False,
                "error": str(e),
                "category": self.category,
                "sub_category": self.sub_category,
                "execution_time": execution_time
            }
    
    def _check_permissions(self, context: WMSContext) -> bool:
        """Check if user has required permissions"""
        from ..auth.permissions import check_user_permissions
        
        required_permissions = self._get_permissions()
        return check_user_permissions(context.user_role, required_permissions)
    
    async def _validate_query(self, query: str, context: WMSContext) -> Dict[str, Any]:
        """Validate the incoming query"""
        if not query or not query.strip():
            return {"valid": False, "reason": "Query cannot be empty"}
        
        if len(query) > 10000:  # 10KB limit
            return {"valid": False, "reason": "Query too long"}
        
        # Category-specific validation
        category_validation = await self._validate_category_specific(query, context)
        if not category_validation["valid"]:
            return category_validation
        
        return {"valid": True}
    
    async def _validate_category_specific(self, query: str, context: WMSContext) -> Dict[str, Any]:
        """Category-specific query validation (override in subclasses)"""
        return {"valid": True}
    
    async def _route_query(self, query: str, context: WMSContext) -> Dict[str, Any]:
        """Route query to appropriate processing method"""
        # Determine query type
        query_type = await self._classify_query_type(query, context)
        
        if query_type == "information_request":
            return await self._handle_information_request(query, context)
        elif query_type == "action_request":
            return await self._handle_action_request(query, context)
        elif query_type == "analysis_request":
            return await self._handle_analysis_request(query, context)
        else:
            return await self._handle_general_query(query, context)
    
    async def _classify_query_type(self, query: str, context: WMSContext) -> str:
        """Classify the type of query to route appropriately"""
        query_lower = query.lower()
        
        # Information request patterns
        info_patterns = ["what is", "explain", "describe", "tell me about", "how does"]
        if any(pattern in query_lower for pattern in info_patterns):
            return "information_request"
        
        # Action request patterns
        action_patterns = ["create", "update", "delete", "move", "assign", "process"]
        if any(pattern in query_lower for pattern in action_patterns):
            return "action_request"
        
        # Analysis request patterns
        analysis_patterns = ["analyze", "report", "summarize", "calculate", "compare"]
        if any(pattern in query_lower for pattern in analysis_patterns):
            return "analysis_request"
        
        return "general_query"
    
    async def _handle_information_request(self, query: str, context: WMSContext) -> Dict[str, Any]:
        """Handle information/knowledge requests"""
        # Search vector database for relevant information
        search_results = await self.vector_manager.search_knowledge(
            query=query,
            class_name=self._get_vector_class_name(),
            limit=5,
            certainty=0.7
        )
        
        if not search_results:
            return {
                "success": True,
                "response": "No relevant information found in the knowledge base.",
                "type": "information_request",
                "sources": []
            }
        
        # Combine search results into coherent response
        response = await self._synthesize_information_response(query, search_results, context)
        
        return {
            "success": True,
            "response": response,
            "type": "information_request",
            "sources": [{"id": r["id"], "certainty": r["certainty"]} for r in search_results]
        }
    
    async def _handle_action_request(self, query: str, context: WMSContext) -> Dict[str, Any]:
        """Handle action/operation requests"""
        # Extract action parameters
        action_params = await self._extract_action_parameters(query, context)
        
        # Validate action permissions
        if not self._can_perform_action(action_params, context):
            return {
                "success": False,
                "error": "Insufficient permissions for requested action",
                "type": "action_request"
            }
        
        # Execute action
        action_result = await self._execute_action(action_params, context)
        
        return {
            "success": action_result.get("success", True),
            "response": action_result.get("message", "Action completed"),
            "type": "action_request",
            "action": action_params.get("action_type"),
            "details": action_result
        }
    
    async def _handle_analysis_request(self, query: str, context: WMSContext) -> Dict[str, Any]:
        """Handle analysis/reporting requests"""
        # Extract analysis parameters
        analysis_params = await self._extract_analysis_parameters(query, context)
        
        # Perform analysis
        analysis_result = await self._perform_analysis(analysis_params, context)
        
        return {
            "success": True,
            "response": analysis_result.get("summary", "Analysis completed"),
            "type": "analysis_request",
            "analysis": analysis_params.get("analysis_type"),
            "data": analysis_result.get("data", {}),
            "insights": analysis_result.get("insights", [])
        }
    
    async def _handle_general_query(self, query: str, context: WMSContext) -> Dict[str, Any]:
        """Handle general queries that don't fit specific categories"""
        # Use LLM to process the query with context
        response = await self._generate_llm_response(query, context)
        
        return {
            "success": True,
            "response": response,
            "type": "general_query"
        }
    
    async def _synthesize_information_response(self, query: str, search_results: List[Dict], context: WMSContext) -> str:
        """Synthesize search results into coherent response"""
        # Combine relevant information
        combined_content = "\n".join([
            result["data"].get("content", "") for result in search_results[:3]
        ])
        
        # Create synthesis prompt
        synthesis_prompt = f"""
Based on the following WMS knowledge base information, provide a clear and comprehensive answer to the user's question.

User Question: {query}

Relevant Information:
{combined_content}

Instructions:
1. Answer directly and concisely
2. Only use information from the provided context
3. If information is incomplete, state what is missing
4. Include relevant details specific to {self.category} - {self.sub_category}
5. Format the response clearly with sections if needed

Answer:
"""
        
        # Generate response using LLM
        response = await self.llm.ainvoke(synthesis_prompt)
        return response.content if hasattr(response, 'content') else str(response)
    
    async def _generate_llm_response(self, query: str, context: WMSContext) -> str:
        """Generate response using LLM with proper context"""
        system_prompt = f"""
You are a specialized WMS assistant for {self.category} - {self.sub_category}.

Specialization: {self._get_specialization()}
Capabilities: {', '.join(self._get_capabilities())}

User Context:
- Role: {context.user_role}
- Session: {context.session_id}

Instructions:
1. Provide accurate information specific to {self.category}
2. Stay within your specialization area
3. Be concise but comprehensive
4. If you cannot answer, explain why and suggest alternatives
5. Use WMS terminology appropriately for the user's role level
"""
        
        # Create message chain
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        
        # Add conversation history if available
        for msg in context.conversation_history[-5:]:  # Last 5 messages
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Generate response
        response = await self.llm.ainvoke(messages)
        return response.content if hasattr(response, 'content') else str(response)
    
    def _get_vector_class_name(self) -> str:
        """Get the vector database class name for this agent"""
        # Map categories to vector classes
        class_mapping = {
            "locations": "LocationsKnowledge",
            "items": "ItemsKnowledge",
            "inventory_management": "InventoryKnowledge",
            "other_data_categorization": "DataCategorizationKnowledge"
        }
        return class_mapping.get(self.category, "WMSKnowledge")
    
    async def _extract_action_parameters(self, query: str, context: WMSContext) -> Dict[str, Any]:
        """Extract parameters for action requests (override in subclasses)"""
        return {"action_type": "generic", "parameters": {}}
    
    def _can_perform_action(self, action_params: Dict, context: WMSContext) -> bool:
        """Check if user can perform the requested action"""
        # Basic permission check - override in subclasses for specific logic
        user_permissions = self._get_user_permissions(context.user_role)
        required_permission = action_params.get("required_permission", "write")
        return required_permission in user_permissions
    
    async def _execute_action(self, action_params: Dict, context: WMSContext) -> Dict[str, Any]:
        """Execute the requested action (override in subclasses)"""
        return {
            "success": True,
            "message": f"Action {action_params.get('action_type', 'generic')} would be executed here"
        }
    
    async def _extract_analysis_parameters(self, query: str, context: WMSContext) -> Dict[str, Any]:
        """Extract parameters for analysis requests (override in subclasses)"""
        return {"analysis_type": "generic", "parameters": {}}
    
    async def _perform_analysis(self, analysis_params: Dict, context: WMSContext) -> Dict[str, Any]:
        """Perform the requested analysis (override in subclasses)"""
        return {
            "summary": f"Analysis {analysis_params.get('analysis_type', 'generic')} would be performed here",
            "data": {},
            "insights": []
        }
    
    async def _post_process_result(self, result: Dict[str, Any], context: WMSContext) -> Dict[str, Any]:
        """Post-process the result before returning (override for customization)"""
        # Add context to conversation history
        if result.get("success"):
            context.add_message("assistant", result.get("response", ""), {
                "category": self.category,
                "sub_category": self.sub_category,
                "type": result.get("type", "unknown")
            })
        
        return result
    
    def _get_user_permissions(self, user_role: str) -> List[str]:
        """Get permissions for user role"""
        role_permissions = {
            "end_user": ["read", "basic_query"],
            "operations_user": ["read", "write", "execute_operations"],
            "admin_user": ["read", "write", "delete", "configure", "manage_users"],
            "management_user": ["read", "analyze", "report"],
            "ceo_user": ["read", "strategic_analysis"]
        }
        return role_permissions.get(user_role, ["read"])


class WMSAgentOrchestrator(LoggerMixin):
    """Orchestrates multiple WMS agents and routes queries to appropriate agents"""
    
    def __init__(self):
        super().__init__()
        self.agents = {}
        self.agent_registry = {}
        self.load_agent_registry()
    
    def load_agent_registry(self):
        """Load registry of all available agents"""
        self.agent_registry = {
            # Category 1: WMS Introduction
            "wms_introduction.functional": "agents.categories.wms_introduction:WMSIntroductionFunctionalAgent",
            "wms_introduction.technical": "agents.categories.wms_introduction:WMSIntroductionTechnicalAgent",
            "wms_introduction.configuration": "agents.categories.wms_introduction:WMSIntroductionConfigurationAgent",
            "wms_introduction.relationships": "agents.categories.wms_introduction:WMSIntroductionRelationshipsAgent",
            "wms_introduction.notes": "agents.categories.wms_introduction:WMSIntroductionNotesAgent",
            
            # Category 2: Locations
            "locations.functional": "agents.categories.locations:LocationsFunctionalAgent",
            "locations.technical": "agents.categories.locations:LocationsTechnicalAgent",
            "locations.configuration": "agents.categories.locations:LocationsConfigurationAgent",
            "locations.relationships": "agents.categories.locations:LocationsRelationshipsAgent",
            "locations.notes": "agents.categories.locations:LocationsNotesAgent",
            
            # Category 3: Items
            "items.functional": "agents.categories.items:ItemsFunctionalAgent",
            "items.technical": "agents.categories.items:ItemsTechnicalAgent",
            "items.configuration": "agents.categories.items:ItemsConfigurationAgent",
            "items.relationships": "agents.categories.items:ItemsRelationshipsAgent",
            "items.notes": "agents.categories.items:ItemsNotesAgent",
            
            # Category 4: Receiving
            "receiving.functional": "agents.categories.receiving:ReceivingFunctionalAgent",
            "receiving.technical": "agents.categories.receiving:ReceivingTechnicalAgent",
            "receiving.configuration": "agents.categories.receiving:ReceivingConfigurationAgent",
            "receiving.relationships": "agents.categories.receiving:ReceivingRelationshipsAgent",
            "receiving.notes": "agents.categories.receiving:ReceivingNotesAgent",
            
            # Category 5: Locating/Putaway
            "locating_putaway.functional": "agents.categories.locating_putaway:LocatingPutawayFunctionalAgent",
            "locating_putaway.technical": "agents.categories.locating_putaway:LocatingPutawayTechnicalAgent",
            "locating_putaway.configuration": "agents.categories.locating_putaway:LocatingPutawayConfigurationAgent",
            "locating_putaway.relationships": "agents.categories.locating_putaway:LocatingPutawayRelationshipsAgent",
            "locating_putaway.notes": "agents.categories.locating_putaway:LocatingPutawayNotesAgent",
            
            # Category 6: Work Management
            "work.functional": "agents.categories.work:WorkFunctionalAgent",
            "work.technical": "agents.categories.work:WorkTechnicalAgent",
            "work.configuration": "agents.categories.work:WorkConfigurationAgent",
            "work.relationships": "agents.categories.work:WorkRelationshipsAgent",
            "work.notes": "agents.categories.work:WorkNotesAgent",
            
            # Category 7: Inventory Management
            "inventory_management.functional": "agents.categories.inventory:InventoryFunctionalAgent",
            "inventory_management.technical": "agents.categories.inventory:InventoryTechnicalAgent",
            "inventory_management.configuration": "agents.categories.inventory:InventoryConfigurationAgent",
            "inventory_management.relationships": "agents.categories.inventory:InventoryRelationshipsAgent",
            "inventory_management.notes": "agents.categories.inventory:InventoryNotesAgent",
            
            # Category 8: Cycle Counting
            "cycle_counting.functional": "agents.categories.cycle_counting:CycleCountingFunctionalAgent",
            "cycle_counting.technical": "agents.categories.cycle_counting:CycleCountingTechnicalAgent",
            "cycle_counting.configuration": "agents.categories.cycle_counting:CycleCountingConfigurationAgent",
            "cycle_counting.relationships": "agents.categories.cycle_counting:CycleCountingRelationshipsAgent",
            "cycle_counting.notes": "agents.categories.cycle_counting:CycleCountingNotesAgent",
            
            # Category 16: Data Categorization
            "other_data_categorization.functional": "agents.categories.data_categorization:DataCategorizationFunctionalAgent",
            "other_data_categorization.technical": "agents.categories.data_categorization:DataCategorizationTechnicalAgent",
            "other_data_categorization.configuration": "agents.categories.data_categorization:DataCategorizationConfigurationAgent",
            "other_data_categorization.relationships": "agents.categories.data_categorization:DataCategorizationRelationshipsAgent",
            "other_data_categorization.notes": "agents.categories.data_categorization:DataCategorizationNotesAgent",
            
            # Operational Database Agents
            "operational_database.query_execution": "agents.operational_db.operational_query_agent:OperationalDatabaseQueryAgent",
            "operational_database.multi_table_operations": "agents.operational_db.multi_table_orchestrator:MultiTableQueryAgent",
            
            # Additional categories would be added here...
        }
    
    async def route_query(self, query: str, context: WMSContext, 
                         preferred_category: str = None, 
                         preferred_sub_category: str = None) -> Dict[str, Any]:
        """Route query to the most appropriate agent"""
        
        try:
            # Determine best agent for the query
            agent_id = await self._determine_best_agent(
                query, context, preferred_category, preferred_sub_category
            )
            
            # Get or create agent instance
            agent = await self._get_agent(agent_id)
            
            if not agent:
                return {
                    "success": False,
                    "error": f"Agent not found: {agent_id}",
                    "suggested_agents": list(self.agent_registry.keys())[:5]
                }
            
            # Process query with selected agent
            result = await agent.process_query(query, context)
            
            # Add routing metadata
            result["routed_to"] = agent_id
            result["routing_confidence"] = 0.8  # Would be calculated by routing logic
            
            self.log_info(
                f"Query routed successfully to {agent_id}",
                success=result.get("success", False),
                query_length=len(query)
            )
            
            return result
            
        except Exception as e:
            self.log_error(f"Query routing failed: {e}")
            return {
                "success": False,
                "error": f"Routing failed: {str(e)}",
                "fallback_response": "I encountered an error while processing your query. Please try rephrasing your question."
            }
    
    async def _determine_best_agent(self, query: str, context: WMSContext,
                                  preferred_category: str = None,
                                  preferred_sub_category: str = None) -> str:
        """Determine the best agent to handle the query"""
        
        # If specific agent is requested, use it
        if preferred_category and preferred_sub_category:
            agent_id = f"{preferred_category}.{preferred_sub_category}"
            if agent_id in self.agent_registry:
                return agent_id
        
        # Use simple keyword-based routing for now
        # In production, this would use ML-based classification
        query_lower = query.lower()
        
        # Category keywords mapping
        category_keywords = {
            "locations": ["location", "bin", "aisle", "zone", "coordinate", "layout"],
            "items": ["item", "product", "sku", "part", "material", "catalog"],
            "receiving": ["receive", "receipt", "inbound", "asn", "delivery", "dock"],
            "locating_putaway": ["putaway", "put away", "locate", "placement", "storage", "slotting"],
            "work": ["work", "task", "assignment", "labor", "productivity", "performance"],
            "inventory_management": ["inventory", "stock", "quantity", "balance", "on hand"],
            "cycle_counting": ["cycle count", "count", "counting", "accuracy", "audit", "variance"],
            "wms_introduction": ["wms", "system", "overview", "introduction", "basics"],
            "other_data_categorization": ["categorize", "classify", "data", "upload", "process"],
            "operational_database": ["operational", "database", "query", "data", "real-time", "current",
                                   "show me", "display", "list", "find", "search", "report", "summary",
                                   "how many", "what are", "which", "analytics", "metrics", "performance",
                                   "today", "yesterday", "this week", "this month", "recent", "latest",
                                   "complex", "multiple", "relationship", "correlation", "across", "between",
                                   "join", "combine", "merge", "compare", "analysis", "trend", "pattern",
                                   "comprehensive", "detailed", "full picture", "complete view",
                                   "cross-category", "multi-table", "integrated"]
        }
        
        # Sub-category keywords mapping
        sub_category_keywords = {
            "functional": ["how", "process", "workflow", "business", "operation"],
            "technical": ["technical", "system", "integration", "api", "database"],
            "configuration": ["configure", "setup", "parameter", "setting", "option"],
            "relationships": ["relationship", "link", "connection", "integration", "mapping"],
            "notes": ["best practice", "recommendation", "tip", "note", "advice"],
            "query_execution": ["execute", "run", "get", "retrieve", "fetch", "sql", "select"],
            "multi_table_operations": ["multi", "complex", "join", "relationship", "cross", "combined"]
        }
        
        # Score each category
        category_scores = {}
        for category, keywords in category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in query_lower)
            if score > 0:
                category_scores[category] = score
        
        # Score each sub-category
        sub_category_scores = {}
        for sub_category, keywords in sub_category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in query_lower)
            if score > 0:
                sub_category_scores[sub_category] = score
        
        # Select best category and sub-category
        best_category = max(category_scores, key=category_scores.get) if category_scores else "wms_introduction"
        best_sub_category = max(sub_category_scores, key=sub_category_scores.get) if sub_category_scores else "functional"
        
        agent_id = f"{best_category}.{best_sub_category}"
        
        # Fallback to available agent if not found
        if agent_id not in self.agent_registry:
            agent_id = next(iter(self.agent_registry.keys()))
        
        self.log_info(
            f"Determined best agent: {agent_id}",
            category_scores=category_scores,
            sub_category_scores=sub_category_scores
        )
        
        return agent_id
    
    async def _get_agent(self, agent_id: str) -> Optional[WMSBaseAgent]:
        """Get or create agent instance"""
        if agent_id not in self.agents:
            # Lazy load agent
            if agent_id in self.agent_registry:
                try:
                    # Dynamic import and instantiation would go here
                    # For now, return a placeholder
                    self.log_warning(f"Agent {agent_id} not yet implemented, using placeholder")
                    return None
                except Exception as e:
                    self.log_error(f"Failed to load agent {agent_id}: {e}")
                    return None
            else:
                self.log_error(f"Agent {agent_id} not found in registry")
                return None
        
        return self.agents[agent_id]
    
    def register_agent(self, agent_id: str, agent_instance: WMSBaseAgent):
        """Register an agent instance"""
        self.agents[agent_id] = agent_instance
        self.log_info(f"Registered agent: {agent_id}")
    
    def get_available_agents(self) -> List[str]:
        """Get list of all available agents"""
        return list(self.agent_registry.keys())
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of agent system"""
        total_agents = len(self.agent_registry)
        loaded_agents = len(self.agents)
        
        return {
            "status": "healthy",
            "total_agents_registered": total_agents,
            "agents_loaded": loaded_agents,
            "agent_registry_keys": list(self.agent_registry.keys())[:10]  # First 10 for brevity
        }


# Global orchestrator instance
_orchestrator = None


def get_agent_orchestrator() -> WMSAgentOrchestrator:
    """Get global agent orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WMSAgentOrchestrator()
    return _orchestrator