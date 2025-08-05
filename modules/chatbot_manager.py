import os
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# LangChain imports
from langchain_community.chat_models import AzureChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from langchain.schema import Document

# Azure OpenAI
from openai import AzureOpenAI

from .logger import LoggerMixin
from .config_manager import ConfigManager

class ChatbotManager(LoggerMixin):
    """
    Manages WMS chatbot functionality with RAG and conversation memory
    """
    
    def __init__(self, db_manager, config_manager: ConfigManager = None):
        super().__init__()
        
        self.db_manager = db_manager
        self.config_manager = config_manager or ConfigManager()
        
        # Initialize components
        self.llm = None
        self.embeddings = None
        self.vector_store = None
        self.conversation_chain = None
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
            
            # Initialize Azure OpenAI client
            self.llm = AzureChatOpenAI(
                azure_deployment=azure_config["deployment_name"],
                openai_api_version=azure_config["api_version"],
                azure_endpoint=azure_config["endpoint"],
                api_key=azure_config["api_key"],
                temperature=chatbot_config.get("temperature", 0.7),
                max_tokens=chatbot_config.get("max_tokens", 4000)
            )
            
            # Initialize embeddings
            self.embeddings = OpenAIEmbeddings(
                azure_deployment=azure_config["deployment_name"],
                openai_api_version=azure_config["api_version"],
                azure_endpoint=azure_config["endpoint"],
                api_key=azure_config["api_key"]
            )
            
            # Initialize vector store
            self.init_vector_store()
            
            # Initialize conversation memory
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                max_token_limit=chatbot_config.get("max_tokens", 4000)
            )
            
            # Initialize conversation chain
            self.init_conversation_chain()
            
            self.log_info("Chatbot components initialized successfully")
            
        except Exception as e:
            self.log_error(f"Failed to initialize chatbot: {e}")
            self.log_warning("Chatbot will use placeholder responses")
    
    def init_vector_store(self):
        """Initialize vector store from database"""
        try:
            # Get documents from database
            documents = self.db_manager.get_documents(limit=1000)  # Get all documents
            
            if not documents:
                self.log_info("No documents found in database for vector store")
                return
            
            # Prepare documents for vector store
            docs = []
            for doc in documents:
                content = doc.get('content', '')
                if content.strip():
                    metadata = {
                        'document_id': doc.get('document_id'),
                        'filename': doc.get('filename'),
                        'file_type': doc.get('file_type'),
                        'created_at': doc.get('created_at'),
                        'source': 'wms_database'
                    }
                    
                    # Split content into chunks
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=1000,
                        chunk_overlap=200
                    )
                    chunks = text_splitter.split_text(content)
                    
                    for i, chunk in enumerate(chunks):
                        docs.append(Document(
                            page_content=chunk,
                            metadata={**metadata, 'chunk_id': i}
                        ))
            
            # Create vector store
            if docs:
                self.vector_store = Chroma.from_documents(
                    documents=docs,
                    embedding=self.embeddings,
                    persist_directory=self.config_manager.get("database.chroma_path")
                )
                
                self.log_info(f"Vector store initialized with {len(docs)} document chunks")
            else:
                self.log_warning("No valid document content found for vector store")
                
        except Exception as e:
            self.log_error(f"Failed to initialize vector store: {e}")
    
    def init_conversation_chain(self):
        """Initialize conversation chain"""
        try:
            if not self.llm or not self.vector_store:
                self.log_warning("LLM or vector store not available - conversation chain not initialized")
                return
            
            # Create WMS-specific prompt template
            prompt_template = """You are a helpful Warehouse Management System (WMS) assistant. 
You have access to a knowledge base of documents and screenshots related to warehouse operations.

Use the following context to answer the user's question. If you don't know the answer, just say that you don't know, don't try to make up an answer.

Context:
{context}

Chat History:
{chat_history}

Human: {question}
Assistant:"""

            prompt = PromptTemplate(
                input_variables=["context", "chat_history", "question"],
                template=prompt_template
            )
            
            # Create conversation chain
            self.conversation_chain = ConversationalRetrievalChain.from_llm(
                llm=self.llm,
                retriever=self.vector_store.as_retriever(
                    search_type="similarity",
                    search_kwargs={"k": 5}
                ),
                memory=self.memory,
                combine_docs_chain_kwargs={"prompt": prompt},
                return_source_documents=True,
                verbose=False
            )
            
            self.log_info("Conversation chain initialized successfully")
            
        except Exception as e:
            self.log_error(f"Failed to initialize conversation chain: {e}")
    
    def process_query(self, query: str, include_sources: bool = True) -> Dict[str, Any]:
        """
        Process a user query and return response
        
        Args:
            query: User's question
            include_sources: Whether to include source documents in response
            
        Returns:
            Dictionary with response and metadata
        """
        try:
            # Add to conversation history
            self.add_to_history("user", query)
            
            # Check if chatbot is properly initialized
            if not self.conversation_chain:
                return self.get_placeholder_response(query)
            
            # Process query
            start_time = time.time()
            result = self.conversation_chain({"question": query})
            processing_time = time.time() - start_time
            
            # Extract response and sources
            response = result.get("answer", "I'm sorry, I couldn't generate a response.")
            source_documents = result.get("source_documents", [])
            
            # Add response to history
            self.add_to_history("assistant", response)
            
            # Prepare result
            result_data = {
                "success": True,
                "response": response,
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
    
    def format_sources(self, source_documents: List[Document]) -> List[Dict[str, Any]]:
        """Format source documents for display"""
        sources = []
        for doc in source_documents:
            metadata = doc.metadata
            sources.append({
                "filename": metadata.get("filename", "Unknown"),
                "file_type": metadata.get("file_type", "Unknown"),
                "chunk_id": metadata.get("chunk_id", 0),
                "content_preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
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
    
    def search_documents(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search documents using vector similarity
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of relevant documents
        """
        try:
            if not self.vector_store:
                return []
            
            # Search vector store
            docs = self.vector_store.similarity_search(query, k=limit)
            
            # Format results
            results = []
            for doc in docs:
                metadata = doc.metadata
                results.append({
                    "content": doc.page_content,
                    "filename": metadata.get("filename", "Unknown"),
                    "file_type": metadata.get("file_type", "Unknown"),
                    "document_id": metadata.get("document_id", "Unknown"),
                    "created_at": metadata.get("created_at", "Unknown")
                })
            
            return results
            
        except Exception as e:
            self.log_error(f"Error searching documents: {e}")
            return []
    
    def process_image_query(self, image_path: str, query: str = None) -> Dict[str, Any]:
        """
        Process image-based query using Azure OpenAI Vision
        
        Args:
            image_path: Path to image file
            query: Optional specific question about the image
            
        Returns:
            Dictionary with response and metadata
        """
        try:
            if not self.config_manager.is_azure_configured():
                return {
                    "success": False,
                    "error": "Azure OpenAI not configured for image processing",
                    "response": "Image processing requires Azure OpenAI configuration."
                }
            
            azure_config = self.config_manager.get_azure_config()
            client = AzureOpenAI(
                api_key=azure_config["api_key"],
                api_version=azure_config["api_version"],
                azure_endpoint=azure_config["endpoint"]
            )
            
            # Prepare prompt
            if query:
                prompt = f"Analyze this warehouse-related image and answer: {query}"
            else:
                prompt = "Analyze this warehouse-related image and describe what you see, focusing on warehouse management aspects like inventory, equipment, processes, or safety considerations."
            
            # Read image
            with open(image_path, 'rb') as image_file:
                response = client.chat.completions.create(
                    model="gpt-4-vision-preview",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": prompt
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_file.read()}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=1000
                )
            
            response_text = response.choices[0].message.content
            
            return {
                "success": True,
                "response": response_text,
                "image_path": image_path,
                "query": query,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.log_error(f"Error processing image query: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": "I'm sorry, I encountered an error while processing the image.",
                "image_path": image_path,
                "query": query
            }
    
    def update_knowledge_base(self):
        """Update knowledge base with new documents"""
        try:
            self.log_info("Updating knowledge base...")
            self.init_vector_store()
            self.init_conversation_chain()
            self.log_info("Knowledge base updated successfully")
            return True
        except Exception as e:
            self.log_error(f"Error updating knowledge base: {e}")
            return False
    
    def get_chatbot_stats(self) -> Dict[str, Any]:
        """Get chatbot statistics"""
        try:
            stats = {
                "conversation_history_count": len(self.conversation_history),
                "memory_buffer_size": len(self.memory.chat_memory.messages) if self.memory else 0,
                "vector_store_documents": self.vector_store._collection.count() if self.vector_store else 0,
                "llm_configured": self.llm is not None,
                "embeddings_configured": self.embeddings is not None,
                "conversation_chain_configured": self.conversation_chain is not None
            }
            return stats
        except Exception as e:
            self.log_error(f"Error getting chatbot stats: {e}")
            return {}
    
    def close(self):
        """Cleanup chatbot resources"""
        try:
            if self.vector_store:
                self.vector_store.persist()
            
            self.log_info("Chatbot resources cleaned up")
            
        except Exception as e:
            self.log_error(f"Error during chatbot cleanup: {e}") 