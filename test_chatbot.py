import os
from modules.database_manager import DatabaseManager
from modules.chatbot_manager import ChatbotManager
from modules.config_manager import ConfigManager

def test_chatbot():
    print("Initializing test...")
    
    # Initialize managers
    config_manager = ConfigManager()
    db_manager = DatabaseManager()
    chatbot_manager = ChatbotManager(db_manager, config_manager)
    
    # Test vector store initialization
    print("\nTesting vector store...")
    stats = chatbot_manager.get_chatbot_stats()
    print(f"Vector store documents: {stats.get('vector_store_documents', 0)}")
    print(f"LLM configured: {stats.get('llm_configured', False)}")
    print(f"Embeddings configured: {stats.get('embeddings_configured', False)}")
    print(f"Conversation chain configured: {stats.get('conversation_chain_configured', False)}")
    
    # Test document search
    print("\nTesting semantic search...")
    search_results = chatbot_manager.search_documents("What APIs are we using?", limit=3)
    print("\nSearch Results:")
    for i, result in enumerate(search_results, 1):
        print(f"\nResult {i}:")
        print(f"File: {result.get('filename')}")
        print(f"Type: {result.get('file_type')}")
        print(f"Content Preview: {result.get('content')[:200]}...")
    
    # Test chatbot query
    print("\nTesting chatbot query...")
    query = "Which APIs are we using in this system?"
    response = chatbot_manager.process_query(query, include_sources=True)
    
    print(f"\nQuery: {query}")
    print(f"Response: {response.get('response')}")
    
    if response.get('sources'):
        print("\nSources used:")
        for i, source in enumerate(response['sources'], 1):
            print(f"\nSource {i}:")
            print(f"File: {source.get('filename')}")
            print(f"Content: {source.get('content_preview')}")
    
    # Cleanup
    chatbot_manager.close()
    db_manager.close()
    print("\nTest completed.")

if __name__ == "__main__":
    test_chatbot()