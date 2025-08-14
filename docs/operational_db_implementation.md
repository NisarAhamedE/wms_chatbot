# Operational Database Implementation

## Overview

The WMS chatbot now includes comprehensive operational database interaction capabilities, enabling users to query real-time WMS data using natural language. This implementation provides a complete pipeline from natural language input to safe SQL execution against operational MS SQL databases.

## Components Implemented

### 1. Schema Manager (`src/operational_db/schema_manager.py`)

**Purpose**: Extract, categorize, and vectorize operational database schemas

**Key Features**:
- Complete MS SQL schema extraction with metadata
- Automatic table categorization based on WMS categories
- Relationship graph building between tables
- Vector database storage for intelligent schema search
- Column mapping for natural language terms
- Sample data extraction for context

**Main Classes**:
- `TableSchema`: Represents database table structure
- `OperationalSchemaManager`: Handles schema operations
- `initialize_operational_schema()`: Setup function

### 2. SQL Generator (`src/operational_db/sql_generator.py`)

**Purpose**: Convert natural language queries to safe, optimized SQL

**Key Features**:
- Intelligent query analysis and classification
- Vector-based table relevance scoring
- Join path planning and optimization
- Safety validation and SQL injection prevention
- Query complexity analysis
- Automatic row limiting for safety

**Main Classes**:
- `IntelligentSQLGenerator`: Core SQL generation engine
- `SafetyValidator`: Query safety validation
- `QueryPlan`: Execution plan representation
- `QueryComplexity`: Complexity classification

### 3. SQL Executor (`src/operational_db/sql_executor.py`)

**Purpose**: Safely execute SQL queries against operational databases

**Key Features**:
- Async query execution with timeout protection
- Connection pooling management
- Result formatting and data type handling
- Query statistics and performance monitoring
- Concurrent query limiting
- Error handling and fallback mechanisms

**Main Classes**:
- `OperationalSQLExecutor`: Query execution engine
- `ExecutionResult`: Query result container
- `ConnectionInfo`: Database connection details

### 4. Operational Query Agent (`src/agents/operational_db/operational_query_agent.py`)

**Purpose**: LangChain agent for operational database queries

**Key Features**:
- Natural language query processing
- Data summarization and reporting
- Query result interpretation
- User-friendly response formatting

**Tools Provided**:
- `OperationalQueryTool`: Execute natural language queries
- `DataSummaryTool`: Generate category-based summaries
- `OperationalReportingTool`: Create comprehensive reports

### 5. Multi-Table Orchestrator (`src/agents/operational_db/multi_table_orchestrator.py`)

**Purpose**: Handle complex queries spanning multiple tables

**Key Features**:
- Multi-table join planning and optimization
- Cross-category analysis capabilities
- Query complexity management
- Fallback query generation
- Correlation and trend analysis

**Tools Provided**:
- `MultiTableQueryTool`: Complex multi-table queries
- `CrossCategoryAnalysisTool`: Cross-category insights

## Integration Points

### Agent Orchestrator Integration

The operational database agents are now integrated into the main agent orchestrator with:
- Category keyword mapping for "operational_database"
- Sub-category routing for "query_execution" and "multi_table_operations"
- Automatic query routing based on natural language patterns

### Safety Mechanisms

1. **Query Validation**:
   - Dangerous keyword detection (DROP, DELETE, etc.)
   - SQL injection prevention
   - Query complexity limits

2. **Execution Safety**:
   - Row count limits (default: 10,000 rows)
   - Query timeout (default: 5 minutes)
   - Concurrent query limits (default: 3)
   - Automatic TOP clause insertion

3. **Connection Safety**:
   - No connection pooling to avoid locks
   - Read-only recommendations
   - Connection timeout limits

## Usage Examples

### Basic Query
```python
# Natural language input
query = "Show me all orders from today"

# Agent processes and converts to SQL
# Executes safely against operational database
# Returns formatted results
```

