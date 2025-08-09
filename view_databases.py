import sqlite3
import chromadb
from pathlib import Path
import json

def view_sqlite_db():
    print("\n=== SQLite Database Contents ===")
    try:
        # Connect to SQLite DB
        conn = sqlite3.connect("data/wms_screenshots.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get document count
        cursor.execute("SELECT COUNT(*) FROM documents")
        count = cursor.fetchone()[0]
        print(f"\nTotal Documents: {count}")
        
        # Get all documents
        print("\nDocuments:")
        print("-" * 80)
        cursor.execute("SELECT document_id, filename, file_type, created_at, status FROM documents")
        rows = cursor.fetchall()
        for row in rows:
            print(f"ID: {row['document_id']}")
            print(f"Filename: {row['filename']}")
            print(f"Type: {row['file_type']}")
            print(f"Created: {row['created_at']}")
            print(f"Status: {row['status']}")
            print("-" * 80)
            
    except Exception as e:
        print(f"Error reading SQLite DB: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def view_chroma_db():
    print("\n=== ChromaDB (Vector Database) Contents ===")
    try:
        # Initialize ChromaDB
        chroma_client = chromadb.PersistentClient(
            path="data/chroma_db",
            settings=chromadb.Settings(
                anonymized_telemetry=False,
                is_persistent=True
            )
        )
        
        # Get collection
        collection = chroma_client.get_collection(name="wms_documents")
        
        # Get document count
        count = collection.count()
        print(f"\nTotal Documents: {count}")
        
        # Get all documents
        print("\nDocuments:")
        print("-" * 80)
        results = collection.get(include=['metadatas'])
        if results and results['metadatas']:
            for idx, metadata in enumerate(results['metadatas']):
                print(f"Document {idx + 1}:")
                print(f"ID: {results['ids'][idx]}")
                for key, value in metadata.items():
                    print(f"{key}: {value}")
                print("-" * 80)
                
    except Exception as e:
        print(f"Error reading ChromaDB: {e}")

if __name__ == "__main__":
    print("Viewing WMS Database Contents")
    print("=" * 50)
    
    view_sqlite_db()
    print("\n")
    view_chroma_db()