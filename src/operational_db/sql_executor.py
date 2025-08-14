"""
SQL Query Executor for Operational Database
Safely executes SQL queries generated from natural language against operational MS SQL database.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from contextlib import asynccontextmanager

import pymssql
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import SQLAlchemyError

from ..core.config import get_settings
from ..core.logging import LoggerMixin
from .schema_manager import get_schema_manager
from .sql_generator import get_sql_generator, QueryPlan
from .performance_optimizer import get_performance_optimizer


@dataclass
class ExecutionResult:
    """Represents query execution result"""
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    row_count: int = 0
    execution_time: float = 0.0
    query_used: str = ""
    warnings: List[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ConnectionInfo:
    """Database connection information"""
    server: str
    database: str
    username: str
    password: str
    port: int = 1433
    
    def get_connection_string(self) -> str:
        """Get SQLAlchemy connection string"""
        return f"mssql+pymssql://{self.username}:{self.password}@{self.server}:{self.port}/{self.database}"


class OperationalSQLExecutor(LoggerMixin):
    """Executes SQL queries safely against operational database"""
    
    def __init__(self):
        super().__init__()
        self.schema_manager = get_schema_manager()
        self.sql_generator = get_sql_generator()
        self.performance_optimizer = get_performance_optimizer()
        self.connection_info: Optional[ConnectionInfo] = None
        self.engine: Optional[Engine] = None
        
        # Safety limits
        self.max_rows = 10000
        self.query_timeout = 300  # 5 minutes
        self.max_concurrent_queries = 3
        
        # Query statistics
        self.query_stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "avg_execution_time": 0.0,
            "last_query_time": None
        }
        
        # Active connections tracking
        self.active_connections = 0
    
    def set_connection(self, connection_info: ConnectionInfo) -> bool:
        """Set database connection information"""
        try:
            self.connection_info = connection_info
            
            # Create engine with safety settings
            self.engine = create_engine(
                connection_info.get_connection_string(),
                poolclass=NullPool,  # No connection pooling for safety
                pool_pre_ping=True,  # Verify connections
                echo=False,
                connect_args={
                    "timeout": 30,  # Connection timeout
                    "login_timeout": 30,
                    "autocommit": True  # Prevent accidental transactions
                }
            )
            
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # Update schema manager connection
            self.schema_manager.set_connection(connection_info.get_connection_string())
            
            # Update performance optimizer engine
            self.performance_optimizer.set_engine(self.engine)
            
            self.log_info("Operational database connection established")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to establish connection: {e}")
            self.engine = None
            return False
    
    async def execute_natural_query(self, natural_query: str, 
                                  category: str = None,
                                  max_rows: int = None) -> ExecutionResult:
        """Execute natural language query against operational database"""
        start_time = datetime.utcnow()
        
        try:
            if not self.engine:
                return ExecutionResult(
                    success=False,
                    error="Database connection not established"
                )
            
            # Check concurrent query limit
            if self.active_connections >= self.max_concurrent_queries:
                return ExecutionResult(
                    success=False,
                    error="Too many concurrent queries. Please try again later."
                )
            
            self.log_info(f"Processing natural query: {natural_query}")
            
            # Step 1: Generate SQL from natural language
            sql_result = await self.sql_generator.generate_sql(natural_query, category)
            
            if not sql_result['success']:
                return ExecutionResult(
                    success=False,
                    error=sql_result['error'],
                    warnings=sql_result.get('suggestions', [])
                )
            
            # Step 2: Analyze query performance before execution
            performance_analysis = await self.performance_optimizer.analyze_query_performance(sql_result['sql'])
            
            # Step 3: Get result size impact analysis
            estimated_rows = sql_result.get('query_plan', {}).get('estimated_rows', 0)
            size_impact = self._estimate_result_size_impact(sql_result['sql'], estimated_rows)
            
            # Step 4: Get index recommendations
            index_recommendations = performance_analysis.get('index_recommendations', [])
            index_suggestions = [f"{rec.reason}: {rec.sql_create_statement}" for rec in index_recommendations[:3]]
            
            # Step 5: Execute the SQL query
            execution_result = await self._execute_sql_query(
                sql=sql_result['sql'],
                max_rows=max_rows or self.max_rows,
                query_plan=sql_result.get('query_plan'),
                performance_analysis=performance_analysis,
                size_impact=size_impact,
                index_suggestions=index_suggestions
            )
            
            # Add SQL generation metadata
            execution_result.metadata.update({
                'original_query': natural_query,
                'generated_sql': sql_result['sql'],
                'query_plan': sql_result.get('query_plan'),
                'sql_explanation': sql_result.get('explanation'),
                'execution_tips': sql_result.get('execution_tips', [])
            })
            
            # Update statistics
            self._update_statistics(execution_result, start_time)
            
            self.log_info(f"Query executed successfully. Returned {execution_result.row_count} rows")
            return execution_result
            
        except Exception as e:
            self.log_error(f"Query execution failed: {e}")
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    async def _execute_sql_query(self, sql: str, max_rows: int,
                               query_plan: Dict[str, Any] = None,
                               performance_analysis: Dict[str, Any] = None,
                               size_impact: Dict[str, Any] = None,
                               index_suggestions: List[str] = None) -> ExecutionResult:
        """Execute SQL query with safety checks"""
        self.active_connections += 1
        start_time = datetime.utcnow()
        
        try:
            # Add safety limit to SQL
            safe_sql = self._add_row_limit(sql, max_rows)
            
            # Execute query with timeout
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self._execute_sync_query, 
                safe_sql, 
                self.query_timeout
            )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            if result['success']:
                # Combine all warnings and suggestions
                all_warnings = result.get('warnings', [])
                
                # Add performance warnings
                if performance_analysis:
                    all_warnings.extend(performance_analysis.get('warnings', []))
                    all_warnings.extend(performance_analysis.get('optimization_suggestions', []))
                
                # Add size impact recommendations
                if size_impact and size_impact.get('recommendations'):
                    all_warnings.extend(size_impact['recommendations'])
                
                # Add index suggestions
                if index_suggestions:
                    all_warnings.extend([f"Performance tip: {suggestion}" for suggestion in index_suggestions])
                
                return ExecutionResult(
                    success=True,
                    data=result['data'],
                    row_count=len(result['data']),
                    execution_time=execution_time,
                    query_used=safe_sql,
                    warnings=all_warnings,
                    metadata={
                        'truncated': result.get('truncated', False),
                        'query_plan': query_plan,
                        'performance_analysis': performance_analysis,
                        'size_impact': size_impact,
                        'index_suggestions': index_suggestions,
                        'result_quality': self._assess_result_quality(len(result['data']), safe_sql)
                    }
                )
            else:
                return ExecutionResult(
                    success=False,
                    error=result['error'],
                    execution_time=execution_time,
                    query_used=safe_sql
                )
                
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
                query_used=sql
            )
        finally:
            self.active_connections -= 1
    
    def _execute_sync_query(self, sql: str, timeout: int) -> Dict[str, Any]:
        """Execute query synchronously with timeout"""
        try:
            with self.engine.connect() as conn:
                # Set query timeout
                conn.execute(text(f"SET LOCK_TIMEOUT {timeout * 1000}"))  # Convert to milliseconds
                
                # Execute main query
                result = conn.execute(text(sql))
                
                # Convert to list of dictionaries
                data = []
                columns = list(result.keys())
                
                for row in result:
                    row_dict = {}
                    for i, value in enumerate(row):
                        # Handle different data types
                        if isinstance(value, datetime):
                            row_dict[columns[i]] = value.isoformat()
                        elif isinstance(value, (bytes, bytearray)):
                            # Handle binary data
                            row_dict[columns[i]] = f"<binary data: {len(value)} bytes>"
                        elif value is None:
                            row_dict[columns[i]] = None
                        else:
                            row_dict[columns[i]] = str(value) if not isinstance(value, (int, float, bool)) else value
                    
                    data.append(row_dict)
                
                warnings = []
                if len(data) >= self.max_rows:
                    warnings.append(f"Results limited to {self.max_rows} rows")
                
                return {
                    'success': True,
                    'data': data,
                    'warnings': warnings,
                    'truncated': len(data) >= self.max_rows
                }
                
        except SQLAlchemyError as e:
            return {
                'success': False,
                'error': f"SQL execution error: {str(e)}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }
    
    def _add_row_limit(self, sql: str, max_rows: int) -> str:
        """Intelligently add row limits only when appropriate"""
        sql_upper = sql.upper().strip()
        
        # Check if TOP/LIMIT is already present
        if ('TOP' in sql_upper and sql_upper.find('TOP') < sql_upper.find('FROM')) or 'LIMIT' in sql_upper:
            return sql
        
        # Don't add limits for aggregation queries (COUNT, SUM, AVG, etc.)
        aggregation_functions = ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN(', 'GROUP BY']
        if any(func in sql_upper for func in aggregation_functions):
            # For aggregation queries, warn user instead of limiting
            return f"-- Warning: This aggregation query may return large result sets\n{sql}"
        
        # Don't add limits for summary/reporting queries
        summary_indicators = ['DISTINCT', 'GROUP BY', 'HAVING']
        if any(indicator in sql_upper for indicator in summary_indicators):
            return sql
        
        # Check if query has proper WHERE clause for filtering
        has_where_clause = 'WHERE' in sql_upper
        has_date_filter = any(date_word in sql_upper for date_word in ['DATE', 'GETDATE', 'TODAY', 'YESTERDAY'])
        
        # If query lacks filtering, add TOP with warning
        if not has_where_clause and not has_date_filter:
            select_pos = sql_upper.find('SELECT')
            if select_pos != -1:
                before_select = sql[:select_pos + 6]
                after_select = sql[select_pos + 6:]
                warning = f"-- WARNING: Query lacks filtering. Results limited to {max_rows} rows for safety.\n"
                warning += f"-- Consider adding WHERE clause for more specific results.\n"
                return f"{warning}{before_select} TOP {max_rows}{after_select}"
        
        return sql
    
    async def _analyze_query_performance(self, sql: str) -> Dict[str, Any]:
        """Analyze query for performance issues and suggest optimizations"""
        performance_analysis = {
            'estimated_cost': 'unknown',
            'missing_indexes': [],
            'optimization_suggestions': [],
            'warnings': []
        }
        
        try:
            if not self.engine:
                return performance_analysis
            
            with self.engine.connect() as conn:
                # Get query execution plan (SQL Server specific)
                plan_query = f"SET SHOWPLAN_ALL ON; {sql}; SET SHOWPLAN_ALL OFF"
                
                try:
                    result = conn.execute(text("SET SHOWPLAN_ALL ON"))
                    plan_result = conn.execute(text(sql))
                    conn.execute(text("SET SHOWPLAN_ALL OFF"))
                    
                    # Parse execution plan for optimization opportunities
                    for row in plan_result:
                        if hasattr(row, 'LogicalOp') and 'Scan' in str(row.LogicalOp):
                            performance_analysis['warnings'].append(
                                f"Table scan detected on {row.Argument}. Consider adding index."
                            )
                        
                        if hasattr(row, 'EstimateRows') and int(row.EstimateRows or 0) > 100000:
                            performance_analysis['warnings'].append(
                                "Large result set estimated. Consider more selective filters."
                            )
                
                except Exception:
                    # Fallback to basic analysis if execution plan fails
                    pass
            
            # Basic SQL analysis for common performance issues
            sql_upper = sql.upper()
            
            # Check for SELECT *
            if 'SELECT *' in sql_upper:
                performance_analysis['optimization_suggestions'].append(
                    "Replace SELECT * with specific column names to improve performance"
                )
            
            # Check for functions in WHERE clause
            if any(func in sql_upper for func in ['SUBSTRING(', 'UPPER(', 'LOWER(', 'CONVERT(']):
                where_pos = sql_upper.find('WHERE')
                if where_pos > 0:
                    where_clause = sql_upper[where_pos:]
                    if any(func in where_clause for func in ['SUBSTRING(', 'UPPER(', 'LOWER(', 'CONVERT(']):
                        performance_analysis['optimization_suggestions'].append(
                            "Avoid functions in WHERE clause. Consider computed columns or pre-filtering."
                        )
            
            # Check for OR conditions
            if ' OR ' in sql_upper and 'WHERE' in sql_upper:
                performance_analysis['optimization_suggestions'].append(
                    "Consider rewriting OR conditions as UNION for better index usage"
                )
            
            # Check for leading wildcards in LIKE
            if "LIKE '%%" in sql_upper or "LIKE N'%" in sql_upper:
                performance_analysis['optimization_suggestions'].append(
                    "Leading wildcards in LIKE prevent index usage. Consider full-text search."
                )
                
        except Exception as e:
            performance_analysis['warnings'].append(f"Performance analysis failed: {str(e)}")
        
        return performance_analysis
    
    async def _suggest_indexes(self, sql: str, table_schemas: List) -> List[str]:
        """Suggest missing indexes based on query patterns"""
        suggestions = []
        sql_upper = sql.upper()
        
        # Extract table and column information
        where_pos = sql_upper.find('WHERE')
        join_positions = [sql_upper.find(join_type) for join_type in ['JOIN', 'INNER JOIN', 'LEFT JOIN', 'RIGHT JOIN'] if join_type in sql_upper]
        
        # Analyze WHERE clause columns
        if where_pos > 0:
            where_clause = sql_upper[where_pos:]
            
            # Common WHERE patterns that benefit from indexes
            for schema in table_schemas:
                table_name = schema.get('table_name', '')
                columns = schema.get('columns', [])
                
                for col in columns:
                    col_name = col.get('name', '').upper()
                    
                    # Column used in WHERE clause
                    if f"{col_name} =" in where_clause or f"{col_name} IN" in where_clause:
                        suggestions.append(f"Consider index on {table_name}.{col_name} (equality filter)")
                    
                    # Column used in range queries
                    elif any(op in where_clause for op in [f"{col_name} >", f"{col_name} <", f"{col_name} BETWEEN"]):
                        suggestions.append(f"Consider index on {table_name}.{col_name} (range filter)")
        
        # Analyze JOIN columns
        if join_positions:
            for schema in table_schemas:
                table_name = schema.get('table_name', '')
                foreign_keys = schema.get('foreign_keys', [])
                
                for fk in foreign_keys:
                    fk_columns = fk.get('columns', [])
                    if fk_columns:
                        suggestions.append(f"Ensure index exists on {table_name}.{fk_columns[0]} (join column)")
        
        # Remove duplicates and limit suggestions
        return list(set(suggestions))[:5]
    
    def _estimate_result_size_impact(self, sql: str, estimated_rows: int) -> Dict[str, Any]:
        """Estimate the impact of result size on performance and user experience"""
        impact_analysis = {
            'size_category': 'small',
            'performance_impact': 'low',
            'user_experience_impact': 'good',
            'recommendations': []
        }
        
        if estimated_rows <= 100:
            impact_analysis.update({
                'size_category': 'small',
                'performance_impact': 'low', 
                'user_experience_impact': 'excellent'
            })
        elif estimated_rows <= 1000:
            impact_analysis.update({
                'size_category': 'medium',
                'performance_impact': 'low',
                'user_experience_impact': 'good'
            })
        elif estimated_rows <= 10000:
            impact_analysis.update({
                'size_category': 'large',
                'performance_impact': 'medium',
                'user_experience_impact': 'acceptable',
                'recommendations': [
                    'Consider pagination for better user experience',
                    'Add more specific filters to reduce result size'
                ]
            })
        else:
            impact_analysis.update({
                'size_category': 'very_large',
                'performance_impact': 'high',
                'user_experience_impact': 'poor',
                'recommendations': [
                    'CRITICAL: Add WHERE clause to filter results',
                    'Consider summary/aggregation instead of detailed data',
                    'Implement pagination or streaming for large datasets',
                    'Use date ranges or other selective filters'
                ]
            })
        
        # Check for aggregation that might reduce actual result size
        sql_upper = sql.upper()
        if any(agg in sql_upper for agg in ['COUNT(', 'SUM(', 'AVG(', 'GROUP BY']):
            impact_analysis['user_experience_impact'] = 'good'
            impact_analysis['recommendations'].insert(0, 'Aggregation query - actual result size likely smaller')
        
        return impact_analysis
    
    def _assess_result_quality(self, row_count: int, sql: str) -> Dict[str, Any]:
        """Assess the quality and completeness of query results"""
        quality_assessment = {
            'completeness': 'complete',
            'reliability': 'high',
            'warnings': [],
            'user_guidance': []
        }
        
        sql_upper = sql.upper()
        
        # Check if results were truncated by our safety limits
        if 'TOP' in sql_upper and row_count >= 1000:
            quality_assessment.update({
                'completeness': 'partial',
                'reliability': 'medium',
                'warnings': ['Results may be incomplete due to safety limits'],
                'user_guidance': [
                    'Add more specific filters to see complete results',
                    'Consider using summary queries for large datasets'
                ]
            })
        
        # Check for queries that might miss data due to lack of filtering
        if 'WHERE' not in sql_upper and row_count > 0:
            quality_assessment['warnings'].append(
                'Query without filtering may not represent current operational state'
            )
            quality_assessment['user_guidance'].append(
                'Add date/time filters for current operational data'
            )
        
        # Check for aggregation queries (usually complete)
        if any(agg in sql_upper for agg in ['COUNT(', 'SUM(', 'AVG(', 'GROUP BY']):
            quality_assessment.update({
                'completeness': 'complete',
                'reliability': 'high'
            })
        
        # Check for empty results
        if row_count == 0:
            quality_assessment.update({
                'completeness': 'empty',
                'reliability': 'unknown',
                'user_guidance': [
                    'No data found matching criteria',
                    'Try broader search terms or different time periods',
                    'Verify table names and column filters'
                ]
            })
        
        return quality_assessment
    
    def _update_statistics(self, result: ExecutionResult, start_time: datetime):
        """Update query execution statistics"""
        self.query_stats["total_queries"] += 1
        self.query_stats["last_query_time"] = datetime.utcnow().isoformat()
        
        if result.success:
            self.query_stats["successful_queries"] += 1
        else:
            self.query_stats["failed_queries"] += 1
        
        # Update average execution time
        total_queries = self.query_stats["total_queries"]
        current_avg = self.query_stats["avg_execution_time"]
        new_time = result.execution_time
        
        self.query_stats["avg_execution_time"] = (
            (current_avg * (total_queries - 1) + new_time) / total_queries
        )
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test database connection and return basic info"""
        try:
            if not self.engine:
                return {
                    'connected': False,
                    'error': 'No connection established'
                }
            
            with self.engine.connect() as conn:
                # Get basic database info
                db_info = {}
                
                # Database name and version
                result = conn.execute(text("SELECT @@VERSION as version, DB_NAME() as database_name"))
                row = result.first()
                if row:
                    db_info['version'] = row[0]
                    db_info['database_name'] = row[1]
                
                # Table count
                result = conn.execute(text("""
                    SELECT COUNT(*) as table_count 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_TYPE = 'BASE TABLE'
                """))
                row = result.first()
                if row:
                    db_info['table_count'] = row[0]
                
                return {
                    'connected': True,
                    'database_info': db_info,
                    'query_stats': self.query_stats
                }
                
        except Exception as e:
            return {
                'connected': False,
                'error': str(e)
            }
    
    async def get_query_suggestions(self, category: str = None) -> List[str]:
        """Get suggested queries for the current database"""
        suggestions = [
            "Show me all orders from today",
            "List items with low inventory",
            "What are the recent inventory movements?",
            "Show picking tasks that are pending",
            "Display location utilization summary",
            "How many receipts were processed this week?",
            "Show work assignments by user",
            "What items need replenishment?",
            "Display shipping summary for this month",
            "Show cycle count accuracy metrics"
        ]
        
        # Add category-specific suggestions
        if category:
            category_suggestions = {
                'inventory_management': [
                    "Show current inventory levels by location",
                    "List items below minimum stock level",
                    "Display inventory accuracy by zone"
                ],
                'locations': [
                    "Show all active locations",
                    "Display location capacity utilization",
                    "List locations by zone"
                ],
                'receiving': [
                    "Show today's receipts",
                    "List pending ASNs",
                    "Display receiving performance metrics"
                ],
                'picking': [
                    "Show open pick tasks",
                    "Display picking productivity by user",
                    "List priority orders"
                ],
                'shipping': [
                    "Show today's shipments",
                    "Display carrier performance",
                    "List pending outbound orders"
                ]
            }
            
            if category in category_suggestions:
                suggestions.extend(category_suggestions[category])
        
        return suggestions
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get query execution statistics"""
        return {
            **self.query_stats,
            'active_connections': self.active_connections,
            'max_concurrent_queries': self.max_concurrent_queries,
            'max_rows_limit': self.max_rows,
            'query_timeout_seconds': self.query_timeout
        }
    
    def format_result_for_display(self, result: ExecutionResult) -> Dict[str, Any]:
        """Format execution result for user-friendly display"""
        if not result.success:
            return {
                'success': False,
                'error': result.error,
                'suggestions': result.warnings
            }
        
        # Format data for display
        display_data = result.data
        if result.row_count > 100:  # Limit display for large results
            display_data = result.data[:100]
        
        # Get performance and quality information
        performance_analysis = result.metadata.get('performance_analysis', {})
        size_impact = result.metadata.get('size_impact', {})
        result_quality = result.metadata.get('result_quality', {})
        
        formatted_result = {
            'success': True,
            'data': display_data,
            'summary': {
                'row_count': result.row_count,
                'execution_time': f"{result.execution_time:.3f} seconds",
                'showing': min(100, result.row_count),
                'total': result.row_count
            },
            'query_info': {
                'original_query': result.metadata.get('original_query', ''),
                'sql_used': result.query_used,
                'explanation': result.metadata.get('sql_explanation', ''),
                'tips': result.metadata.get('execution_tips', [])
            },
            'warnings': result.warnings
        }
        
        # Add quality assessment
        if result_quality:
            formatted_result['data_quality'] = {
                'completeness': result_quality.get('completeness', 'unknown'),
                'reliability': result_quality.get('reliability', 'unknown'),
                'user_guidance': result_quality.get('user_guidance', [])
            }
        
        # Add performance insights
        if performance_analysis:
            formatted_result['performance'] = {
                'classification': performance_analysis.get('query_classification', {}),
                'issues_found': len(performance_analysis.get('performance_issues', [])),
                'optimization_suggestions': performance_analysis.get('optimization_suggestions', [])[:3],
                'index_recommendations': len(performance_analysis.get('index_recommendations', [])),
                'estimated_improvement': performance_analysis.get('estimated_improvement', {})
            }
        
        # Add size impact information
        if size_impact:
            formatted_result['result_impact'] = {
                'size_category': size_impact.get('size_category', 'unknown'),
                'user_experience': size_impact.get('user_experience_impact', 'unknown'),
                'performance_impact': size_impact.get('performance_impact', 'unknown')
            }
        
        return formatted_result


# Global instance
_sql_executor: Optional[OperationalSQLExecutor] = None


def get_sql_executor() -> OperationalSQLExecutor:
    """Get or create global SQL executor instance"""
    global _sql_executor
    
    if _sql_executor is None:
        _sql_executor = OperationalSQLExecutor()
    
    return _sql_executor


async def execute_operational_query(natural_query: str, 
                                   connection_info: ConnectionInfo,
                                   category: str = None,
                                   max_rows: int = 1000) -> ExecutionResult:
    """Convenience function to execute operational database query"""
    executor = get_sql_executor()
    
    # Set connection if needed
    if not executor.engine or executor.connection_info != connection_info:
        success = executor.set_connection(connection_info)
        if not success:
            return ExecutionResult(
                success=False,
                error="Failed to establish database connection"
            )
    
    # Execute query
    return await executor.execute_natural_query(
        natural_query=natural_query,
        category=category,
        max_rows=max_rows
    )