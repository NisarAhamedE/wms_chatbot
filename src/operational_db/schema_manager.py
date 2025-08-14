"""
Operational Database Schema Manager
Handles extraction, storage, and vectorization of MS SQL database schemas for intelligent SQL generation.
"""

import json
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import asyncio
from dataclasses import dataclass, field

import pymssql
from sqlalchemy import create_engine, MetaData, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from ..core.config import get_settings
from ..core.logging import LoggerMixin
from ..database.vector_store import get_weaviate_manager


@dataclass
class TableSchema:
    """Represents a database table schema"""
    schema_name: str
    table_name: str
    columns: List[Dict[str, Any]]
    primary_keys: List[str]
    foreign_keys: List[Dict[str, Any]]
    indexes: List[Dict[str, Any]]
    description: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    row_count: Optional[int] = None
    sample_data: Optional[List[Dict]] = None
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "schema_name": self.schema_name,
            "table_name": self.table_name,
            "full_name": f"{self.schema_name}.{self.table_name}",
            "columns": self.columns,
            "primary_keys": self.primary_keys,
            "foreign_keys": self.foreign_keys,
            "indexes": self.indexes,
            "description": self.description,
            "category": self.category,
            "sub_category": self.sub_category,
            "row_count": self.row_count,
            "sample_data": self.sample_data,
            "relationships": self.relationships
        }
    
    def get_column_names(self) -> List[str]:
        """Get list of column names"""
        return [col["name"] for col in self.columns]
    
    def get_searchable_text(self) -> str:
        """Generate searchable text for vectorization"""
        text_parts = [
            f"Table: {self.schema_name}.{self.table_name}",
            f"Category: {self.category or 'Unknown'}",
            f"Description: {self.description or 'No description'}",
            f"Columns: {', '.join(self.get_column_names())}",
        ]
        
        # Add column details
        for col in self.columns:
            text_parts.append(
                f"Column {col['name']}: {col.get('type', 'unknown')} "
                f"{col.get('description', '')}"
            )
        
        # Add relationship information
        for rel in self.relationships:
            text_parts.append(
                f"Related to {rel['referenced_table']} via {rel['column']}"
            )
        
        return "\n".join(text_parts)


