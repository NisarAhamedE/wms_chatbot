import json
import os
import threading
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import chromadb
from chromadb.config import Settings
import uuid
import psycopg2
from psycopg2.pool import SimpleConnectionPool

from .logger import LoggerMixin
from .config_manager import ConfigManager

class DatabaseManager(LoggerMixin):
    """
    Manages PostgreSQL (TimescaleDB) + ChromaDB for the WMS application
    """
    
    def __init__(self, sqlite_path: str = "data/wms_screenshots.db", 
                 chroma_path: str = "data/chroma_db",
                 max_connections: int = 10,
                 config_manager: ConfigManager = None):
        super().__init__()
        
        self.config_manager = config_manager or ConfigManager()
        self.db_config = self.config_manager.get_database_config()
        
        self.chroma_path = Path(chroma_path)
        self.max_connections = max_connections
        
        # PostgreSQL pool
        pg = self.db_config.get("postgres", {})
        self._pg_pool = SimpleConnectionPool(
            pg.get("pool_min", 1),
            pg.get("pool_max", self.max_connections),
            dsn=self.config_manager.get_postgres_dsn()
        )
        
        # Initialize Postgres schema
        self._init_postgres()
        
        # Initialize ChromaDB flags
        self._chroma_initialized = False
        self._chroma_init_lock = threading.Lock()
        
        # Ensure directories exist
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB in background thread
        threading.Thread(target=self._init_chromadb_async, daemon=True).start()
        
        self.log_info("Database manager initialized for PostgreSQL + ChromaDB")
    
    def _pg_conn(self):
        """Get a PostgreSQL connection from the pool."""
        return self._pg_pool.getconn()

    def _execute_pg(self, sql: str, params: tuple = None, fetch: bool = False):
        """Execute SQL against PostgreSQL with automatic commit and optional fetch."""
        conn = self._pg_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params or ())
                    if fetch:
                        return cur.fetchall()
                    return None
        except Exception as e:
            self.log_error(f"PostgreSQL execution error: {e}")
            raise
        finally:
            self._pg_pool.putconn(conn)
    
    def _init_postgres(self):
        """Initialize PostgreSQL (enable Timescale, create tables)."""
        try:
            self._execute_pg("CREATE EXTENSION IF NOT EXISTS timescaledb;")
            self.create_tables()
        except Exception as e:
            self.log_error(f"Failed to initialize PostgreSQL database: {e}")
            raise
    
    def _init_chromadb_async(self):
        """Initialize ChromaDB asynchronously"""
        try:
            with self._chroma_init_lock:
                if self._chroma_initialized:
                    return
                
                # Configure ChromaDB settings
                settings = {
                    "allow_reset": True,
                    "is_persistent": True,
                    "persist_directory": str(self.chroma_path)
                }
                
                # Initialize client with retry
                max_retries = 3
                retry_delay = 1  # seconds
                
                # Create ChromaDB directory if it doesn't exist
                self.chroma_path.mkdir(parents=True, exist_ok=True)
                
                # Clean up any stale lock files
                lock_file = self.chroma_path / "chroma.lock"
                if lock_file.exists():
                    try:
                        lock_file.unlink()
                        self.log_info("Removed stale ChromaDB lock file")
                    except Exception as e:
                        self.log_error(f"Failed to remove stale lock file: {e}")
                
                # Initialize client
                for attempt in range(max_retries):
                    try:
                        # Create client with minimal settings
                        try:
                            # Try to create persistent client first
                            self.chroma_client = chromadb.PersistentClient(
                                path=str(self.chroma_path),
                                settings=chromadb.Settings(
                                    is_persistent=True,
                                    allow_reset=True,
                                    anonymized_telemetry=False
                                )
                            )
                        except Exception as e:
                            self.log_error(f"Failed to create persistent client: {e}")
                            # Fallback to ephemeral client
                            self.chroma_client = chromadb.EphemeralClient()
                            
                        # Test connection without telemetry
                        try:
                            self.chroma_client._telemetry_enabled = False
                            self.chroma_client.heartbeat()
                            break
                        except Exception as e:
                            self.log_error(f"Failed to test connection: {e}")
                            if attempt == max_retries - 1:
                                raise
                        
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise
                        self.log_error(f"ChromaDB init attempt {attempt + 1} failed: {e}")
                        time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                
                # Get or create collection with retry
                for attempt in range(max_retries):
                    try:
                        # First try to get existing collection
                        try:
                            self.collection = self.chroma_client.get_collection(
                                name="wms_documents"
                            )
                            self.log_info("Retrieved existing ChromaDB collection")
                            break
                        except Exception:
                            # Collection doesn't exist, create new one
                            self.collection = self.chroma_client.create_collection(
                                name="wms_documents",
                                metadata={
                                    "description": "WMS document embeddings",
                                    "created_at": datetime.now().isoformat()
                                }
                            )
                            self.log_info("Created new ChromaDB collection")
                            break
                            
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise
                        self.log_error(f"Collection init attempt {attempt + 1} failed: {e}")
                        time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                
                # Test collection access
                try:
                    self.collection.count()
                    self._chroma_initialized = True
                    self.log_info("ChromaDB initialized successfully")
                except Exception as e:
                    raise Exception(f"Failed to access collection: {e}")
                
        except Exception as e:
            self.log_error(f"Failed to initialize ChromaDB: {e}")
            # Initialize empty collection to prevent errors
            self.collection = None
            self._chroma_initialized = False
            # Raise error to prevent silent failures
            raise
    
    def ensure_chromadb_initialized(self):
        """Ensure ChromaDB is initialized before use"""
        if not self._chroma_initialized:
            with self._chroma_init_lock:
                if not self._chroma_initialized:
                    self._init_chromadb_async()
    
    def init_chromadb(self):
        """Initialize ChromaDB for vector storage (synchronous version)"""
        self._init_chromadb_async()
    
    def create_tables(self):
        """Create PostgreSQL tables if they don't exist (screenshots as hypertable)."""
        # Documents
        self._execute_pg(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                document_id TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size BIGINT,
                content TEXT,
                metadata JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                status TEXT DEFAULT 'processed',
                error_message TEXT
            );
            """
        )
        # Screenshots
        self._execute_pg(
            """
            CREATE TABLE IF NOT EXISTS screenshots (
                id SERIAL PRIMARY KEY,
                screenshot_id TEXT UNIQUE NOT NULL,
                document_id TEXT,
                image_path TEXT NOT NULL,
                page_number INT,
                extracted_text TEXT,
                confidence_score DOUBLE PRECISION,
                processing_time DOUBLE PRECISION,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        self._execute_pg("SELECT create_hypertable('screenshots', 'created_at', if_not_exists => TRUE);")
        # Processing history
        self._execute_pg(
            """
            CREATE TABLE IF NOT EXISTS processing_history (
                id SERIAL PRIMARY KEY,
                document_id TEXT,
                operation TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        # Indexes
        self._execute_pg("CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents (filename);")
        self._execute_pg("CREATE INDEX IF NOT EXISTS idx_documents_file_type ON documents (file_type);")
        self._execute_pg("CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at);")
        self._execute_pg("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents (status);")
        self._execute_pg("CREATE INDEX IF NOT EXISTS idx_documents_combined ON documents (file_type, status, created_at);")
        self._execute_pg("CREATE INDEX IF NOT EXISTS idx_screenshots_document_id ON screenshots (document_id);")
        self._execute_pg("CREATE INDEX IF NOT EXISTS idx_screenshots_created_at ON screenshots (created_at);")
        self._execute_pg("CREATE INDEX IF NOT EXISTS idx_screenshots_confidence ON screenshots (confidence_score);")
        self._execute_pg("CREATE INDEX IF NOT EXISTS idx_processing_history_document_id ON processing_history (document_id);")
        self._execute_pg("CREATE INDEX IF NOT EXISTS idx_processing_history_status ON processing_history (status);")
        self._execute_pg("CREATE INDEX IF NOT EXISTS idx_processing_history_operation ON processing_history (operation);")
        self.log_info("PostgreSQL tables and indexes created successfully")
    
    def store_document(self, file_path: str, content: str, metadata: Dict[str, Any], 
                       validate: bool = True) -> str:
        """
        Store document in both SQLite and ChromaDB with optional validation
        
        Args:
            file_path: Path to the document file
            content: Extracted text content
            metadata: Additional metadata
            validate: Whether to validate consistency after storage
            
        Returns:
            Document ID
        """
        try:
            document_id = str(uuid.uuid4())
            file_path_obj = Path(file_path)
            
            # Prepare document data
            doc_data = {
                'document_id': document_id,
                'filename': file_path_obj.name,
                'file_path': str(file_path_obj.absolute()),
                'file_type': file_path_obj.suffix.lower(),
                'file_size': file_path_obj.stat().st_size if file_path_obj.exists() else 0,
                'content': content,
                'metadata': json.dumps(metadata),
                'status': 'processed'
            }
            
            # Store in both databases
            try:
                # Store in SQLite first (primary database)
                self.store_document_sqlite(doc_data)
                
                # Store in ChromaDB
                self.store_document_chromadb(document_id, content, metadata)
                
                # Validate consistency if requested
                if validate:
                    # Check if document exists in both databases
                    cursor = self._execute_sql(
                        "SELECT COUNT(*) FROM documents WHERE document_id = ?",
                        (document_id,)
                    )
                    sql_exists = cursor.fetchone()[0] > 0
                    
                    vector_exists = bool(self.collection.get(
                        ids=[document_id],
                        include=[]
                    )['ids'])
                    
                    if not sql_exists or not vector_exists:
                        raise Exception(
                            f"Consistency check failed - SQL: {sql_exists}, Vector: {vector_exists}"
                        )
                
                # Log successful processing
                self.log_processing_history(document_id, 'store', 'success')
                self.log_info(f"Document stored successfully: {document_id}")
                return document_id
                
            except Exception as store_error:
                # Attempt rollback
                self.log_error(f"Error during document storage, attempting rollback: {store_error}")
                
                try:
                    # Remove from SQLite if exists
                    self._execute_sql(
                        "DELETE FROM documents WHERE document_id = ?",
                        (document_id,)
                    )
                    
                    # Remove from ChromaDB if exists
                    self.collection.delete(ids=[document_id])
                    
                    self.log_info(f"Rollback completed for document: {document_id}")
                    
                except Exception as rollback_error:
                    self.log_error(f"Rollback failed: {rollback_error}")
                
                raise store_error
            
        except Exception as e:
            self.log_error(f"Failed to store document: {e}")
            if 'document_id' in locals():
                self.log_processing_history(document_id, 'store', 'error', str(e))
            raise
    
    def store_document_sqlite(self, doc_data: Dict[str, Any]):
        """Store document in SQLite database"""
        self._execute_sql("""
            INSERT INTO documents 
            (document_id, filename, file_path, file_type, file_size, content, metadata, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_data['document_id'],
            doc_data['filename'],
            doc_data['file_path'],
            doc_data['file_type'],
            doc_data['file_size'],
            doc_data['content'],
            doc_data['metadata'],
            doc_data['status']
        ))
    
    def store_document_chromadb(self, document_id: str, content: str, metadata: Dict[str, Any]):
        """Store document in ChromaDB"""
        # Create embedding metadata
        embedding_metadata = {
            'document_id': document_id,
            'type': 'document',
            'timestamp': datetime.now().isoformat(),
            **metadata
        }
        
        # Add to collection
        self.collection.add(
            documents=[content],
            metadatas=[embedding_metadata],
            ids=[document_id]
        )
    
    def store_screenshot(self, document_id: str, image_path: str, extracted_text: str, 
                        page_number: int = 1, confidence_score: float = 0.0) -> str:
        """
        Store screenshot data
        
        Args:
            document_id: Associated document ID
            image_path: Path to screenshot image
            extracted_text: Extracted text from screenshot
            page_number: Page number (for multi-page documents)
            confidence_score: OCR confidence score
            
        Returns:
            Screenshot ID
        """
        try:
            screenshot_id = str(uuid.uuid4())
            
            # Store in SQLite
            self._execute_sql("""
                INSERT INTO screenshots 
                (screenshot_id, document_id, image_path, page_number, extracted_text, confidence_score)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                screenshot_id,
                document_id,
                image_path,
                page_number,
                extracted_text,
                confidence_score
            ))
            
            # Also store in ChromaDB
            metadata = {
                'document_id': document_id,
                'screenshot_id': screenshot_id,
                'type': 'screenshot',
                'page_number': page_number,
                'confidence_score': confidence_score,
                'timestamp': datetime.now().isoformat()
            }
            
            self.collection.add(
                documents=[extracted_text],
                metadatas=[metadata],
                ids=[screenshot_id]
            )
            
            self.log_info(f"Screenshot stored successfully: {screenshot_id}")
            return screenshot_id
            
        except Exception as e:
            self.log_error(f"Failed to store screenshot: {e}")
            raise
    
    def get_documents(self, limit: int = 100, offset: int = 0, 
                    file_type: str = None, status: str = None) -> List[Dict[str, Any]]:
        """
        Get documents from SQLite with pagination, filtering, and caching
        
        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip
            file_type: Filter by file type
            status: Filter by status
            
        Returns:
            List of document dictionaries
        """
        try:
            # Create cache key
            cache_key = f"docs_{limit}_{offset}_{file_type}_{status}"
            
            # Check cache (valid for 5 seconds)
            if hasattr(self, '_docs_cache'):
                cache_entry = self._docs_cache.get(cache_key)
                if cache_entry and (time.time() - cache_entry['timestamp'] < 5):
                    return cache_entry['data']
            else:
                self._docs_cache = {}
            
            # Use simpler query without joins for better performance
            query = ["""
                SELECT 
                    d.*,
                    (SELECT COUNT(*) FROM documents) as total_count
                FROM documents d
                WHERE 1=1
            """]
            params = []
            
            if file_type:
                query.append("AND d.file_type = ?")
                params.append(file_type)
            
            if status:
                query.append("AND d.status = ?")
                params.append(status)
            
            # Add optimized ordering with index
            query.append("ORDER BY d.created_at DESC, d.document_id")
            
            # Add pagination
            query.append("LIMIT ? OFFSET ?")
            params.extend([limit, offset])
            
            # Execute optimized query with WAL mode
            self._execute_sql("PRAGMA journal_mode=WAL")
            self._execute_sql("PRAGMA synchronous=NORMAL")
            self._execute_sql("PRAGMA cache_size=10000")
            self._execute_sql("PRAGMA temp_store=MEMORY")
            
            cursor = self._execute_sql(" ".join(query), tuple(params))
            rows = cursor.fetchall()
            
            # Convert to dictionaries with additional info
            results = []
            for row in rows:
                doc = dict(row)
                
                # Add vector DB status
                if hasattr(self, 'collection') and self.collection:
                    try:
                        vector_result = self.collection.get(
                            ids=[doc['document_id']],
                            include=[]
                        )
                        doc['in_vector_db'] = bool(vector_result and vector_result.get('ids'))
                    except:
                        doc['in_vector_db'] = False
                else:
                    doc['in_vector_db'] = False
                
                results.append(doc)
            
            # Update cache
            self._docs_cache[cache_key] = {
                'timestamp': time.time(),
                'data': results
            }
            
            # Limit cache size
            if len(self._docs_cache) > 100:
                oldest = min(self._docs_cache.items(), key=lambda x: x[1]['timestamp'])
                del self._docs_cache[oldest[0]]
            
            return results
            
        except Exception as e:
            self.log_error(f"Error getting documents: {e}")
            return []
    
    def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID from PostgreSQL"""
        cursor = self._execute_sql("""
            SELECT * FROM documents WHERE document_id = ?
        """, (document_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_vector_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID from vector database"""
        try:
            # Ensure ChromaDB is initialized
            self.ensure_chromadb_initialized()
            
            # Check if collection is available
            if not hasattr(self, 'collection') or not self.collection:
                return None
            
            # Get document with retries
            max_retries = 3
            retry_delay = 1
            result = None
            
            for attempt in range(max_retries):
                try:
                    # First try to get just metadata to check existence
                    result = self.collection.get(
                        ids=[document_id],
                        include=[]
                    )
                    
                    # If document exists, get full content
                    if result and result['ids'] and len(result['ids']) > 0:
                        result = self.collection.get(
                            ids=[document_id],
                            include=['metadatas', 'documents']
                        )
                        break
                    else:
                        return None  # Document doesn't exist
                        
                except Exception as e:
                    if attempt == max_retries - 1:
                        self.log_error(f"ChromaDB get error after {max_retries} attempts: {e}")
                        return None
                    self.log_error(f"ChromaDB get attempt {attempt + 1} failed: {e}")
                    time.sleep(retry_delay)
            
            # Parse result safely
            try:
                if result and result['ids'] and len(result['ids']) > 0:
                    return {
                        'id': document_id,
                        'content': result['documents'][0] if result.get('documents') else '',
                        'metadata': result['metadatas'][0] if result.get('metadatas') else {}
                    }
                return None
                
            except (KeyError, IndexError) as e:
                self.log_error(f"Error parsing vector document result: {e}")
                return None
            
        except Exception as e:
            self.log_error(f"Error getting vector document: {e}")
            return None
    
    def get_vector_documents(self) -> List[Dict[str, Any]]:
        """Get all documents from vector database"""
        try:
            # Ensure ChromaDB is initialized
            self.ensure_chromadb_initialized()
            
            # Check if collection is available
            if not hasattr(self, 'collection') or not self.collection:
                return []
            
            # Get documents in batches to avoid memory issues
            batch_size = 100
            all_documents = []
            
            try:
                # First get total count (empty get to get IDs only)
                result = self.collection.get(include=[])
                if not result or 'ids' not in result:
                    return []
                
                total_docs = len(result['ids'])
                
                # Process in batches
                for start_idx in range(0, total_docs, batch_size):
                    end_idx = min(start_idx + batch_size, total_docs)
                    doc_ids = result['ids'][start_idx:end_idx]
                    
                    try:
                        # Get batch with retries
                        max_retries = 3
                        retry_delay = 1
                        batch_result = None
                        
                        for attempt in range(max_retries):
                            try:
                                batch_result = self.collection.get(
                                    ids=doc_ids,
                                    include=['metadatas', 'documents']
                                )
                                break
                            except Exception as e:
                                if attempt == max_retries - 1:
                                    raise
                                self.log_error(f"ChromaDB batch attempt {attempt + 1} failed: {e}")
                                time.sleep(retry_delay)
                        
                        if batch_result and 'ids' in batch_result:
                            for i, doc_id in enumerate(batch_result['ids']):
                                try:
                                    all_documents.append({
                                        'id': doc_id,
                                        'content': batch_result['documents'][i] if batch_result.get('documents') else '',
                                        'metadata': batch_result['metadatas'][i] if batch_result.get('metadatas') else {}
                                    })
                                except (IndexError, KeyError) as e:
                                    self.log_error(f"Error parsing document {doc_id}: {e}")
                                    continue
                        
                    except Exception as e:
                        self.log_error(f"Error processing batch {start_idx}-{end_idx}: {e}")
                        continue
                    
                    # Small delay between batches
                    time.sleep(0.1)
                
                return all_documents
                
            except Exception as e:
                self.log_error(f"ChromaDB get all error: {e}")
                return []
            
        except Exception as e:
            self.log_error(f"Error getting vector documents: {e}")
            return []
    
    def search_documents(self, query: str, limit: int = 10, 
                         file_type: str = None, min_score: float = 0.5) -> List[Dict[str, Any]]:
        """
        Search documents using ChromaDB semantic search with optimized filtering
        
        Args:
            query: Search query
            limit: Maximum number of results
            file_type: Filter by file type
            min_score: Minimum similarity score (0-1)
            
        Returns:
            List of matching documents with similarity scores
        """
        try:
            # Prepare filter conditions
            filter_dict = {}
            if file_type:
                filter_dict["file_type"] = file_type
            
            # Search in ChromaDB with metadata filtering
            results = self.collection.query(
                query_texts=[query],
                n_results=limit * 2,  # Get more results for filtering
                where=filter_dict if filter_dict else None
            )
            
            if not results['ids'][0]:
                return []
            
            # Get document IDs for batch retrieval
            doc_ids = results['ids'][0]
            
        # Batch retrieve documents from PostgreSQL
            placeholders = ','.join(['?' for _ in doc_ids])
            cursor = self._execute_sql(
                f"""
                SELECT * FROM documents 
                WHERE document_id IN ({placeholders})
                ORDER BY created_at DESC
                """, 
                tuple(doc_ids)
            )
            
            # Create document lookup dictionary
            doc_lookup = {row['document_id']: dict(row) for row in cursor.fetchall()}
            
            # Combine results with similarity scores and filter by min_score
            documents = []
            for i, doc_id in enumerate(doc_ids):
                similarity = 1 - (results['distances'][0][i] if results['distances'] else 0)
                if similarity >= min_score and doc_id in doc_lookup:
                    doc = doc_lookup[doc_id]
                    doc['similarity_score'] = similarity
                    documents.append(doc)
                    
                    if len(documents) >= limit:
                        break
            
            return documents
            
        except Exception as e:
            self.log_error(f"Search failed: {e}")
            return []
    
    def delete_document(self, document_id: str, delete_from_vector: bool = False) -> bool:
        """
        Delete document from databases
        
        Args:
            document_id: Document ID to delete
            delete_from_vector: If True, also delete from vector DB
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if delete_from_vector:
                # Delete from both databases
                self._execute_sql("DELETE FROM documents WHERE document_id = ?", (document_id,))
                self._execute_sql("DELETE FROM screenshots WHERE document_id = ?", (document_id,))
                self.collection.delete(ids=[document_id])
                self.log_processing_history(document_id, 'delete', 'success', 'Deleted from both databases')
            else:
                # Only delete from vector DB
                self.collection.delete(ids=[document_id])
                self.log_processing_history(document_id, 'delete', 'success', 'Deleted from vector DB only')
            
            self.log_info(f"Document deleted successfully: {document_id} (vector_only={not delete_from_vector})")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to delete document: {e}")
            return False
            
    def get_document_status(self, document_id: str) -> Dict[str, bool]:
        """
        Get document presence status in both databases
        
        Args:
            document_id: Document ID to check
            
        Returns:
            Dictionary with status in each database
        """
        status = {
            'sql_exists': False,
            'vector_exists': False
        }
        
        # Check SQLite
        try:
            cursor = self._execute_sql(
                "SELECT COUNT(*) FROM documents WHERE document_id = ?",
                (document_id,)
            )
            status['sql_exists'] = cursor.fetchone()[0] > 0
        except Exception as e:
            self.log_error(f"Error checking SQLite status: {e}")
        
        # Check ChromaDB
        try:
            if hasattr(self, 'collection') and self.collection:
                try:
                    result = self.collection.get(
                        ids=[document_id],
                        include=[]
                    )
                    status['vector_exists'] = bool(result and result.get('ids'))
                except Exception as e:
                    self.log_error(f"Error querying ChromaDB: {e}")
        except Exception as e:
            self.log_error(f"Error checking vector status: {e}")
        
        return status
            
    def migrate_to_vector(self, document_id: str) -> bool:
        """
        Migrate document from SQLite to vector DB
        
        Args:
            document_id: Document ID to migrate
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get document from SQLite
            cursor = self._execute_sql(
                "SELECT content, metadata FROM documents WHERE document_id = ?",
                (document_id,)
            )
            doc = cursor.fetchone()
            
            if doc:
                # Add to vector DB
                self.store_document_chromadb(
                    document_id,
                    doc['content'],
                    json.loads(doc['metadata'])
                )
                
                self.log_processing_history(
                    document_id,
                    'migrate',
                    'success',
                    'Migrated to vector DB'
                )
                return True
            else:
                self.log_error(f"Document not found in SQLite: {document_id}")
                return False
                
        except Exception as e:
            self.log_error(f"Failed to migrate document: {e}")
            return False
    
    def log_processing_history(self, document_id: str, operation: str, status: str, details: str = ""):
        """Log processing history"""
        self._execute_sql("""
            INSERT INTO processing_history (document_id, operation, status, details)
            VALUES (?, ?, ?, ?)
        """, (document_id, operation, status, details))
    
    def get_processing_history(self, document_id: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get processing history"""
        if document_id:
            cursor = self._execute_sql("""
                SELECT * FROM processing_history 
                WHERE document_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (document_id, limit))
        else:
            cursor = self._execute_sql("""
                SELECT * FROM processing_history 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        # Document count
        cursor = self._execute_sql("SELECT COUNT(*) FROM documents")
        doc_count = cursor.fetchone()[0]
        
        # Screenshot count
        cursor = self._execute_sql("SELECT COUNT(*) FROM screenshots")
        screenshot_count = cursor.fetchone()[0]
        
        # File type distribution
        cursor = self._execute_sql("""
            SELECT file_type, COUNT(*) as count 
            FROM documents 
            GROUP BY file_type
        """)
        file_types = dict(cursor.fetchall())
        
        # ChromaDB collection info
        collection_count = self.collection.count()
        
        return {
            'total_documents': doc_count,
            'total_screenshots': screenshot_count,
            'file_type_distribution': file_types,
            'vector_documents': collection_count
        }
    
    def backup_database(self, backup_path: str = None) -> bool:
        """Create database backup"""
        try:
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"backup/wms_backup_{timestamp}.db"
            
            backup_path = Path(backup_path)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get thread-local connection
            conn = self._get_connection()
            
            # Create backup connection
            backup_conn = sqlite3.connect(backup_path)
            
            # Backup SQLite database
            conn.backup(backup_conn)
            backup_conn.close()
            
            self.log_info(f"Database backup created: {backup_path}")
            return True
            
        except Exception as e:
            self.log_error(f"Backup failed: {e}")
            return False
    
    def validate_database_consistency(self) -> Dict[str, Any]:
        """
        Validate consistency between SQL and vector databases
        
        Returns:
            Dictionary with validation results and inconsistencies
        """
        try:
            # Get all document IDs from both databases
            cursor = self._execute_sql("SELECT document_id FROM documents")
            sql_doc_ids = set(row['document_id'] for row in cursor.fetchall())
            
            vector_doc_ids = set(self.collection.get()['ids'])
            
            # Find inconsistencies
            missing_in_vector = sql_doc_ids - vector_doc_ids
            missing_in_sql = vector_doc_ids - sql_doc_ids
            
            # Get metadata consistency
            metadata_inconsistencies = []
            for doc_id in sql_doc_ids & vector_doc_ids:
                # Get SQL metadata
                cursor = self._execute_sql(
                    "SELECT filename, file_type, created_at FROM documents WHERE document_id = ?",
                    (doc_id,)
                )
                sql_metadata = dict(cursor.fetchone())
                
                # Get vector metadata
                vector_metadata = self.collection.get(
                    ids=[doc_id],
                    include=['metadatas']
                )['metadatas'][0]
                
                # Compare metadata
                if (sql_metadata['filename'] != vector_metadata.get('filename') or
                    sql_metadata['file_type'] != vector_metadata.get('file_type')):
                    metadata_inconsistencies.append({
                        'document_id': doc_id,
                        'sql_metadata': sql_metadata,
                        'vector_metadata': vector_metadata
                    })
            
            # Prepare validation report
            report = {
                'total_sql_documents': len(sql_doc_ids),
                'total_vector_documents': len(vector_doc_ids),
                'missing_in_vector_db': list(missing_in_vector),
                'missing_in_sql_db': list(missing_in_sql),
                'metadata_inconsistencies': metadata_inconsistencies,
                'is_consistent': (not missing_in_vector and 
                                not missing_in_sql and 
                                not metadata_inconsistencies)
            }
            
            self.log_info(f"Database consistency check completed: {report['is_consistent']}")
            return report
            
        except Exception as e:
            self.log_error(f"Error validating database consistency: {e}")
            return {
                'error': str(e),
                'is_consistent': False
            }
    
    def repair_database_consistency(self, validation_report: Dict[str, Any] = None) -> bool:
        """
        Repair inconsistencies between SQL and vector databases
        
        Args:
            validation_report: Optional validation report from validate_database_consistency()
            
        Returns:
            True if repairs were successful
        """
        try:
            if validation_report is None:
                validation_report = self.validate_database_consistency()
            
            if validation_report.get('error'):
                return False
            
            # Handle missing vector documents
            for doc_id in validation_report['missing_in_vector_db']:
                cursor = self._execute_sql(
                    "SELECT content, metadata FROM documents WHERE document_id = ?",
                    (doc_id,)
                )
                doc = cursor.fetchone()
                if doc:
                    # Re-add to vector database
                    self.store_document_chromadb(
                        doc_id,
                        doc['content'],
                        json.loads(doc['metadata'])
                    )
            
            # Handle missing SQL documents
            for doc_id in validation_report['missing_in_sql_db']:
                # Remove from vector database as SQL is primary
                self.collection.delete(ids=[doc_id])
            
            # Fix metadata inconsistencies
            for inconsistency in validation_report['metadata_inconsistencies']:
                doc_id = inconsistency['document_id']
                cursor = self._execute_sql(
                    "SELECT content, metadata FROM documents WHERE document_id = ?",
                    (doc_id,)
                )
                doc = cursor.fetchone()
                if doc:
                    # Update vector database metadata
                    self.collection.update(
                        ids=[doc_id],
                        metadatas=[json.loads(doc['metadata'])]
                    )
            
            self.log_info("Database consistency repairs completed")
            return True
            
        except Exception as e:
            self.log_error(f"Error repairing database consistency: {e}")
            return False
    
    def close(self):
        """Close database connections"""
        try:
            # Close thread-local connection if exists
            if hasattr(self._thread_local, 'connection'):
                self._thread_local.connection.close()
                delattr(self._thread_local, 'connection')
            
            if hasattr(self, 'chroma_client'):
                self.chroma_client.reset()
            
            self.log_info("Database connections closed")
            
        except Exception as e:
            self.log_error(f"Error closing databases: {e}") 