### Complex Multi-Table Query
```python
# Complex analysis request
query = "Compare inventory accuracy between different zones over the last month"

# Multi-table orchestrator:
# 1. Identifies relevant tables (inventory, locations, accuracy metrics)
# 2. Plans optimal joins
# 3. Generates complex SQL with aggregations
# 4. Executes with safety checks
# 5. Provides analytical insights
```

### Schema Management
```python
# Initialize schema extraction
await initialize_operational_schema(
    connection_string="mssql+pymssql://user:pass@server/db",
    include_sample_data=True
)

# Schema automatically:
# - Extracted from MS SQL
# - Categorized by WMS function
# - Vectorized for search
# - Made available for query generation
```

## Configuration

### Environment Variables
```bash
# Database connection
OPERATIONAL_DB_SERVER=your-server.com
OPERATIONAL_DB_NAME=WMS_Production
OPERATIONAL_DB_USERNAME=readonly_user
OPERATIONAL_DB_PASSWORD=secure_password

# Safety limits
MAX_QUERY_ROWS=10000
QUERY_TIMEOUT_SECONDS=300
MAX_CONCURRENT_QUERIES=3
```

### UI Integration Points
- Database connection setup page
- Schema extraction trigger
- Natural language query interface
- Result visualization and export
- Query history and bookmarks

## WMS Categories Supported

The system automatically categorizes database tables into these WMS categories:

1. **Locations**: Bins, zones, aisles, warehouse layout
2. **Items**: Products, SKUs, item master data
3. **Inventory**: Stock levels, quantities, movements
4. **Receiving**: Receipts, ASNs, inbound operations
5. **Putaway**: Location assignments, placement strategies
6. **Work**: Tasks, assignments, labor management
7. **Cycle Counting**: Count schedules, accuracy metrics
8. **Wave Management**: Wave planning and execution
9. **Allocation**: Inventory reservations, availability
10. **Replenishment**: Stock replenishment planning
11. **Picking**: Order picking, productivity metrics
12. **Packing**: Cartonization, packing operations
13. **Shipping**: Outbound orders, carrier management
14. **Yard Management**: Dock scheduling, trailer management
15. **Other/Data Categorization**: General data operations

## Performance Considerations

### Query Optimization
- Intelligent join path selection
- Index usage recommendations
- Query complexity analysis
- Automatic LIMIT/TOP clause insertion

### Scalability
- Async processing for concurrent users
- Connection management without pooling
- Vector search for schema relevance
- Caching of schema metadata

### Monitoring
- Query execution statistics
- Performance metrics tracking
- Error rate monitoring
- User interaction analytics

## Security Features

### Access Control
- Read-only database access recommended
- User role-based query restrictions
- Query audit logging
- Sensitive data detection

### Query Safety
- SQL injection prevention
- Dangerous operation blocking
- Resource usage limits
- Connection timeout protection

## Future Enhancements

### Planned Features
1. **Advanced Analytics**: Machine learning insights
2. **Query Caching**: Intelligent result caching
3. **Real-time Monitoring**: Live operational dashboards
4. **Performance Tuning**: Automatic query optimization
5. **Data Visualization**: Chart and graph generation
6. **Export Capabilities**: Multiple format support
7. **Scheduled Queries**: Automated reporting
8. **Alert System**: Threshold-based notifications

### Integration Opportunities
- Business Intelligence tools
- External reporting systems
- Mobile application support
- API gateway integration
- Enterprise service bus connectivity

## Testing Strategy

### Unit Tests
- Schema extraction validation
- SQL generation accuracy
- Safety mechanism verification
- Agent tool functionality

### Integration Tests
- End-to-end query processing
- Multi-agent orchestration
- Database connection handling
- Error scenario coverage

### Performance Tests
- Concurrent user handling
- Large result set processing
- Complex query execution
- Memory usage optimization

## Conclusion

The operational database interaction system provides a comprehensive solution for natural language querying of WMS operational data. It combines intelligent query generation, robust safety mechanisms, and user-friendly interfaces to enable business users to access real-time operational insights without requiring SQL knowledge.

The system is designed for enterprise-scale deployment with proper security, performance, and monitoring capabilities, while maintaining the flexibility to handle the full spectrum of WMS data analysis needs.