class OperationalSchemaManager(LoggerMixin):
    """Manages operational database schema extraction and vectorization"""
    
    def __init__(self, connection_string: str = None):
        super().__init__()
        self.connection_string = connection_string
        self.engine: Optional[Engine] = None
        self.metadata = MetaData()
        self.vector_manager = get_weaviate_manager()
        self.schemas: Dict[str, TableSchema] = {}
        
        # WMS Category mappings for tables
        self.category_mappings = {
            # Locations
            "location": "locations",
            "bin": "locations",
            "zone": "locations",
            "aisle": "locations",
            "warehouse": "locations",
            
            # Items
            "item": "items",
            "product": "items",
            "sku": "items",
            "material": "items",
            "part": "items",
            
            # Inventory
            "inventory": "inventory_management",
            "stock": "inventory_management",
            "balance": "inventory_management",
            "on_hand": "inventory_management",
            
            # Receiving
            "receipt": "receiving",
            "receiving": "receiving",
            "asn": "receiving",
            "inbound": "receiving",
            "purchase_order": "receiving",
            
            # Putaway
            "putaway": "locating_putaway",
            "put_away": "locating_putaway",
            "placement": "locating_putaway",
            
            # Work
            "work": "work",
            "task": "work",
            "assignment": "work",
            "labor": "work",
            
            # Cycle Counting
            "cycle_count": "cycle_counting",
            "count": "cycle_counting",
            "audit": "cycle_counting",
            
            # Wave Management
            "wave": "wave_management",
            "batch": "wave_management",
            
            # Allocation
            "allocation": "allocation",
            "reservation": "allocation",
            
            # Replenishment
            "replenishment": "replenishment",
            "replen": "replenishment",
            
            # Picking
            "pick": "picking",
            "order": "picking",
            
            # Packing
            "pack": "packing",
            "carton": "packing",
            "container": "packing",
            
            # Shipping
            "ship": "shipping",
            "outbound": "shipping",
            "carrier": "shipping",
            "freight": "shipping",
            
            # Yard Management
            "yard": "yard_management",
            "dock": "yard_management",
            "trailer": "yard_management",
            "appointment": "yard_management"
        }
    
    def set_connection(self, connection_string: str):
        """Set or update database connection"""
        try:
            self.connection_string = connection_string
            # Create engine with NullPool to avoid connection pooling issues
            self.engine = create_engine(
                connection_string, 
                poolclass=NullPool,
                echo=False
            )
            self.log_info("Database connection established")
            return True
        except Exception as e:
            self.log_error(f"Failed to establish database connection: {e}")
            return False
    
    async def extract_schema(self, include_sample_data: bool = True, 
                           sample_size: int = 5) -> Dict[str, TableSchema]:
        """Extract complete database schema"""
        if not self.engine:
            raise ValueError("Database connection not established")
        
        try:
            self.log_info("Starting schema extraction")
            inspector = inspect(self.engine)
            
            # Get all schemas
            schemas = inspector.get_schema_names()
            
            for schema_name in schemas:
                # Skip system schemas
                if schema_name in ['sys', 'INFORMATION_SCHEMA', 'guest']:
                    continue
                
                # Get tables in schema
                tables = inspector.get_table_names(schema=schema_name)
                
                for table_name in tables:
                    try:
                        table_schema = await self._extract_table_schema(
                            inspector, schema_name, table_name, 
                            include_sample_data, sample_size
                        )
                        
                        # Categorize table
                        table_schema.category = self._categorize_table(table_name)
                        
                        # Store schema
                        full_name = f"{schema_name}.{table_name}"
                        self.schemas[full_name] = table_schema
                        
                        self.log_info(f"Extracted schema for {full_name}")
                        
                    except Exception as e:
                        self.log_warning(f"Failed to extract schema for {schema_name}.{table_name}: {e}")
            
            # Build relationships
            self._build_relationships()
            
            self.log_info(f"Schema extraction complete. Extracted {len(self.schemas)} tables")
            return self.schemas
            
        except Exception as e:
            self.log_error(f"Schema extraction failed: {e}")
            raise
    
    async def _extract_table_schema(self, inspector, schema_name: str, 
                                   table_name: str, include_sample_data: bool,
                                   sample_size: int) -> TableSchema:
        """Extract schema for a single table"""
        # Get columns
        columns = []
        for col in inspector.get_columns(table_name, schema=schema_name):
            column_info = {
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "default": col.get("default"),
                "autoincrement": col.get("autoincrement", False),
                "comment": col.get("comment", "")
            }
            columns.append(column_info)
        
        # Get primary keys
        pk_constraint = inspector.get_pk_constraint(table_name, schema=schema_name)
        primary_keys = pk_constraint.get("constrained_columns", []) if pk_constraint else []
        
        # Get foreign keys
        foreign_keys = []
        for fk in inspector.get_foreign_keys(table_name, schema=schema_name):
            foreign_keys.append({
                "name": fk.get("name"),
                "columns": fk.get("constrained_columns", []),
                "referenced_schema": fk.get("referred_schema"),
                "referenced_table": fk.get("referred_table"),
                "referenced_columns": fk.get("referred_columns", [])
            })
        
        # Get indexes
        indexes = []
        for idx in inspector.get_indexes(table_name, schema=schema_name):
            indexes.append({
                "name": idx.get("name"),
                "columns": idx.get("column_names", []),
                "unique": idx.get("unique", False)
            })
        
        # Get row count and sample data
        row_count = None
        sample_data = None
        
        if include_sample_data:
            with self.engine.connect() as conn:
                # Get row count
                count_query = text(f"SELECT COUNT(*) FROM [{schema_name}].[{table_name}]")
                row_count = conn.execute(count_query).scalar()
                
                # Get sample data
                if row_count > 0 and sample_size > 0:
                    sample_query = text(
                        f"SELECT TOP {sample_size} * FROM [{schema_name}].[{table_name}]"
                    )
                    result = conn.execute(sample_query)
                    sample_data = [dict(row._mapping) for row in result]
        
        # Get table description from extended properties (MS SQL specific)
        description = self._get_table_description(schema_name, table_name)
        
        return TableSchema(
            schema_name=schema_name,
            table_name=table_name,
            columns=columns,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys,
            indexes=indexes,
            description=description,
            row_count=row_count,
            sample_data=sample_data
        )
    
    def _get_table_description(self, schema_name: str, table_name: str) -> Optional[str]:
        """Get table description from MS SQL extended properties"""
        try:
            with self.engine.connect() as conn:
                query = text("""
                    SELECT 
                        p.value AS description
                    FROM sys.extended_properties p
                    JOIN sys.tables t ON p.major_id = t.object_id
                    JOIN sys.schemas s ON t.schema_id = s.schema_id
                    WHERE p.class = 1
                        AND p.name = 'MS_Description'
                        AND s.name = :schema_name
                        AND t.name = :table_name
                """)
                
                result = conn.execute(query, {
                    "schema_name": schema_name,
                    "table_name": table_name
                }).first()
                
                return result[0] if result else None
                
        except Exception as e:
            self.log_warning(f"Failed to get table description: {e}")
            return None
    
    def _categorize_table(self, table_name: str) -> str:
        """Categorize table based on name patterns"""
        table_lower = table_name.lower()
        
        for keyword, category in self.category_mappings.items():
            if keyword in table_lower:
                return category
        
        # Default category for uncategorized tables
        return "other_data_categorization"
    
    def _build_relationships(self):
        """Build relationship graph between tables"""
        for table_name, schema in self.schemas.items():
            relationships = []
            
            # Process foreign keys
            for fk in schema.foreign_keys:
                ref_schema = fk.get("referenced_schema", schema.schema_name)
                ref_table = fk["referenced_table"]
                ref_full_name = f"{ref_schema}.{ref_table}"
                
                relationship = {
                    "type": "foreign_key",
                    "column": fk["columns"][0] if fk["columns"] else None,
                    "referenced_table": ref_full_name,
                    "referenced_column": fk["referenced_columns"][0] if fk["referenced_columns"] else None,
                    "relationship_name": fk.get("name", "")
                }
                relationships.append(relationship)
                
                # Add reverse relationship to referenced table
                if ref_full_name in self.schemas:
                    reverse_rel = {
                        "type": "referenced_by",
                        "column": fk["referenced_columns"][0] if fk["referenced_columns"] else None,
                        "referencing_table": table_name,
                        "referencing_column": fk["columns"][0] if fk["columns"] else None,
                        "relationship_name": fk.get("name", "")
                    }
                    self.schemas[ref_full_name].relationships.append(reverse_rel)
            
            schema.relationships = relationships
    
    async def vectorize_schemas(self, batch_size: int = 10) -> bool:
        """Vectorize schemas and store in vector database"""
        try:
            self.log_info(f"Starting schema vectorization for {len(self.schemas)} tables")
            
            # Prepare data for vectorization
            documents = []
            for table_name, schema in self.schemas.items():
                doc = {
                    "id": hashlib.md5(table_name.encode()).hexdigest(),
                    "table_name": table_name,
                    "schema_name": schema.schema_name,
                    "category": schema.category,
                    "description": schema.description or "",
                    "content": schema.get_searchable_text(),
                    "columns": json.dumps(schema.columns),
                    "primary_keys": json.dumps(schema.primary_keys),
                    "foreign_keys": json.dumps(schema.foreign_keys),
                    "relationships": json.dumps(schema.relationships),
                    "row_count": schema.row_count or 0,
                    "indexed_at": datetime.utcnow().isoformat()
                }
                documents.append(doc)
            
            # Store in vector database in batches
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                success = await self.vector_manager.store_documents(
                    documents=batch,
                    class_name="OperationalSchema"
                )
                
                if not success:
                    self.log_error(f"Failed to vectorize batch {i//batch_size + 1}")
                    return False
                
                self.log_info(f"Vectorized batch {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1}")
            
            self.log_info("Schema vectorization complete")
            return True
            
        except Exception as e:
            self.log_error(f"Schema vectorization failed: {e}")
            return False
    
    def get_table_schema(self, table_name: str) -> Optional[TableSchema]:
        """Get schema for a specific table"""
        # Try exact match first
        if table_name in self.schemas:
            return self.schemas[table_name]
        
        # Try case-insensitive match
        for key, schema in self.schemas.items():
            if key.lower() == table_name.lower():
                return schema
        
        # Try partial match (table name without schema)
        for key, schema in self.schemas.items():
            if key.split('.')[-1].lower() == table_name.lower():
                return schema
        
        return None
    
    def get_tables_by_category(self, category: str) -> List[TableSchema]:
        """Get all tables in a specific category"""
        return [
            schema for schema in self.schemas.values()
            if schema.category == category
        ]
    
    def find_related_tables(self, table_name: str, depth: int = 1) -> List[str]:
        """Find tables related to the given table up to specified depth"""
        related = set()
        to_process = {table_name}
        processed = set()
        
        for _ in range(depth):
            next_level = set()
            for current_table in to_process:
                if current_table in processed:
                    continue
                
                processed.add(current_table)
                schema = self.get_table_schema(current_table)
                
                if schema:
                    for rel in schema.relationships:
                        if rel["type"] == "foreign_key":
                            related_table = rel["referenced_table"]
                        elif rel["type"] == "referenced_by":
                            related_table = rel["referencing_table"]
                        else:
                            continue
                        
                        if related_table not in processed:
                            related.add(related_table)
                            next_level.add(related_table)
            
            to_process = next_level
        
        return list(related)
    
    def get_join_path(self, table1: str, table2: str) -> Optional[List[Dict[str, str]]]:
        """Find join path between two tables"""
        # This is a simplified version - in production, use graph algorithms
        schema1 = self.get_table_schema(table1)
        schema2 = self.get_table_schema(table2)
        
        if not schema1 or not schema2:
            return None
        
        # Direct relationship
        for rel in schema1.relationships:
            if rel.get("referenced_table") == table2 or rel.get("referencing_table") == table2:
                return [{
                    "from_table": table1,
                    "to_table": table2,
                    "from_column": rel.get("column") or rel.get("referencing_column"),
                    "to_column": rel.get("referenced_column") or rel.get("column"),
                    "join_type": "INNER JOIN"
                }]
        
        # TODO: Implement multi-hop path finding
        return None
    
    async def search_schemas(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search schemas using vector similarity"""
        results = await self.vector_manager.search_knowledge(
            query=query,
            class_name="OperationalSchema",
            limit=limit,
            certainty=0.7
        )
        
        enriched_results = []
        for result in results:
            data = result.get("data", {})
            enriched_results.append({
                "table_name": data.get("table_name"),
                "schema_name": data.get("schema_name"),
                "category": data.get("category"),
                "description": data.get("description"),
                "columns": json.loads(data.get("columns", "[]")),
                "certainty": result.get("certainty", 0)
            })
        
        return enriched_results
    
    def generate_column_mapping(self, table_name: str, user_terms: List[str]) -> Dict[str, str]:
        """Map user terms to actual column names"""
        schema = self.get_table_schema(table_name)
        if not schema:
            return {}
        
        mapping = {}
        columns = schema.get_column_names()
        
        for term in user_terms:
            term_lower = term.lower()
            
            # Exact match
            for col in columns:
                if col.lower() == term_lower:
                    mapping[term] = col
                    break
            
            # Partial match
            if term not in mapping:
                for col in columns:
                    if term_lower in col.lower() or col.lower() in term_lower:
                        mapping[term] = col
                        break
            
            # Common abbreviations
            if term not in mapping:
                abbreviations = {
                    "qty": ["quantity", "qty"],
                    "desc": ["description", "desc"],
                    "id": ["_id", "id"],
                    "num": ["number", "num", "no"],
                    "dt": ["date", "datetime", "dt"],
                    "amt": ["amount", "amt"],
                    "loc": ["location", "loc"],
                    "wh": ["warehouse", "wh"]
                }
                
                for abbr, variations in abbreviations.items():
                    if term_lower in variations:
                        for col in columns:
                            col_lower = col.lower()
                            if any(v in col_lower for v in variations):
                                mapping[term] = col
                                break
                        if term in mapping:
                            break
        
        return mapping
    
    def export_schema_documentation(self, output_file: str = "schema_documentation.json"):
        """Export schema documentation to file"""
        documentation = {
            "extracted_at": datetime.utcnow().isoformat(),
            "database": self.connection_string.split('/')[-1] if self.connection_string else "unknown",
            "tables_count": len(self.schemas),
            "categories": {},
            "tables": {}
        }
        
        # Group by category
        for table_name, schema in self.schemas.items():
            category = schema.category or "uncategorized"
            if category not in documentation["categories"]:
                documentation["categories"][category] = []
            documentation["categories"][category].append(table_name)
            
            # Add table details
            documentation["tables"][table_name] = schema.to_dict()
        
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(documentation, f, indent=2, default=str)
        
        self.log_info(f"Schema documentation exported to {output_file}")
        return documentation


# Global instance
_schema_manager: Optional[OperationalSchemaManager] = None


def get_schema_manager(connection_string: str = None) -> OperationalSchemaManager:
    """Get or create global schema manager instance"""
    global _schema_manager
    
    if _schema_manager is None:
        _schema_manager = OperationalSchemaManager(connection_string)
    elif connection_string and _schema_manager.connection_string != connection_string:
        _schema_manager.set_connection(connection_string)
    
    return _schema_manager


async def initialize_operational_schema(connection_string: str, 
                                       include_sample_data: bool = True) -> bool:
    """Initialize operational schema extraction and vectorization"""
    try:
        manager = get_schema_manager(connection_string)
        
        # Extract schemas
        schemas = await manager.extract_schema(include_sample_data=include_sample_data)
        
        if not schemas:
            return False
        
        # Vectorize schemas
        success = await manager.vectorize_schemas()
        
        return success
        
    except Exception as e:
        print(f"Failed to initialize operational schema: {e}")
        return False