"""
Operational Database Demo Script
Demonstrates the WMS chatbot's operational database interaction capabilities.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.operational_db.sql_executor import OperationalSQLExecutor, ConnectionInfo
from src.operational_db.schema_manager import get_schema_manager, initialize_operational_schema
from src.agents.operational_db import OperationalDatabaseQueryAgent, MultiTableQueryAgent
from src.agents.base import WMSContext


async def demo_operational_database_features():
    """Demonstrate operational database features"""
    
    print("=== WMS Chatbot Operational Database Demo ===\n")
    
    # Example connection info (in real usage, this comes from UI)
    connection_info = ConnectionInfo(
        server="your-sql-server.com",
        database="WMS_Production", 
        username="wms_readonly_user",
        password="secure_password"
    )
    
    print("1. SQL Executor Demo")
    print("-" * 30)
    
    executor = OperationalSQLExecutor()
    
    # Note: This would fail without actual database - showing structure
    print("Setting up database connection...")
    # success = executor.set_connection(connection_info)
    print("✓ Connection configured")
    
    print("\nExample natural language queries that can be executed:")
    example_queries = [
        "Show me all inventory from today",
        "How many orders are pending?", 
        "List locations with low utilization",
        "Show shipping performance this week",
        "What items need replenishment?",
        "Display work task summary by user"
    ]
    
    for i, query in enumerate(example_queries, 1):
        print(f"  {i}. {query}")
    
    print("\n2. Schema Manager Demo")
    print("-" * 30)
    
    schema_manager = get_schema_manager()
    print("✓ Schema manager initialized")
    print("Features available:")
    print("  • Extract complete MS SQL database schemas")
    print("  • Automatically categorize tables by WMS function")
    print("  • Build relationship graphs between tables")
    print("  • Vectorize schemas for intelligent search")
    print("  • Generate column mappings for natural language")
    
    print("\n3. Agent Integration Demo")
    print("-" * 30)
    
    # Create WMS context
    context = WMSContext(
        user_id="demo_user",
        user_role="operations_user",
        session_id="demo_session"
    )
    
    # Initialize operational query agent
    query_agent = OperationalDatabaseQueryAgent()
    print(f"✓ {query_agent.name} initialized")
    print(f"  Category: {query_agent.category}")
    print(f"  Tools available: {len(query_agent.tools)}")
    
    # Initialize multi-table agent
    multi_table_agent = MultiTableQueryAgent()
    print(f"✓ {multi_table_agent.name} initialized")
    print(f"  Category: {multi_table_agent.category}")
    print(f"  Tools available: {len(multi_table_agent.tools)}")
    
    print("\n4. Query Processing Pipeline")
    print("-" * 30)
    
    sample_query = "Show me orders and their inventory status from this week"
    print(f"Sample query: '{sample_query}'")
    print("\nProcessing steps:")
    print("  1. Natural language query received")
    print("  2. Agent orchestrator routes to operational_database category")
    print("  3. SQL generator analyzes query and identifies relevant tables")
    print("  4. Schema manager provides table relationships and column info")
    print("  5. Intelligent SQL query generated with safety validation")
    print("  6. Query executed against operational database")
    print("  7. Results formatted and returned to user")
    
    print("\n5. Safety Features")
    print("-" * 30)
    
    print("Built-in safety mechanisms:")
    print("  • Query validation prevents dangerous operations")
    print("  • Row limits prevent overwhelming result sets")
    print("  • Query timeout prevents long-running queries")
    print("  • Connection pooling disabled for safety")
    print("  • Read-only database access recommended")
    print("  • SQL injection protection via parameterized queries")
    print("  • Automatic TOP clause insertion for MS SQL")
    
    print("\n6. Multi-Table Capabilities")
    print("-" * 30)
    
    print("Complex query examples:")
    complex_queries = [
        "Compare inventory accuracy between different zones",
        "Show correlation between picking productivity and order complexity",
        "Analyze cross-category performance trends over time",
        "Display comprehensive operational dashboard metrics"
    ]
    
    for i, query in enumerate(complex_queries, 1):
        print(f"  {i}. {query}")
    
    print("\nMulti-table features:")
    print("  • Automatic join path discovery")
    print("  • Query complexity analysis")
    print("  • Fallback query generation")
    print("  • Cross-category correlation analysis")
    print("  • Execution order optimization")
    
    print("\n=== Demo Complete ===")
    print("The WMS chatbot is now ready for operational database interaction!")


def demo_configuration_examples():
    """Show configuration examples"""
    
    print("\n=== Configuration Examples ===\n")
    
    print("1. Environment Variables (.env):")
    print("-" * 30)
    env_example = '''
# Operational Database Settings
OPERATIONAL_DB_SERVER=your-sql-server.com
OPERATIONAL_DB_NAME=WMS_Production
OPERATIONAL_DB_USERNAME=wms_readonly
OPERATIONAL_DB_PASSWORD=secure_password
OPERATIONAL_DB_PORT=1433

# Query Safety Settings
MAX_QUERY_ROWS=10000
QUERY_TIMEOUT_SECONDS=300
MAX_CONCURRENT_QUERIES=3

# Schema Refresh Settings
SCHEMA_REFRESH_INTERVAL_HOURS=24
AUTO_VECTORIZE_SCHEMAS=true
'''
    print(env_example)
    
    print("2. Connection String Examples:")
    print("-" * 30)
    print("Standard SQL Server:")
    print("  mssql+pymssql://username:password@server:1433/database")
    print("\nWindows Authentication:")
    print("  mssql+pymssql://server/database?trusted_connection=yes")
    print("\nAzure SQL Database:")
    print("  mssql+pymssql://username:password@server.database.windows.net/database")
    
    print("\n3. UI Integration Points:")
    print("-" * 30)
    print("Database Connection Setup Page:")
    print("  • Connection string input/validation")
    print("  • Test connection functionality") 
    print("  • Schema extraction trigger")
    print("  • Vectorization status display")
    print("\nQuery Interface:")
    print("  • Natural language input box")
    print("  • Category selection (optional)")
    print("  • Query history")
    print("  • Result export options")


if __name__ == "__main__":
    print("Starting WMS Chatbot Operational Database Demo...\n")
    
    # Run the async demo
    asyncio.run(demo_operational_database_features())
    
    # Show configuration examples
    demo_configuration_examples()
    
    print("\nNote: This is a demonstration of the system architecture.")
    print("Actual database operations require valid connection credentials.")