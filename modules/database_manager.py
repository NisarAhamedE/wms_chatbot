import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import chromadb
from chromadb.config import Settings
import uuid

from .logger import LoggerMixin

class DatabaseManager(LoggerMixin):
    """
    Manages both SQLite and ChromaDB databases for the WMS application
    """
    
    def __init__(self, sqlite_path: str = "data/wms_screenshots.db", 
                 chroma_path: str = "data/chroma_db"):
        super().__init__()
        
        self.sqlite_path = Path(sqlite_path)
        self.chroma_path = Path(chroma_path)
        
        # Ensure directories exist
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize databases
        self.init_sqlite()
        self.init_chromadb()
        
        self.log_info("Database manager initialized")
    
    def init_sqlite(self):
        """Initialize SQLite database with required tables"""
        try:
            self.sqlite_conn = sqlite3.connect(self.sqlite_path)
            self.sqlite_conn.row_factory = sqlite3.Row
            
            # Create tables
            self.create_tables()
            
        except Exception as e:
            self.log_error(f"Failed to initialize SQLite database: {e}")
            raise
    
    def init_chromadb(self):
        """Initialize ChromaDB for vector storage"""
        try:
            self.chroma_client = chromadb.PersistentClient(
                path=str(self.chroma_path),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            self.collection = self.chroma_client.get_or_create_collection(
                name="wms_documents",
                metadata={"description": "WMS document embeddings"}
            )
            
        except Exception as e:
            self.log_error(f"Failed to initialize ChromaDB: {e}")
            raise
    
    def create_tables(self):
        """Create SQLite tables if they don't exist"""
        cursor = self.sqlite_conn.cursor()
        
        # Documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER,
                content TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'processed',
                error_message TEXT
            )
        """)
        
        # Screenshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS screenshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                screenshot_id TEXT UNIQUE NOT NULL,
                document_id TEXT,
                image_path TEXT NOT NULL,
                page_number INTEGER,
                extracted_text TEXT,
                confidence_score REAL,
                processing_time REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents (document_id)
            )
        """)
        
        # Processing history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT,
                operation TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents (document_id)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents (filename)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_file_type ON documents (file_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_screenshots_document_id ON screenshots (document_id)")
        
        self.sqlite_conn.commit()
        self.log_info("SQLite tables created successfully")
    
    def store_document(self, file_path: str, content: str, metadata: Dict[str, Any]) -> str:
        """
        Store document in both SQLite and ChromaDB
        
        Args:
            file_path: Path to the document file
            content: Extracted text content
            metadata: Additional metadata
            
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
            
            # Store in SQLite
            self.store_document_sqlite(doc_data)
            
            # Store in ChromaDB
            self.store_document_chromadb(document_id, content, metadata)
            
            # Log processing history
            self.log_processing_history(document_id, 'store', 'success')
            
            self.log_info(f"Document stored successfully: {document_id}")
            return document_id
            
        except Exception as e:
            self.log_error(f"Failed to store document: {e}")
            if 'document_id' in locals():
                self.log_processing_history(document_id, 'store', 'error', str(e))
            raise
    
    def store_document_sqlite(self, doc_data: Dict[str, Any]):
        """Store document in SQLite database"""
        cursor = self.sqlite_conn.cursor()
        
        cursor.execute("""
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
        
        self.sqlite_conn.commit()
    
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
            
            cursor = self.sqlite_conn.cursor()
            cursor.execute("""
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
            
            self.sqlite_conn.commit()
            
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
    
    def get_documents(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get documents from SQLite with pagination"""
        cursor = self.sqlite_conn.cursor()
        
        cursor.execute("""
            SELECT * FROM documents 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        cursor = self.sqlite_conn.cursor()
        
        cursor.execute("""
            SELECT * FROM documents WHERE document_id = ?
        """, (document_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def search_documents(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search documents using ChromaDB semantic search
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching documents
        """
        try:
            # Search in ChromaDB
            results = self.collection.query(
                query_texts=[query],
                n_results=limit
            )
            
            # Get full document details from SQLite
            documents = []
            for i, doc_id in enumerate(results['ids'][0]):
                doc = self.get_document_by_id(doc_id)
                if doc:
                    doc['similarity_score'] = results['distances'][0][i]
                    documents.append(doc)
            
            return documents
            
        except Exception as e:
            self.log_error(f"Search failed: {e}")
            return []
    
    def delete_document(self, document_id: str) -> bool:
        """
        Delete document from both databases
        
        Args:
            document_id: Document ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete from SQLite
            cursor = self.sqlite_conn.cursor()
            cursor.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
            cursor.execute("DELETE FROM screenshots WHERE document_id = ?", (document_id,))
            self.sqlite_conn.commit()
            
            # Delete from ChromaDB
            self.collection.delete(ids=[document_id])
            
            # Log deletion
            self.log_processing_history(document_id, 'delete', 'success')
            
            self.log_info(f"Document deleted successfully: {document_id}")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to delete document: {e}")
            return False
    
    def log_processing_history(self, document_id: str, operation: str, status: str, details: str = ""):
        """Log processing history"""
        cursor = self.sqlite_conn.cursor()
        cursor.execute("""
            INSERT INTO processing_history (document_id, operation, status, details)
            VALUES (?, ?, ?, ?)
        """, (document_id, operation, status, details))
        self.sqlite_conn.commit()
    
    def get_processing_history(self, document_id: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get processing history"""
        cursor = self.sqlite_conn.cursor()
        
        if document_id:
            cursor.execute("""
                SELECT * FROM processing_history 
                WHERE document_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (document_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM processing_history 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        cursor = self.sqlite_conn.cursor()
        
        # Document count
        cursor.execute("SELECT COUNT(*) FROM documents")
        doc_count = cursor.fetchone()[0]
        
        # Screenshot count
        cursor.execute("SELECT COUNT(*) FROM screenshots")
        screenshot_count = cursor.fetchone()[0]
        
        # File type distribution
        cursor.execute("""
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
            
            # Create backup connection
            backup_conn = sqlite3.connect(backup_path)
            
            # Backup SQLite database
            self.sqlite_conn.backup(backup_conn)
            backup_conn.close()
            
            self.log_info(f"Database backup created: {backup_path}")
            return True
            
        except Exception as e:
            self.log_error(f"Backup failed: {e}")
            return False
    
    def close(self):
        """Close database connections"""
        try:
            if hasattr(self, 'sqlite_conn'):
                self.sqlite_conn.close()
            
            if hasattr(self, 'chroma_client'):
                self.chroma_client.reset()
            
            self.log_info("Database connections closed")
            
        except Exception as e:
            self.log_error(f"Error closing databases: {e}") 