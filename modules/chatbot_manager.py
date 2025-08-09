import os
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# LangChain imports
from langchain_openai import AzureChatOpenAI
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.memory import BaseMemory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain.chains.conversation.memory import ConversationBufferMemory

# Azure OpenAI
from openai import AzureOpenAI

from .logger import LoggerMixin
from .config_manager import ConfigManager

class ChatbotManager(LoggerMixin):
    """
    Manages WMS chatbot functionality with conversation memory
    """
    
    def __init__(self, db_manager, config_manager: ConfigManager = None):
        super().__init__()
        
        self.db_manager = db_manager
        self.config_manager = config_manager or ConfigManager()
        
        # Initialize components
        self.llm = None
        self.documents = []
        self.memory = None
        
        # Conversation history
        self.conversation_history = []
        self.max_history = 50
        
        # Initialize chatbot
        self.init_chatbot()
        
        self.log_info("Chatbot manager initialized")
    
    def init_chatbot(self):
        """Initialize chatbot components"""
        try:
            # Check if Azure OpenAI is configured
            if not self.config_manager.is_azure_configured():
                self.log_warning("Azure OpenAI not configured - chatbot will use placeholder responses")
                return
            
            azure_config = self.config_manager.get_azure_config()
            chatbot_config = self.config_manager.get_chatbot_config()
            
            # Initialize Azure OpenAI client for text-only queries
            self.llm = AzureChatOpenAI(
                azure_deployment=azure_config["deployment"]["chat"],
                openai_api_version=azure_config["api_version"],
                azure_endpoint=azure_config["endpoint"],
                api_key=azure_config["api_key"],
                temperature=0.0,  # Zero temperature for deterministic responses
                max_tokens=chatbot_config.get("max_tokens", 4000)
            )
            
            # Load documents into memory
            documents = self.db_manager.get_documents(limit=1000)
            for doc in documents:
                content = doc.get('content', '')
                if content.strip():
                    self.documents.append({
                        'content': content,
                        'metadata': {
                            'document_id': doc.get('document_id'),
                            'filename': doc.get('filename'),
                            'file_type': doc.get('file_type'),
                            'created_at': doc.get('created_at')
                        }
                    })
            
            # Initialize conversation memory with message history
            self.message_history = ChatMessageHistory()
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                chat_memory=self.message_history,
                max_token_limit=chatbot_config.get("max_tokens", 4000),
                output_key="output"  # Add output_key to fix deprecation warning
            )
            
            self.log_info(f"Chatbot initialized with {len(self.documents)} documents")
            
        except Exception as e:
            self.log_error(f"Failed to initialize chatbot: {e}")
            self.log_warning("Chatbot will use placeholder responses")
    
    def process_query(self, query: str, include_sources: bool = True) -> Dict[str, Any]:
        """Process a user query and return response"""
        try:
            self.add_to_history("user", query)
            
            if not self.llm:
                return self.get_placeholder_response(query)
            
            start_time = time.time()
            
            # Find relevant documents using vector search (k=6, high precision)
            search_results = self.db_manager.search_documents(query, limit=6, min_score=0.7)
            context = ""
            source_documents = []
            for doc in search_results:
                # Only use vector DB results
                if doc.get('vector_exists', True):
                    context += f"\n{doc['content']}"
                    source_documents.append({
                        'content': doc['content'],
                        'metadata': {
                            'document_id': doc['document_id'],
                            'filename': doc['filename'],
                            'file_type': doc['file_type'],
                            'created_at': doc['created_at'],
                            'similarity_score': doc.get('similarity_score', 0)
                        }
                    })
            
            # Create prompt
            prompt = f"""You are a WMS assistant that STRICTLY uses only the provided vector database context. Never add your own knowledge or assumptions.

CRITICAL INSTRUCTIONS:
1. ONLY use information from the provided vector database context
2. If no relevant information is found in the context, respond with "No relevant information found in the vector database."
3. For every piece of information in your response, cite the source document using [Doc ID: xxx]
4. Keep responses factual and directly tied to the context
5. Do not make assumptions or add external information
6. Format responses with clear sections and citations

Available Context (Vector DB, k=6):
{context}

Previous Conversation:
{self.memory.buffer if hasattr(self.memory, 'buffer') else ''}

Current Question: {query}

Remember: Only respond with information from the vector database context. Always include document references."""

            # Get response from LLM
            response = self.llm.invoke(prompt)
            processing_time = time.time() - start_time
            
            # Extract response text
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Add response to history
            self.add_to_history("assistant", response_text)
            
            # Prepare result
            result_data = {
                "success": True,
                "response": response_text,
                "processing_time": processing_time,
                "query": query,
                "timestamp": datetime.now().isoformat()
            }
            
            if include_sources and source_documents:
                result_data["sources"] = self.format_sources(source_documents)
            
            self.log_info(f"Query processed successfully in {processing_time:.2f}s")
            return result_data
            
        except Exception as e:
            self.log_error(f"Error processing query: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": "I'm sorry, I encountered an error while processing your query.",
                "query": query,
                "timestamp": datetime.now().isoformat()
            }
    
    def get_placeholder_response(self, query: str) -> Dict[str, Any]:
        """Get placeholder response when chatbot is not fully initialized"""
        placeholder_responses = {
            "warehouse": "I'm a WMS chatbot designed to help with warehouse management queries. I can answer questions about inventory, shipping, receiving, and other warehouse operations.",
            "inventory": "I can help you with inventory management questions. Please ask me about stock levels, item locations, or inventory processes.",
            "shipping": "I can assist with shipping and logistics questions. Ask me about shipping methods, tracking, or delivery processes.",
            "receiving": "I can help with receiving operations. Ask me about receiving procedures, quality checks, or putaway processes."
        }
        
        query_lower = query.lower()
        response = "I'm a WMS chatbot. I can help you with warehouse management questions. Please ask me about inventory, shipping, receiving, or other warehouse operations."
        
        for keyword, specific_response in placeholder_responses.items():
            if keyword in query_lower:
                response = specific_response
                break
        
        return {
            "success": True,
            "response": response,
            "processing_time": 0.1,
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "note": "Placeholder response - Azure OpenAI not configured"
        }
    
    def format_sources(self, source_documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format source documents for display"""
        sources = []
        for doc in source_documents:
            metadata = doc['metadata']
            content = doc['content']
            sources.append({
                "filename": metadata.get("filename", "Unknown"),
                "file_type": metadata.get("file_type", "Unknown"),
                "content_preview": content[:200] + "..." if len(content) > 200 else content,
                "created_at": metadata.get("created_at", "Unknown")
            })
        return sources
    
    def add_to_history(self, role: str, content: str):
        """Add message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        # Limit history size
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
    
    def get_conversation_history(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get conversation history"""
        if limit:
            return self.conversation_history[-limit:]
        return self.conversation_history.copy()
    
    def clear_conversation_history(self):
        """Clear conversation history"""
        self.conversation_history.clear()
        if self.memory:
            self.memory.clear()
        self.log_info("Conversation history cleared")
    
    def process_image_query(self, image_path: str, query: str = None) -> Dict[str, Any]:
        """Process image-based query - DISABLED"""
        return {
            "success": False,
            "error": "Image analysis is disabled. Please use text-based queries with vector search.",
            "response": "Image analysis is not available. Please describe your question in text form.",
            "image_path": image_path,
            "query": query
        }
    
    def get_chatbot_stats(self) -> Dict[str, Any]:
        """Get chatbot statistics"""
        try:
            stats = {
                "conversation_history_count": len(self.conversation_history),
                "memory_buffer_size": len(self.memory.chat_memory.messages) if self.memory else 0,
                "document_count": len(self.documents),
                "llm_configured": self.llm is not None
            }
            return stats
        except Exception as e:
            self.log_error(f"Error getting chatbot stats: {e}")
            return {}
    
    def close(self):
        """Cleanup resources"""
        try:
            if self.memory:
                self.memory.clear()
            self.conversation_history.clear()
            self.documents.clear()
            self.log_info("Chatbot resources cleaned up")
        except Exception as e:
            self.log_error(f"Error during cleanup: {e}")