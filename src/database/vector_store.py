"""
Weaviate vector database integration for semantic search and knowledge storage.
Handles all vector operations including schema creation, data storage, and retrieval.
"""

import json
import uuid
from typing import Any, Dict, List, Optional, Tuple

import weaviate
from weaviate.classes.config import Configure, Property, DataType
from weaviate.exceptions import WeaviateException

from ..core.config import get_database_settings
from ..core.logging import LoggerMixin


class WeaviateManager(LoggerMixin):
    """Manages Weaviate vector database operations"""
    
    def __init__(self):
        super().__init__()
        self.settings = get_database_settings()
        self._client = None
        self._schema_initialized = False
    
    def _get_client(self) -> weaviate.Client:
        """Get Weaviate client with proper configuration"""
        if self._client is None:
            try:
                # Configure authentication if API key is provided
                auth_config = None
                if self.settings.weaviate_api_key:
                    auth_config = weaviate.AuthApiKey(api_key=self.settings.weaviate_api_key)
                
                self._client = weaviate.Client(
                    url=str(self.settings.weaviate_url),
                    auth_client_secret=auth_config,
                    timeout_config=(5, 60),  # (connection, read) timeout in seconds
                    additional_headers={
                        "X-OpenAI-Api-Key": self._get_openai_key()  # For OpenAI embedding
                    }
                )
                
                # Test connection
                if self._client.is_ready():
                    self.log_info("Weaviate client connected successfully")
                else:
                    raise ConnectionError("Weaviate is not ready")
                    
            except Exception as e:
                self.log_error(f"Failed to connect to Weaviate: {e}")
                raise
        
        return self._client
    
    def _get_openai_key(self) -> str:
        """Get OpenAI API key for embeddings"""
        from ..core.config import get_azure_openai_settings
        azure_settings = get_azure_openai_settings()
        return azure_settings.api_key
    
    async def initialize_schema(self) -> None:
        """Initialize Weaviate schema with all WMS collections"""
        if self._schema_initialized:
            return
        
        try:
            client = self._get_client()
            
            # Delete existing schema if it exists (for development)
            # In production, use migrations instead
            if client.schema.exists():
                client.schema.delete_all()
                self.log_warning("Existing Weaviate schema deleted")
            
            # Create schema for all WMS categories
            schema_classes = self._get_schema_classes()
            
            for class_config in schema_classes:
                try:
                    client.schema.create_class(class_config)
                    self.log_info(f"Created Weaviate class: {class_config['class']}")
                except WeaviateException as e:
                    if "already exists" in str(e):
                        self.log_warning(f"Class {class_config['class']} already exists")
                    else:
                        raise
            
            self._schema_initialized = True
            self.log_info("Weaviate schema initialized successfully")
            
        except Exception as e:
            self.log_error(f"Failed to initialize Weaviate schema: {e}")
            raise
    
    def _get_schema_classes(self) -> List[Dict[str, Any]]:
        """Get schema configuration for all WMS classes"""
        return [
            {
                "class": "WMSKnowledge",
                "description": "General WMS knowledge base for all categories",
                "vectorizer": "text2vec-openai",
                "moduleConfig": {
                    "text2vec-openai": {
                        "model": "text-embedding-ada-002",
                        "modelVersion": "002",
                        "type": "text"
                    }
                },
                "properties": [
                    {
                        "name": "category",
                        "dataType": ["string"],
                        "description": "WMS category (1-16)"
                    },
                    {
                        "name": "sub_category",
                        "dataType": ["string"],
                        "description": "Sub-category type (functional, technical, configuration, relationships, notes)"
                    },
                    {
                        "name": "content",
                        "dataType": ["text"],
                        "description": "Knowledge content"
                    },
                    {
                        "name": "keywords",
                        "dataType": ["string[]"],
                        "description": "Related keywords"
                    },
                    {
                        "name": "postgres_id",
                        "dataType": ["string"],
                        "description": "Linked PostgreSQL record ID"
                    },
                    {
                        "name": "confidence_score",
                        "dataType": ["number"],
                        "description": "Content confidence score"
                    },
                    {
                        "name": "data_format",
                        "dataType": ["string"],
                        "description": "Original data format (text, image, audio, video)"
                    },
                    {
                        "name": "metadata",
                        "dataType": ["object"],
                        "description": "Additional metadata"
                    }
                ]
            },
            {
                "class": "LocationsKnowledge",
                "description": "Location management specific knowledge",
                "vectorizer": "text2vec-openai",
                "moduleConfig": {
                    "text2vec-openai": {
                        "model": "text-embedding-ada-002",
                        "modelVersion": "002",
                        "type": "text"
                    }
                },
                "properties": [
                    {
                        "name": "location_concept",
                        "dataType": ["string"],
                        "description": "Location-related concept"
                    },
                    {
                        "name": "functional_description",
                        "dataType": ["text"],
                        "description": "Functional aspects of location management"
                    },
                    {
                        "name": "technical_specs",
                        "dataType": ["text"],
                        "description": "Technical specifications"
                    },
                    {
                        "name": "configuration_guide",
                        "dataType": ["text"],
                        "description": "Configuration guidance"
                    },
                    {
                        "name": "relationships",
                        "dataType": ["text"],
                        "description": "Relationships with other modules"
                    },
                    {
                        "name": "best_practices",
                        "dataType": ["text"],
                        "description": "Best practices and recommendations"
                    },
                    {
                        "name": "postgres_location_id",
                        "dataType": ["string"],
                        "description": "Linked PostgreSQL location ID"
                    }
                ]
            },
            {
                "class": "ItemsKnowledge",
                "description": "Item management specific knowledge",
                "vectorizer": "text2vec-openai",
                "moduleConfig": {
                    "text2vec-openai": {
                        "model": "text-embedding-ada-002",
                        "modelVersion": "002",
                        "type": "text"
                    }
                },
                "properties": [
                    {
                        "name": "item_concept",
                        "dataType": ["string"],
                        "description": "Item-related concept"
                    },
                    {
                        "name": "item_attributes",
                        "dataType": ["text"],
                        "description": "Item attributes and characteristics"
                    },
                    {
                        "name": "classification_rules",
                        "dataType": ["text"],
                        "description": "Item classification rules"
                    },
                    {
                        "name": "storage_requirements",
                        "dataType": ["text"],
                        "description": "Storage requirements and handling"
                    },
                    {
                        "name": "supplier_relationships",
                        "dataType": ["text"],
                        "description": "Supplier and vendor relationships"
                    },
                    {
                        "name": "postgres_item_id",
                        "dataType": ["string"],
                        "description": "Linked PostgreSQL item ID"
                    }
                ]
            },
            {
                "class": "InventoryKnowledge",
                "description": "Inventory management specific knowledge",
                "vectorizer": "text2vec-openai",
                "moduleConfig": {
                    "text2vec-openai": {
                        "model": "text-embedding-ada-002",
                        "modelVersion": "002",
                        "type": "text"
                    }
                },
                "properties": [
                    {
                        "name": "inventory_concept",
                        "dataType": ["string"],
                        "description": "Inventory-related concept"
                    },
                    {
                        "name": "tracking_methods",
                        "dataType": ["text"],
                        "description": "Inventory tracking methodologies"
                    },
                    {
                        "name": "accuracy_procedures",
                        "dataType": ["text"],
                        "description": "Accuracy maintenance procedures"
                    },
                    {
                        "name": "movement_patterns",
                        "dataType": ["text"],
                        "description": "Inventory movement patterns"
                    },
                    {
                        "name": "valuation_methods",
                        "dataType": ["text"],
                        "description": "Inventory valuation methods"
                    },
                    {
                        "name": "postgres_inventory_id",
                        "dataType": ["string"],
                        "description": "Linked PostgreSQL inventory ID"
                    }
                ]
            },
            {
                "class": "DataCategorizationKnowledge",
                "description": "Data categorization and validation knowledge",
                "vectorizer": "text2vec-openai",
                "moduleConfig": {
                    "text2vec-openai": {
                        "model": "text-embedding-ada-002",
                        "modelVersion": "002",
                        "type": "text"
                    }
                },
                "properties": [
                    {
                        "name": "categorization_rule",
                        "dataType": ["string"],
                        "description": "Data categorization rule"
                    },
                    {
                        "name": "classification_pattern",
                        "dataType": ["text"],
                        "description": "Classification patterns and logic"
                    },
                    {
                        "name": "validation_criteria",
                        "dataType": ["text"],
                        "description": "Validation criteria and rules"
                    },
                    {
                        "name": "multi_category_logic",
                        "dataType": ["text"],
                        "description": "Multi-category assignment logic"
                    },
                    {
                        "name": "data_quality_standards",
                        "dataType": ["text"],
                        "description": "Data quality standards and best practices"
                    },
                    {
                        "name": "postgres_categorization_id",
                        "dataType": ["string"],
                        "description": "Linked PostgreSQL categorization ID"
                    }
                ]
            }
        ]
    
    async def store_knowledge(self, class_name: str, data: Dict[str, Any], 
                            object_id: Optional[str] = None) -> str:
        """Store knowledge in Weaviate with automatic embedding generation"""
        try:
            client = self._get_client()
            
            # Generate UUID if not provided
            if object_id is None:
                object_id = str(uuid.uuid4())
            
            # Store the object
            client.data_object.create(
                data_object=data,
                class_name=class_name,
                uuid=object_id
            )
            
            self.log_info(f"Stored knowledge in {class_name}: {object_id}")
            return object_id
            
        except Exception as e:
            self.log_error(f"Failed to store knowledge in {class_name}: {e}")
            raise
    
    async def search_knowledge(self, query: str, class_name: Optional[str] = None,
                             limit: int = 10, certainty: float = 0.7) -> List[Dict[str, Any]]:
        """Search knowledge using semantic similarity"""
        try:
            client = self._get_client()
            
            # Build the query
            if class_name:
                where_filter = {"path": ["class"], "operator": "Equal", "valueString": class_name}
            else:
                where_filter = None
            
            # Perform semantic search
            result = (
                client.query
                .get(class_name or "WMSKnowledge")
                .with_near_text({"concepts": [query], "certainty": certainty})
                .with_limit(limit)
                .with_additional(["certainty", "id"])
                .do()
            )
            
            # Extract results
            results = []
            if "data" in result and "Get" in result["data"]:
                class_key = class_name or "WMSKnowledge"
                if class_key in result["data"]["Get"]:
                    for item in result["data"]["Get"][class_key]:
                        results.append({
                            "id": item["_additional"]["id"],
                            "certainty": item["_additional"]["certainty"],
                            "data": {k: v for k, v in item.items() if k != "_additional"}
                        })
            
            self.log_info(f"Found {len(results)} results for query: {query}")
            return results
            
        except Exception as e:
            self.log_error(f"Failed to search knowledge: {e}")
            raise
    
    async def hybrid_search(self, query: str, class_name: Optional[str] = None,
                          alpha: float = 0.75, limit: int = 10) -> List[Dict[str, Any]]:
        """Perform hybrid search combining semantic and keyword search"""
        try:
            client = self._get_client()
            
            # Perform hybrid search
            result = (
                client.query
                .get(class_name or "WMSKnowledge")
                .with_hybrid(query=query, alpha=alpha)
                .with_limit(limit)
                .with_additional(["score", "id"])
                .do()
            )
            
            # Extract results
            results = []
            if "data" in result and "Get" in result["data"]:
                class_key = class_name or "WMSKnowledge"
                if class_key in result["data"]["Get"]:
                    for item in result["data"]["Get"][class_key]:
                        results.append({
                            "id": item["_additional"]["id"],
                            "score": item["_additional"]["score"],
                            "data": {k: v for k, v in item.items() if k != "_additional"}
                        })
            
            self.log_info(f"Hybrid search found {len(results)} results for: {query}")
            return results
            
        except Exception as e:
            self.log_error(f"Failed to perform hybrid search: {e}")
            raise
    
    async def get_by_id(self, class_name: str, object_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve object by ID"""
        try:
            client = self._get_client()
            
            result = client.data_object.get_by_id(
                uuid=object_id,
                class_name=class_name
            )
            
            if result:
                self.log_info(f"Retrieved object {object_id} from {class_name}")
                return result
            else:
                self.log_warning(f"Object {object_id} not found in {class_name}")
                return None
                
        except Exception as e:
            self.log_error(f"Failed to retrieve object {object_id}: {e}")
            raise
    
    async def update_knowledge(self, class_name: str, object_id: str, 
                             data: Dict[str, Any]) -> bool:
        """Update existing knowledge object"""
        try:
            client = self._get_client()
            
            client.data_object.update(
                data_object=data,
                class_name=class_name,
                uuid=object_id
            )
            
            self.log_info(f"Updated object {object_id} in {class_name}")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to update object {object_id}: {e}")
            return False
    
    async def delete_knowledge(self, class_name: str, object_id: str) -> bool:
        """Delete knowledge object"""
        try:
            client = self._get_client()
            
            client.data_object.delete(
                uuid=object_id,
                class_name=class_name
            )
            
            self.log_info(f"Deleted object {object_id} from {class_name}")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to delete object {object_id}: {e}")
            return False
    
    async def create_bidirectional_link(self, postgres_id: str, vector_id: str,
                                      table_name: str, class_name: str) -> Tuple[str, str]:
        """Create bidirectional link between PostgreSQL and Weaviate"""
        try:
            # Store the link information in both directions
            link_data = {
                "postgres_table": table_name,
                "postgres_id": postgres_id,
                "vector_class": class_name,
                "vector_id": vector_id,
                "link_created": str(datetime.utcnow()),
                "link_type": "bidirectional"
            }
            
            # Create link object in Weaviate
            link_id = await self.store_knowledge("DataLinks", link_data)
            
            self.log_info(f"Created bidirectional link: {postgres_id} <-> {vector_id}")
            return postgres_id, vector_id
            
        except Exception as e:
            self.log_error(f"Failed to create bidirectional link: {e}")
            raise
    
    async def get_linked_records(self, postgres_id: str = None, 
                               vector_id: str = None) -> List[Dict[str, Any]]:
        """Get linked records from bidirectional links"""
        try:
            if postgres_id:
                # Find vector records linked to this PostgreSQL record
                query = f"postgres_id:{postgres_id}"
            elif vector_id:
                # Find PostgreSQL records linked to this vector record
                query = f"vector_id:{vector_id}"
            else:
                raise ValueError("Either postgres_id or vector_id must be provided")
            
            results = await self.search_knowledge(query, "DataLinks")
            
            self.log_info(f"Found {len(results)} linked records")
            return results
            
        except Exception as e:
            self.log_error(f"Failed to get linked records: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Weaviate health and connectivity"""
        try:
            client = self._get_client()
            
            # Check if Weaviate is ready
            is_ready = client.is_ready()
            
            # Get cluster info
            cluster_info = client.cluster.get_nodes_status()
            
            # Count objects in main class
            try:
                object_count = client.query.aggregate("WMSKnowledge").with_meta_count().do()
                total_objects = object_count["data"]["Aggregate"]["WMSKnowledge"][0]["meta"]["count"]
            except:
                total_objects = 0
            
            return {
                "status": "healthy" if is_ready else "unhealthy",
                "is_ready": is_ready,
                "cluster_status": cluster_info,
                "total_objects": total_objects,
                "schema_initialized": self._schema_initialized
            }
            
        except Exception as e:
            self.log_error(f"Weaviate health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "is_ready": False,
                "schema_initialized": False
            }
    
    async def close(self):
        """Close Weaviate client connection"""
        if self._client:
            # Weaviate client doesn't have explicit close method
            # Just clear the reference
            self._client = None
            self.log_info("Weaviate client connection closed")


# Global Weaviate manager instance
_weaviate_manager = None


def get_weaviate_manager() -> WeaviateManager:
    """Get global Weaviate manager instance"""
    global _weaviate_manager
    if _weaviate_manager is None:
        _weaviate_manager = WeaviateManager()
    return _weaviate_manager