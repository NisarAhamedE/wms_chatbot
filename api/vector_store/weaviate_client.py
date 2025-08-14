import os
import json
import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import logging
import weaviate
from weaviate.config import Config
from weaviate.exceptions import WeaviateException
import numpy as np

# LangChain imports
from langchain.embeddings import OpenAIEmbeddings, HuggingFaceEmbeddings
from langchain.vectorstores import Weaviate
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Local imports
from ..files.models import FileMetadata
from ..database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:5002")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class WeaviateManager:
    """Manager for Weaviate vector database operations."""
    
    def __init__(self):
        self.client = None
        self.embeddings = None
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        self.schemas_created = False
        
        # Initialize client
        self.connect()
    
    def connect(self):
        """Connect to Weaviate instance."""
        try:
            # Configure Weaviate client
            config = Config(
                connection_config=weaviate.ConnectionConfig(
                    url=WEAVIATE_URL,
                    api_key=WEAVIATE_API_KEY
                ),
                additional_config=weaviate.AdditionalConfig(
                    timeout=(30, 60)  # (connection, read) timeout in seconds
                )
            )
            
            self.client = weaviate.Client(config=config)
            
            # Test connection
            if self.client.is_ready():
                logger.info("Connected to Weaviate successfully")
                self.setup_schemas()
            else:
                logger.warning("Weaviate is not ready")
                
        except Exception as e:
            logger.error(f"Failed to connect to Weaviate: {e}")
            self.client = None
    
    def setup_embeddings(self):
        """Initialize embeddings model."""
        try:
            if OPENAI_API_KEY:
                self.embeddings = OpenAIEmbeddings(
                    openai_api_key=OPENAI_API_KEY,
                    model="text-embedding-ada-002"
                )
                logger.info("Using OpenAI embeddings")
            else:
                self.embeddings = HuggingFaceEmbeddings(
                    model_name="sentence-transformers/all-MiniLM-L6-v2",
                    model_kwargs={'device': 'cpu'}
                )
                logger.info("Using HuggingFace embeddings")
                
        except Exception as e:
            logger.error(f"Failed to initialize embeddings: {e}")
            self.embeddings = None
    
    def setup_schemas(self):
        """Create Weaviate schemas for WMS data."""
        if not self.client or self.schemas_created:
            return
        
        try:
            # File Content Schema
            file_content_schema = {
                "class": "FileContent",
                "description": "Chunks of content from uploaded files",
                "vectorizer": "none",  # We'll provide our own vectors
                "properties": [
                    {
                        "name": "content",
                        "dataType": ["text"],
                        "description": "The text content of the chunk"
                    },
                    {
                        "name": "fileId",
                        "dataType": ["string"],
                        "description": "ID of the source file"
                    },
                    {
                        "name": "fileName",
                        "dataType": ["string"],
                        "description": "Name of the source file"
                    },
                    {
                        "name": "chunkIndex",
                        "dataType": ["int"],
                        "description": "Index of this chunk within the file"
                    },
                    {
                        "name": "category",
                        "dataType": ["string"],
                        "description": "WMS category of the file"
                    },
                    {
                        "name": "fileType",
                        "dataType": ["string"],
                        "description": "Type of the source file"
                    },
                    {
                        "name": "uploadedBy",
                        "dataType": ["int"],
                        "description": "User ID who uploaded the file"
                    },
                    {
                        "name": "uploadedAt",
                        "dataType": ["date"],
                        "description": "When the file was uploaded"
                    },
                    {
                        "name": "keywords",
                        "dataType": ["string[]"],
                        "description": "Keywords extracted from the content"
                    }
                ]
            }
            
            # WMS Knowledge Schema
            wms_knowledge_schema = {
                "class": "WMSKnowledge",
                "description": "WMS knowledge base entries",
                "vectorizer": "none",
                "properties": [
                    {
                        "name": "title",
                        "dataType": ["string"],
                        "description": "Title of the knowledge entry"
                    },
                    {
                        "name": "content",
                        "dataType": ["text"],
                        "description": "Content of the knowledge entry"
                    },
                    {
                        "name": "category",
                        "dataType": ["string"],
                        "description": "WMS category"
                    },
                    {
                        "name": "subcategory",
                        "dataType": ["string"],
                        "description": "WMS subcategory"
                    },
                    {
                        "name": "tags",
                        "dataType": ["string[]"],
                        "description": "Tags associated with the entry"
                    },
                    {
                        "name": "source",
                        "dataType": ["string"],
                        "description": "Source of the knowledge"
                    },
                    {
                        "name": "createdAt",
                        "dataType": ["date"],
                        "description": "When the entry was created"
                    },
                    {
                        "name": "updatedAt",
                        "dataType": ["date"],
                        "description": "When the entry was last updated"
                    }
                ]
            }
            
            # Conversation Context Schema
            conversation_context_schema = {
                "class": "ConversationContext",
                "description": "Context from conversations for learning",
                "vectorizer": "none",
                "properties": [
                    {
                        "name": "question",
                        "dataType": ["text"],
                        "description": "User question"
                    },
                    {
                        "name": "answer",
                        "dataType": ["text"],
                        "description": "Agent response"
                    },
                    {
                        "name": "agentId",
                        "dataType": ["string"],
                        "description": "ID of the agent that responded"
                    },
                    {
                        "name": "category",
                        "dataType": ["string"],
                        "description": "WMS category of the conversation"
                    },
                    {
                        "name": "userId",
                        "dataType": ["int"],
                        "description": "User who had the conversation"
                    },
                    {
                        "name": "rating",
                        "dataType": ["int"],
                        "description": "User rating of the response"
                    },
                    {
                        "name": "createdAt",
                        "dataType": ["date"],
                        "description": "When the conversation occurred"
                    }
                ]
            }
            
            # Create schemas if they don't exist
            existing_schemas = [schema["class"] for schema in self.client.schema.get()["classes"]]
            
            if "FileContent" not in existing_schemas:
                self.client.schema.create_class(file_content_schema)
                logger.info("Created FileContent schema")
            
            if "WMSKnowledge" not in existing_schemas:
                self.client.schema.create_class(wms_knowledge_schema)
                logger.info("Created WMSKnowledge schema")
            
            if "ConversationContext" not in existing_schemas:
                self.client.schema.create_class(conversation_context_schema)
                logger.info("Created ConversationContext schema")
            
            self.schemas_created = True
            self.setup_embeddings()
            
        except Exception as e:
            logger.error(f"Error setting up schemas: {e}")
    
    async def add_file_content(
        self, 
        file_metadata: FileMetadata, 
        force_reprocess: bool = False
    ) -> Dict[str, Any]:
        """Add file content to vector store."""
        if not self.client or not self.embeddings:
            return {"success": False, "error": "Vector store not available"}
        
        try:
            # Check if file already processed
            if not force_reprocess:
                existing = self.client.data_object.get(
                    class_name="FileContent",
                    where={
                        "path": ["fileId"],
                        "operator": "Equal",
                        "valueString": file_metadata.id
                    }
                )
                
                if existing.get("objects"):
                    return {"success": True, "message": "File already processed", "chunks": 0}
            
            # Extract and chunk content
            content = file_metadata.extracted_text or ""
            if not content:
                return {"success": False, "error": "No content to vectorize"}
            
            chunks = self.text_splitter.split_text(content)
            
            if not chunks:
                return {"success": False, "error": "No chunks generated"}
            
            # Delete existing content for this file
            if force_reprocess:
                await self.delete_file_content(file_metadata.id)
            
            # Process chunks
            added_chunks = 0
            batch_size = 100
            
            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i:i + batch_size]
                batch_objects = []
                
                for idx, chunk in enumerate(batch_chunks):
                    try:
                        # Generate embedding
                        embedding = self.embeddings.embed_query(chunk)
                        
                        # Prepare object
                        obj = {
                            "content": chunk,
                            "fileId": file_metadata.id,
                            "fileName": file_metadata.original_name,
                            "chunkIndex": i + idx,
                            "category": file_metadata.categories[0] if file_metadata.categories else "Other",
                            "fileType": file_metadata.file_type,
                            "uploadedBy": file_metadata.uploaded_by,
                            "uploadedAt": file_metadata.uploaded_at.isoformat(),
                            "keywords": file_metadata.keywords or []
                        }
                        
                        batch_objects.append({
                            "class": "FileContent",
                            "properties": obj,
                            "vector": embedding
                        })
                        
                    except Exception as e:
                        logger.error(f"Error processing chunk {idx}: {e}")
                        continue
                
                # Batch insert
                if batch_objects:
                    try:
                        result = self.client.batch.create_objects(batch_objects)
                        added_chunks += len([r for r in result if r.get("result", {}).get("status") == "SUCCESS"])
                    except Exception as e:
                        logger.error(f"Error inserting batch: {e}")
            
            return {
                "success": True,
                "chunks_added": added_chunks,
                "total_chunks": len(chunks)
            }
            
        except Exception as e:
            logger.error(f"Error adding file content to vector store: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_content(
        self,
        query: str,
        user_id: Optional[int] = None,
        categories: Optional[List[str]] = None,
        file_types: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search content in vector store."""
        if not self.client or not self.embeddings:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.embeddings.embed_query(query)
            
            # Build where filter
            where_conditions = []
            
            if user_id:
                where_conditions.append({
                    "path": ["uploadedBy"],
                    "operator": "Equal",
                    "valueInt": user_id
                })
            
            if categories:
                category_conditions = []
                for category in categories:
                    category_conditions.append({
                        "path": ["category"],
                        "operator": "Equal",
                        "valueString": category
                    })
                
                if len(category_conditions) > 1:
                    where_conditions.append({
                        "operator": "Or",
                        "operands": category_conditions
                    })
                else:
                    where_conditions.extend(category_conditions)
            
            if file_types:
                type_conditions = []
                for file_type in file_types:
                    type_conditions.append({
                        "path": ["fileType"],
                        "operator": "Equal",
                        "valueString": file_type
                    })
                
                if len(type_conditions) > 1:
                    where_conditions.append({
                        "operator": "Or",
                        "operands": type_conditions
                    })
                else:
                    where_conditions.extend(type_conditions)
            
            # Combine conditions
            where_filter = None
            if len(where_conditions) > 1:
                where_filter = {
                    "operator": "And",
                    "operands": where_conditions
                }
            elif len(where_conditions) == 1:
                where_filter = where_conditions[0]
            
            # Perform search
            search_params = {
                "class_name": "FileContent",
                "query_properties": ["content", "fileName"],
                "vector": query_embedding,
                "limit": limit,
                "with_additional": ["distance", "certainty"]
            }
            
            if where_filter:
                search_params["where"] = where_filter
            
            result = self.client.query.get(**search_params).do()
            
            # Process results
            search_results = []
            if result.get("data", {}).get("Get", {}).get("FileContent"):
                for item in result["data"]["Get"]["FileContent"]:
                    search_results.append({
                        "content": item.get("content", ""),
                        "file_id": item.get("fileId", ""),
                        "file_name": item.get("fileName", ""),
                        "chunk_index": item.get("chunkIndex", 0),
                        "category": item.get("category", ""),
                        "file_type": item.get("fileType", ""),
                        "uploaded_at": item.get("uploadedAt", ""),
                        "keywords": item.get("keywords", []),
                        "distance": item.get("_additional", {}).get("distance", 1.0),
                        "certainty": item.get("_additional", {}).get("certainty", 0.0)
                    })
            
            return search_results
            
        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            return []
    
    async def delete_file_content(self, file_id: str) -> bool:
        """Delete all content for a specific file."""
        if not self.client:
            return False
        
        try:
            result = self.client.data_object.delete(
                class_name="FileContent",
                where={
                    "path": ["fileId"],
                    "operator": "Equal",
                    "valueString": file_id
                }
            )
            
            return result.get("successful", 0) > 0
            
        except Exception as e:
            logger.error(f"Error deleting file content: {e}")
            return False
    
    async def add_wms_knowledge(
        self,
        title: str,
        content: str,
        category: str,
        subcategory: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source: str = "manual"
    ) -> bool:
        """Add WMS knowledge entry."""
        if not self.client or not self.embeddings:
            return False
        
        try:
            # Generate embedding
            embedding = self.embeddings.embed_query(f"{title} {content}")
            
            # Prepare object
            obj = {
                "title": title,
                "content": content,
                "category": category,
                "subcategory": subcategory or "",
                "tags": tags or [],
                "source": source,
                "createdAt": datetime.utcnow().isoformat(),
                "updatedAt": datetime.utcnow().isoformat()
            }
            
            # Insert object
            result = self.client.data_object.create(
                data_object=obj,
                class_name="WMSKnowledge",
                vector=embedding
            )
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error adding WMS knowledge: {e}")
            return False
    
    async def search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search WMS knowledge base."""
        if not self.client or not self.embeddings:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.embeddings.embed_query(query)
            
            # Build search
            search_params = {
                "class_name": "WMSKnowledge",
                "query_properties": ["title", "content"],
                "vector": query_embedding,
                "limit": limit,
                "with_additional": ["distance", "certainty"]
            }
            
            if category:
                search_params["where"] = {
                    "path": ["category"],
                    "operator": "Equal",
                    "valueString": category
                }
            
            result = self.client.query.get(**search_params).do()
            
            # Process results
            knowledge_results = []
            if result.get("data", {}).get("Get", {}).get("WMSKnowledge"):
                for item in result["data"]["Get"]["WMSKnowledge"]:
                    knowledge_results.append({
                        "title": item.get("title", ""),
                        "content": item.get("content", ""),
                        "category": item.get("category", ""),
                        "subcategory": item.get("subcategory", ""),
                        "tags": item.get("tags", []),
                        "source": item.get("source", ""),
                        "distance": item.get("_additional", {}).get("distance", 1.0),
                        "certainty": item.get("_additional", {}).get("certainty", 0.0)
                    })
            
            return knowledge_results
            
        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return []
    
    async def store_conversation_context(
        self,
        question: str,
        answer: str,
        agent_id: str,
        category: str,
        user_id: int,
        rating: Optional[int] = None
    ) -> bool:
        """Store conversation context for learning."""
        if not self.client or not self.embeddings:
            return False
        
        try:
            # Generate embedding from question-answer pair
            combined_text = f"Q: {question} A: {answer}"
            embedding = self.embeddings.embed_query(combined_text)
            
            # Prepare object
            obj = {
                "question": question,
                "answer": answer,
                "agentId": agent_id,
                "category": category,
                "userId": user_id,
                "rating": rating or 0,
                "createdAt": datetime.utcnow().isoformat()
            }
            
            # Insert object
            result = self.client.data_object.create(
                data_object=obj,
                class_name="ConversationContext",
                vector=embedding
            )
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error storing conversation context: {e}")
            return False
    
    async def get_similar_conversations(
        self,
        query: str,
        agent_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Get similar conversations for context."""
        if not self.client or not self.embeddings:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.embeddings.embed_query(query)
            
            # Build where filter
            where_conditions = []
            
            if agent_id:
                where_conditions.append({
                    "path": ["agentId"],
                    "operator": "Equal",
                    "valueString": agent_id
                })
            
            if category:
                where_conditions.append({
                    "path": ["category"],
                    "operator": "Equal",
                    "valueString": category
                })
            
            # Combine conditions
            where_filter = None
            if len(where_conditions) > 1:
                where_filter = {
                    "operator": "And",
                    "operands": where_conditions
                }
            elif len(where_conditions) == 1:
                where_filter = where_conditions[0]
            
            # Perform search
            search_params = {
                "class_name": "ConversationContext",
                "query_properties": ["question", "answer"],
                "vector": query_embedding,
                "limit": limit,
                "with_additional": ["distance", "certainty"]
            }
            
            if where_filter:
                search_params["where"] = where_filter
            
            result = self.client.query.get(**search_params).do()
            
            # Process results
            conversation_results = []
            if result.get("data", {}).get("Get", {}).get("ConversationContext"):
                for item in result["data"]["Get"]["ConversationContext"]:
                    conversation_results.append({
                        "question": item.get("question", ""),
                        "answer": item.get("answer", ""),
                        "agent_id": item.get("agentId", ""),
                        "category": item.get("category", ""),
                        "rating": item.get("rating", 0),
                        "distance": item.get("_additional", {}).get("distance", 1.0),
                        "certainty": item.get("_additional", {}).get("certainty", 0.0)
                    })
            
            return conversation_results
            
        except Exception as e:
            logger.error(f"Error getting similar conversations: {e}")
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        if not self.client:
            return {}
        
        try:
            stats = {}
            
            # Get object counts
            for class_name in ["FileContent", "WMSKnowledge", "ConversationContext"]:
                try:
                    result = self.client.query.aggregate(class_name).with_meta_count().do()
                    count = result.get("data", {}).get("Aggregate", {}).get(class_name, [{}])[0].get("meta", {}).get("count", 0)
                    stats[f"{class_name.lower()}_count"] = count
                except Exception as e:
                    logger.error(f"Error getting count for {class_name}: {e}")
                    stats[f"{class_name.lower()}_count"] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting vector store stats: {e}")
            return {}
    
    def is_healthy(self) -> bool:
        """Check if Weaviate is healthy."""
        try:
            return self.client and self.client.is_ready()
        except Exception:
            return False

# Initialize global Weaviate manager
weaviate_manager = WeaviateManager()