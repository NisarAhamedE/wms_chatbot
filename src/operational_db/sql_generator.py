"""
Intelligent SQL Generator for Operational Database Queries
Converts natural language queries to safe, optimized SQL queries using schema knowledge.
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from langchain_openai import AzureChatOpenAI
from sqlparse import parse, format as sql_format
from sqlparse.sql import Statement, Token
from sqlparse.tokens import Keyword, Name

from ..core.config import get_azure_openai_settings
from ..core.logging import LoggerMixin
from .schema_manager import get_schema_manager, TableSchema


class QueryType(Enum):
    """Types of SQL queries"""
    SELECT = "SELECT"
    COUNT = "COUNT"
    SUMMARY = "SUMMARY"
    TREND = "TREND"
    COMPARISON = "COMPARISON"
    UNKNOWN = "UNKNOWN"


class QueryComplexity(Enum):
    """Query complexity levels"""
    SIMPLE = "SIMPLE"      # Single table
    MODERATE = "MODERATE"  # 2-3 tables with simple joins
    COMPLEX = "COMPLEX"    # Multiple tables with complex logic
    ADVANCED = "ADVANCED"  # Subqueries, CTEs, advanced analytics


@dataclass
class QueryPlan:
    """Represents a query execution plan"""
    query_type: QueryType
    complexity: QueryComplexity
    tables: List[str]
    columns: List[str]
    joins: List[Dict[str, str]]
    filters: List[Dict[str, Any]]
    aggregations: List[Dict[str, str]]
    grouping: List[str]
    ordering: List[Dict[str, str]]
    limit: Optional[int] = None
    estimated_rows: Optional[int] = None
    safety_score: float = 1.0
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class SafetyValidator:
    """Validates SQL queries for safety and performance"""
    
    DANGEROUS_KEYWORDS = [
        'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE',
        'EXEC', 'EXECUTE', 'MERGE', 'BULK', 'OPENROWSET', 'OPENDATASOURCE',
        'SHUTDOWN', 'RESTORE', 'BACKUP'
    ]
    
    RISKY_FUNCTIONS = [
        'xp_cmdshell', 'sp_configure', 'OPENQUERY', 'OPENXML'
    ]
    
    @classmethod
    def validate_query(cls, sql: str) -> Tuple[bool, List[str], float]:
        """Validate SQL query for safety and performance"""
        warnings = []
        safety_score = 1.0
        
        sql_upper = sql.upper()
        
        # Check for dangerous keywords
        for keyword in cls.DANGEROUS_KEYWORDS:
            if keyword in sql_upper:
                return False, [f"Dangerous keyword '{keyword}' detected"], 0.0
        
        # Check for risky functions
        for func in cls.RISKY_FUNCTIONS:
            if func.upper() in sql_upper:
                return False, [f"Risky function '{func}' detected"], 0.0
        
        # Check for potential performance issues
        if 'SELECT *' in sql_upper:
            warnings.append("SELECT * may impact performance - consider specifying columns")
            safety_score -= 0.1
        
        # Check for missing WHERE clause on large tables
        if 'WHERE' not in sql_upper and 'LIMIT' not in sql_upper and 'TOP' not in sql_upper:
            warnings.append("Query lacks filtering - may return large result set")
            safety_score -= 0.2
        
        # Check for Cartesian products
        if 'JOIN' in sql_upper and 'ON' not in sql_upper:
            warnings.append("Potential Cartesian product - ensure proper join conditions")
            safety_score -= 0.3
        
        # Check for complex nested queries
        nested_count = sql_upper.count('SELECT') - 1
        if nested_count > 2:
            warnings.append("Complex nested query - consider breaking into steps")
            safety_score -= 0.1
        
        return True, warnings, max(0.0, safety_score)


class IntelligentSQLGenerator(LoggerMixin):
    """Generates SQL queries from natural language using schema knowledge"""
    
    def __init__(self):
        super().__init__()
        self.schema_manager = get_schema_manager()
        self.llm = self._initialize_llm()
        self.safety_validator = SafetyValidator()
        
        # Query patterns for different types of requests
        self.query_patterns = {
            'count': ['how many', 'count', 'total', 'number of'],
            'list': ['list', 'show', 'display', 'get', 'find'],
            'summary': ['summary', 'summarize', 'overview', 'aggregate'],
            'trend': ['trend', 'over time', 'by date', 'historical'],
            'comparison': ['compare', 'vs', 'versus', 'difference', 'between'],
            'top': ['top', 'highest', 'largest', 'maximum', 'best'],
            'bottom': ['bottom', 'lowest', 'smallest', 'minimum', 'worst']
        }
        
        # Common date filters
        self.date_patterns = {
            'today': "CAST(GETDATE() AS DATE) = CAST({column} AS DATE)",
            'yesterday': "CAST(GETDATE() - 1 AS DATE) = CAST({column} AS DATE)",
            'this week': "{column} >= DATEADD(WEEK, DATEDIFF(WEEK, 0, GETDATE()), 0)",
            'last week': "{column} >= DATEADD(WEEK, DATEDIFF(WEEK, 0, GETDATE()) - 1, 0) AND {column} < DATEADD(WEEK, DATEDIFF(WEEK, 0, GETDATE()), 0)",
            'this month': "{column} >= DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()), 0)",
            'last month': "{column} >= DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()) - 1, 0) AND {column} < DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()), 0)",
            'last 7 days': "{column} >= DATEADD(DAY, -7, GETDATE())",
            'last 30 days': "{column} >= DATEADD(DAY, -30, GETDATE())",
            'last 90 days': "{column} >= DATEADD(DAY, -90, GETDATE())"
        }
    
    def _initialize_llm(self) -> AzureChatOpenAI:
        """Initialize Azure OpenAI LLM"""
        azure_settings = get_azure_openai_settings()
        
        return AzureChatOpenAI(
            azure_deployment=azure_settings.deployment_chat,
            openai_api_version=azure_settings.api_version,
            azure_endpoint=str(azure_settings.endpoint),
            api_key=azure_settings.api_key,
            temperature=0.1,  # Low temperature for consistent SQL generation
            max_tokens=2000
        )
    
    async def generate_sql(self, natural_query: str, category: str = None) -> Dict[str, Any]:
        """Generate SQL from natural language query"""
        try:
            self.log_info(f"Generating SQL for query: {natural_query}")
            
            # Step 1: Analyze query and identify relevant tables
            query_analysis = await self._analyze_query(natural_query, category)
            
            if not query_analysis['relevant_tables']:
                return {
                    'success': False,
                    'error': 'No relevant tables found for the query',
                    'suggestions': await self._get_query_suggestions(natural_query)
                }
            
            # Step 2: Create query plan
            query_plan = await self._create_query_plan(natural_query, query_analysis)
            
            # Step 3: Generate SQL
            sql_result = await self._generate_sql_from_plan(query_plan, natural_query)
            
            if not sql_result['success']:
                return sql_result
            
            # Step 4: Validate and optimize
            validated_sql = self._validate_and_optimize_sql(sql_result['sql'], query_plan)
            
            # Step 5: Format final response
            response = {
                'success': True,
                'sql': validated_sql['sql'],
                'query_plan': {
                    'type': query_plan.query_type.value,
                    'complexity': query_plan.complexity.value,
                    'tables': query_plan.tables,
                    'estimated_rows': query_plan.estimated_rows,
                    'safety_score': validated_sql['safety_score']
                },
                'explanation': validated_sql['explanation'],
                'warnings': validated_sql['warnings'],
                'execution_tips': self._get_execution_tips(query_plan)
            }
            
            self.log_info("SQL generation completed successfully")
            return response
            
        except Exception as e:
            self.log_error(f"SQL generation failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'suggestions': ["Please rephrase your query", "Check table and column names"]
            }
    
    async def _analyze_query(self, query: str, category: str = None) -> Dict[str, Any]:
        """Analyze natural language query to understand intent and identify tables"""
        query_lower = query.lower()
        
        # Determine query type
        query_type = self._classify_query_type(query_lower)
        
        # Find relevant tables using vector search
        relevant_tables = await self._find_relevant_tables(query, category)
        
        # Extract entities (column names, values, etc.)
        entities = self._extract_entities(query_lower)
        
        # Determine time range if mentioned
        time_range = self._extract_time_range(query_lower)
        
        return {
            'query_type': query_type,
            'relevant_tables': relevant_tables,
            'entities': entities,
            'time_range': time_range,
            'original_query': query
        }
    
    def _classify_query_type(self, query: str) -> QueryType:
        """Classify the type of query based on patterns"""
        for pattern_type, patterns in self.query_patterns.items():
            if any(pattern in query for pattern in patterns):
                if pattern_type == 'count':
                    return QueryType.COUNT
                elif pattern_type in ['summary']:
                    return QueryType.SUMMARY
                elif pattern_type == 'trend':
                    return QueryType.TREND
                elif pattern_type == 'comparison':
                    return QueryType.COMPARISON
        
        return QueryType.SELECT
    
    async def _find_relevant_tables(self, query: str, category: str = None) -> List[Dict[str, Any]]:
        """Find tables relevant to the query using vector search and keyword matching"""
        relevant_tables = []
        
        # Use vector search to find relevant schemas
        vector_results = await self.schema_manager.search_schemas(query, limit=10)
        
        for result in vector_results:
            table_name = result['table_name']
            schema = self.schema_manager.get_table_schema(table_name)
            
            if schema:
                relevance_score = result['certainty']
                
                # Boost score if category matches
                if category and schema.category == category:
                    relevance_score += 0.2
                
                # Boost score for keyword matches in table/column names
                query_words = query.lower().split()
                for word in query_words:
                    if word in table_name.lower():
                        relevance_score += 0.1
                    for col in schema.get_column_names():
                        if word in col.lower():
                            relevance_score += 0.05
                
                relevant_tables.append({
                    'table_name': table_name,
                    'schema': schema,
                    'relevance_score': min(1.0, relevance_score),
                    'description': result.get('description', ''),
                    'columns': result.get('columns', [])
                })
        
        # Sort by relevance score
        relevant_tables.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return relevant_tables[:5]  # Return top 5 most relevant tables
    
    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        """Extract entities like numbers, dates, status values from query"""
        entities = {
            'numbers': [],
            'dates': [],
            'statuses': [],
            'ids': [],
            'names': []
        }
        
        # Extract numbers
        numbers = re.findall(r'\b\d+\.?\d*\b', query)
        entities['numbers'] = numbers
        
        # Extract potential dates
        date_patterns = [
            r'\b\d{4}-\d{2}-\d{2}\b',  # YYYY-MM-DD
            r'\b\d{2}/\d{2}/\d{4}\b',  # MM/DD/YYYY
            r'\b\d{1,2}/\d{1,2}/\d{4}\b'  # M/D/YYYY
        ]
        
        for pattern in date_patterns:
            dates = re.findall(pattern, query)
            entities['dates'].extend(dates)
        
        # Extract status-like words
        status_words = ['active', 'inactive', 'pending', 'completed', 'cancelled', 
                       'open', 'closed', 'approved', 'rejected']
        for word in status_words:
            if word in query:
                entities['statuses'].append(word)
        
        # Extract potential IDs (patterns like ABC123, 12345, etc.)
        id_patterns = [
            r'\b[A-Z]{2,4}\d{3,}\b',  # ABC123
            r'\b\d{6,}\b'  # 123456
        ]
        
        for pattern in id_patterns:
            ids = re.findall(pattern, query)
            entities['ids'].extend(ids)
        
        return entities
    
    def _extract_time_range(self, query: str) -> Optional[str]:
        """Extract time range from query"""
        for time_phrase, sql_condition in self.date_patterns.items():
            if time_phrase in query:
                return time_phrase
        
        # Check for specific date ranges
        if 'between' in query and 'and' in query:
            # Extract date range like "between 2023-01-01 and 2023-12-31"
            date_range_pattern = r'between\s+(\S+)\s+and\s+(\S+)'
            match = re.search(date_range_pattern, query, re.IGNORECASE)
            if match:
                return f"between {match.group(1)} and {match.group(2)}"
        
        return None
    
    async def _create_query_plan(self, query: str, analysis: Dict[str, Any]) -> QueryPlan:
        """Create detailed query execution plan"""
        relevant_tables = analysis['relevant_tables']
        
        if not relevant_tables:
            raise ValueError("No relevant tables found")
        
        # Start with the most relevant table
        primary_table = relevant_tables[0]
        tables = [primary_table['table_name']]
        
        # Determine if we need joins
        joins = []
        if len(relevant_tables) > 1:
            joins = await self._plan_joins(relevant_tables[:3])  # Max 3 tables for complexity
            tables.extend([join['to_table'] for join in joins])
        
        # Plan columns to select
        columns = await self._plan_columns(query, relevant_tables)
        
        # Plan filters
        filters = self._plan_filters(query, analysis, relevant_tables)
        
        # Plan aggregations
        aggregations = self._plan_aggregations(query, analysis['query_type'])
        
        # Plan grouping and ordering
        grouping, ordering = self._plan_grouping_ordering(query, columns, aggregations)
        
        # Determine complexity
        complexity = self._determine_complexity(len(tables), len(joins), len(aggregations))
        
        # Estimate result size
        estimated_rows = self._estimate_result_size(primary_table['schema'], filters)
        
        return QueryPlan(
            query_type=analysis['query_type'],
            complexity=complexity,
            tables=tables,
            columns=columns,
            joins=joins,
            filters=filters,
            aggregations=aggregations,
            grouping=grouping,
            ordering=ordering,
            estimated_rows=estimated_rows
        )
    
    async def _plan_joins(self, relevant_tables: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Plan joins between tables"""
        joins = []
        
        if len(relevant_tables) < 2:
            return joins
        
        primary_table = relevant_tables[0]['table_name']
        
        for i in range(1, len(relevant_tables)):
            secondary_table = relevant_tables[i]['table_name']
            
            # Find join path
            join_path = self.schema_manager.get_join_path(primary_table, secondary_table)
            
            if join_path:
                joins.extend(join_path)
            else:
                # Try to find common column names for join
                primary_schema = relevant_tables[0]['schema']
                secondary_schema = relevant_tables[i]['schema']
                
                common_columns = self._find_common_columns(
                    primary_schema.get_column_names(),
                    secondary_schema.get_column_names()
                )
                
                if common_columns:
                    joins.append({
                        'from_table': primary_table,
                        'to_table': secondary_table,
                        'from_column': common_columns[0],
                        'to_column': common_columns[0],
                        'join_type': 'INNER JOIN'
                    })
        
        return joins
    
    def _find_common_columns(self, cols1: List[str], cols2: List[str]) -> List[str]:
        """Find common column names between two tables"""
        common = []
        
        for col1 in cols1:
            for col2 in cols2:
                if col1.lower() == col2.lower():
                    common.append(col1)
                elif col1.lower().endswith('_id') and col2.lower().endswith('_id'):
                    # Check if they might be related IDs
                    base1 = col1.lower().replace('_id', '')
                    base2 = col2.lower().replace('_id', '')
                    if base1 == base2:
                        common.append(col1)
        
        return common
    
    async def _plan_columns(self, query: str, relevant_tables: List[Dict[str, Any]]) -> List[str]:
        """Plan which columns to select"""
        columns = []
        query_lower = query.lower()
        
        # If it's a count query, we might just need COUNT(*)
        if 'count' in query_lower or 'how many' in query_lower:
            return ['COUNT(*) as count']
        
        # Otherwise, determine relevant columns based on query content
        for table_info in relevant_tables:
            schema = table_info['schema']
            table_name = table_info['table_name']
            
            # Always include primary key
            if schema.primary_keys:
                columns.extend([f"{table_name}.{pk}" for pk in schema.primary_keys])
            
            # Add columns mentioned in query
            for col in schema.get_column_names():
                col_lower = col.lower()
                
                # Direct mention
                if col_lower in query_lower:
                    columns.append(f"{table_name}.{col}")
                
                # Common column patterns
                elif any(pattern in col_lower for pattern in ['name', 'description', 'status', 'date', 'time']):
                    if any(pattern in query_lower for pattern in ['name', 'description', 'status', 'date', 'time']):
                        columns.append(f"{table_name}.{col}")
                
                # Quantity-related columns for summary queries
                elif any(pattern in col_lower for pattern in ['quantity', 'amount', 'total', 'count']):
                    if any(pattern in query_lower for pattern in ['total', 'sum', 'amount', 'quantity']):
                        columns.append(f"{table_name}.{col}")
        
        # If no specific columns identified, select key descriptive columns
        if len(columns) <= len(relevant_tables):  # Only PKs selected
            for table_info in relevant_tables:
                schema = table_info['schema']
                table_name = table_info['table_name']
                
                # Add description columns
                for col in schema.get_column_names():
                    if any(pattern in col.lower() for pattern in ['description', 'name', 'title']):
                        columns.append(f"{table_name}.{col}")
                        break
        
        return list(set(columns))  # Remove duplicates
    
    def _plan_filters(self, query: str, analysis: Dict[str, Any], 
                     relevant_tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Plan WHERE clause filters"""
        filters = []
        
        # Add time-based filters
        if analysis['time_range']:
            time_columns = []
            for table_info in relevant_tables:
                schema = table_info['schema']
                for col in schema.get_column_names():
                    if any(pattern in col.lower() for pattern in ['date', 'time', 'created', 'updated']):
                        time_columns.append(f"{table_info['table_name']}.{col}")
            
            if time_columns:
                time_condition = self.date_patterns.get(analysis['time_range'])
                if time_condition:
                    filters.append({
                        'type': 'date_filter',
                        'column': time_columns[0],  # Use first date column found
                        'condition': time_condition.format(column=time_columns[0]),
                        'description': f"Filter for {analysis['time_range']}"
                    })
        
        # Add entity-based filters
        entities = analysis['entities']
        
        # Status filters
        if entities['statuses']:
            for table_info in relevant_tables:
                schema = table_info['schema']
                for col in schema.get_column_names():
                    if 'status' in col.lower():
                        for status in entities['statuses']:
                            filters.append({
                                'type': 'status_filter',
                                'column': f"{table_info['table_name']}.{col}",
                                'value': status,
                                'condition': f"{table_info['table_name']}.{col} = '{status}'",
                                'description': f"Filter by status: {status}"
                            })
        
        # ID filters
        if entities['ids']:
            for table_info in relevant_tables:
                schema = table_info['schema']
                for col in schema.get_column_names():
                    if col.lower().endswith('_id') or col.lower() == 'id':
                        for id_val in entities['ids']:
                            filters.append({
                                'type': 'id_filter',
                                'column': f"{table_info['table_name']}.{col}",
                                'value': id_val,
                                'condition': f"{table_info['table_name']}.{col} = '{id_val}'",
                                'description': f"Filter by ID: {id_val}"
                            })
        
        return filters
    
    def _plan_aggregations(self, query: str, query_type: QueryType) -> List[Dict[str, str]]:
        """Plan aggregation functions"""
        aggregations = []
        query_lower = query.lower()
        
        if query_type == QueryType.COUNT:
            aggregations.append({
                'function': 'COUNT',
                'column': '*',
                'alias': 'total_count'
            })
        elif query_type == QueryType.SUMMARY:
            # Look for aggregation keywords
            if 'sum' in query_lower or 'total' in query_lower:
                aggregations.append({
                    'function': 'SUM',
                    'column': 'quantity',  # Will be replaced with actual column
                    'alias': 'total_amount'
                })
            
            if 'average' in query_lower or 'avg' in query_lower:
                aggregations.append({
                    'function': 'AVG',
                    'column': 'quantity',
                    'alias': 'average_amount'
                })
            
            if 'max' in query_lower or 'maximum' in query_lower or 'highest' in query_lower:
                aggregations.append({
                    'function': 'MAX',
                    'column': 'quantity',
                    'alias': 'max_amount'
                })
            
            if 'min' in query_lower or 'minimum' in query_lower or 'lowest' in query_lower:
                aggregations.append({
                    'function': 'MIN',
                    'column': 'quantity',
                    'alias': 'min_amount'
                })
        
        return aggregations
    
    def _plan_grouping_ordering(self, query: str, columns: List[str], 
                               aggregations: List[Dict[str, str]]) -> Tuple[List[str], List[Dict[str, str]]]:
        """Plan GROUP BY and ORDER BY clauses"""
        grouping = []
        ordering = []
        
        query_lower = query.lower()
        
        # If we have aggregations, we need grouping
        if aggregations:
            # Group by non-aggregate columns
            for col in columns:
                if not any(agg_func in col.upper() for agg_func in ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN']):
                    if '.' in col:  # Qualified column name
                        grouping.append(col)
        
        # Determine ordering
        if 'order by' in query_lower:
            # Extract explicit ORDER BY
            order_match = re.search(r'order\s+by\s+(\w+)', query_lower)
            if order_match:
                ordering.append({
                    'column': order_match.group(1),
                    'direction': 'ASC'
                })
        else:
            # Implicit ordering based on keywords
            if any(keyword in query_lower for keyword in ['top', 'highest', 'largest', 'maximum']):
                # Order by first numeric column DESC
                for col in columns:
                    if any(pattern in col.lower() for pattern in ['quantity', 'amount', 'total', 'count']):
                        ordering.append({
                            'column': col,
                            'direction': 'DESC'
                        })
                        break
            
            elif any(keyword in query_lower for keyword in ['bottom', 'lowest', 'smallest', 'minimum']):
                # Order by first numeric column ASC
                for col in columns:
                    if any(pattern in col.lower() for pattern in ['quantity', 'amount', 'total', 'count']):
                        ordering.append({
                            'column': col,
                            'direction': 'ASC'
                        })
                        break
        
        return grouping, ordering
    
    def _determine_complexity(self, table_count: int, join_count: int, aggregation_count: int) -> QueryComplexity:
        """Determine query complexity level"""
        if table_count == 1 and join_count == 0 and aggregation_count <= 1:
            return QueryComplexity.SIMPLE
        elif table_count <= 3 and join_count <= 2 and aggregation_count <= 3:
            return QueryComplexity.MODERATE
        elif table_count <= 5 and join_count <= 4:
            return QueryComplexity.COMPLEX
        else:
            return QueryComplexity.ADVANCED
    
    def _estimate_result_size(self, primary_schema: TableSchema, filters: List[Dict[str, Any]]) -> int:
        """Estimate number of rows the query will return"""
        base_rows = primary_schema.row_count or 1000
        
        # Apply filter reduction estimates
        reduction_factor = 1.0
        
        for filter_info in filters:
            if filter_info['type'] == 'date_filter':
                if 'today' in filter_info.get('description', '').lower():
                    reduction_factor *= 0.01  # Assume 1% of data is from today
                elif 'week' in filter_info.get('description', '').lower():
                    reduction_factor *= 0.1   # 10% for week
                elif 'month' in filter_info.get('description', '').lower():
                    reduction_factor *= 0.25  # 25% for month
            
            elif filter_info['type'] == 'id_filter':
                reduction_factor *= 0.001  # Very specific filter
            
            elif filter_info['type'] == 'status_filter':
                reduction_factor *= 0.2   # 20% for typical status filter
        
        return max(1, int(base_rows * reduction_factor))
    
    async def _generate_sql_from_plan(self, plan: QueryPlan, original_query: str) -> Dict[str, Any]:
        """Generate actual SQL from the query plan"""
        try:
            # Build SQL components
            select_clause = self._build_select_clause(plan.columns, plan.aggregations)
            from_clause = self._build_from_clause(plan.tables[0])
            join_clause = self._build_join_clause(plan.joins)
            where_clause = self._build_where_clause(plan.filters)
            group_by_clause = self._build_group_by_clause(plan.grouping)
            order_by_clause = self._build_order_by_clause(plan.ordering)
            limit_clause = self._build_limit_clause(plan.limit, plan.estimated_rows)
            
            # Combine into final SQL
            sql_parts = [select_clause, from_clause]
            
            if join_clause:
                sql_parts.append(join_clause)
            if where_clause:
                sql_parts.append(where_clause)
            if group_by_clause:
                sql_parts.append(group_by_clause)
            if order_by_clause:
                sql_parts.append(order_by_clause)
            if limit_clause:
                sql_parts.append(limit_clause)
            
            sql = '\n'.join(sql_parts)
            
            # Format SQL
            formatted_sql = sql_format(sql, reindent=True, keyword_case='upper')
            
            return {
                'success': True,
                'sql': formatted_sql,
                'explanation': f"Generated SQL for: {original_query}"
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"SQL generation failed: {str(e)}"
            }
    
    def _build_select_clause(self, columns: List[str], aggregations: List[Dict[str, str]]) -> str:
        """Build SELECT clause"""
        if aggregations:
            select_items = []
            for agg in aggregations:
                if agg['column'] == '*':
                    select_items.append(f"{agg['function']}(*) AS {agg['alias']}")
                else:
                    select_items.append(f"{agg['function']}({agg['column']}) AS {agg['alias']}")
            
            # Add non-aggregate columns for grouping
            for col in columns:
                if not any(func in col.upper() for func in ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN']):
                    select_items.append(col)
            
            return f"SELECT {', '.join(select_items)}"
        else:
            if columns:
                return f"SELECT {', '.join(columns)}"
            else:
                return "SELECT *"
    
    def _build_from_clause(self, table: str) -> str:
        """Build FROM clause"""
        return f"FROM {table}"
    
    def _build_join_clause(self, joins: List[Dict[str, str]]) -> str:
        """Build JOIN clauses"""
        if not joins:
            return ""
        
        join_parts = []
        for join in joins:
            join_parts.append(
                f"{join['join_type']} {join['to_table']} ON "
                f"{join['from_table']}.{join['from_column']} = {join['to_table']}.{join['to_column']}"
            )
        
        return '\n'.join(join_parts)
    
    def _build_where_clause(self, filters: List[Dict[str, Any]]) -> str:
        """Build WHERE clause"""
        if not filters:
            return ""
        
        conditions = [f"({filter_info['condition']})" for filter_info in filters]
        return f"WHERE {' AND '.join(conditions)}"
    
    def _build_group_by_clause(self, grouping: List[str]) -> str:
        """Build GROUP BY clause"""
        if not grouping:
            return ""
        
        return f"GROUP BY {', '.join(grouping)}"
    
    def _build_order_by_clause(self, ordering: List[Dict[str, str]]) -> str:
        """Build ORDER BY clause"""
        if not ordering:
            return ""
        
        order_items = [f"{order['column']} {order['direction']}" for order in ordering]
        return f"ORDER BY {', '.join(order_items)}"
    
    def _build_limit_clause(self, limit: Optional[int], estimated_rows: Optional[int]) -> str:
        """Build LIMIT/TOP clause for safety"""
        # Use explicit limit or safety limit based on estimated size
        if limit:
            return f"-- LIMIT {limit}  -- Use appropriate syntax for MS SQL (TOP clause)"
        elif estimated_rows and estimated_rows > 10000:
            return "-- Consider adding TOP clause to limit results"
        
        return ""
    
    def _validate_and_optimize_sql(self, sql: str, plan: QueryPlan) -> Dict[str, Any]:
        """Validate and optimize generated SQL"""
        is_safe, warnings, safety_score = self.safety_validator.validate_query(sql)
        
        if not is_safe:
            return {
                'sql': sql,
                'safety_score': 0.0,
                'warnings': warnings,
                'explanation': "Query failed safety validation"
            }
        
        # Add optimization suggestions
        optimizations = []
        
        if plan.estimated_rows and plan.estimated_rows > 1000:
            optimizations.append("Consider adding more specific filters to reduce result size")
        
        if len(plan.tables) > 3:
            optimizations.append("Complex multi-table query - ensure proper indexing on join columns")
        
        if not any('WHERE' in warning for warning in warnings):
            optimizations.append("Query performance looks good")
        
        return {
            'sql': sql,
            'safety_score': safety_score,
            'warnings': warnings + optimizations,
            'explanation': f"Generated {plan.complexity.value.lower()} {plan.query_type.value.lower()} query involving {len(plan.tables)} table(s)"
        }
    
    def _get_execution_tips(self, plan: QueryPlan) -> List[str]:
        """Get tips for query execution"""
        tips = []
        
        if plan.complexity == QueryComplexity.COMPLEX:
            tips.append("This is a complex query - consider breaking it into smaller parts if performance is slow")
        
        if plan.estimated_rows and plan.estimated_rows > 5000:
            tips.append("Large result set expected - consider using pagination or additional filters")
        
        if len(plan.joins) > 2:
            tips.append("Multiple joins detected - ensure proper indexes exist on join columns")
        
        if plan.query_type == QueryType.TREND:
            tips.append("Time-based analysis - ensure date columns are indexed")
        
        tips.append("Always test queries on a small dataset first")
        
        return tips
    
    async def _get_query_suggestions(self, query: str) -> List[str]:
        """Get suggestions when query fails"""
        suggestions = [
            "Try using more specific table or column names",
            "Check if the data you're looking for exists in the system",
            "Use simpler language and avoid technical jargon",
            "Specify a time range if looking for recent data"
        ]
        
        # Add category-specific suggestions
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['order', 'pick', 'ship']):
            suggestions.append("Try: 'Show me orders from last week' or 'List picking tasks today'")
        
        if any(word in query_lower for word in ['inventory', 'stock', 'quantity']):
            suggestions.append("Try: 'Show inventory levels' or 'Items with low stock'")
        
        if any(word in query_lower for word in ['location', 'bin', 'zone']):
            suggestions.append("Try: 'Show all locations' or 'Locations in zone A'")
        
        return suggestions


# Global instance
_sql_generator: Optional[IntelligentSQLGenerator] = None


def get_sql_generator() -> IntelligentSQLGenerator:
    """Get or create global SQL generator instance"""
    global _sql_generator
    
    if _sql_generator is None:
        _sql_generator = IntelligentSQLGenerator()
    
    return _sql_generator