"""
Operational Database Agents Package
Agents specialized in querying and analyzing operational WMS database.
"""

from .operational_query_agent import (
    OperationalDatabaseQueryAgent,
    OperationalQueryTool,
    DataSummaryTool,
    OperationalReportingTool,
    OPERATIONAL_DB_KEYWORDS
)

from .multi_table_orchestrator import (
    MultiTableQueryAgent,
    MultiTableQueryTool,
    CrossCategoryAnalysisTool,
    MultiTableOrchestrator,
    MULTI_TABLE_KEYWORDS
)

__all__ = [
    # Agents
    "OperationalDatabaseQueryAgent",
    "MultiTableQueryAgent",
    
    # Tools
    "OperationalQueryTool",
    "DataSummaryTool", 
    "OperationalReportingTool",
    "MultiTableQueryTool",
    "CrossCategoryAnalysisTool",
    
    # Orchestrator
    "MultiTableOrchestrator",
    
    # Keywords for routing
    "OPERATIONAL_DB_KEYWORDS",
    "MULTI_TABLE_KEYWORDS"
]

# Convenience function to get all operational DB agents
def get_operational_db_agents():
    """Get all operational database agents"""
    return [
        OperationalDatabaseQueryAgent(),
        MultiTableQueryAgent()
    ]

# Combined keywords for routing
ALL_OPERATIONAL_KEYWORDS = OPERATIONAL_DB_KEYWORDS + MULTI_TABLE_KEYWORDS