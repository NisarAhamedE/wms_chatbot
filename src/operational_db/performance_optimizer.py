"""
Performance Optimizer for Operational Database Queries
Provides intelligent index recommendations and query optimization suggestions.
"""

from typing import Dict, List, Optional, Any, Tuple
import re
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ..core.logging import LoggerMixin


class IndexType(Enum):
    """Types of database indexes"""
    CLUSTERED = "CLUSTERED"
    NONCLUSTERED = "NONCLUSTERED"
    UNIQUE = "UNIQUE"
    COVERING = "COVERING"
    FILTERED = "FILTERED"
    COLUMNSTORE = "COLUMNSTORE"


@dataclass
class IndexRecommendation:
    """Represents an index recommendation"""
    table_name: str
    columns: List[str]
    index_type: IndexType
    priority: str  # HIGH, MEDIUM, LOW
    reason: str
    estimated_benefit: str
    sql_create_statement: str
    covering_columns: List[str] = None
    filter_condition: str = None
    
    def __post_init__(self):
        if self.covering_columns is None:
            self.covering_columns = []


class WMSPerformanceOptimizer(LoggerMixin):
    """Optimizes query performance for WMS operational database"""
    
    def __init__(self, engine: Engine = None):
        super().__init__()
        self.engine = engine
        
        # WMS-specific optimization patterns
        self.wms_query_patterns = {
            'inventory_lookup': {
                'tables': ['inventory', 'item', 'location'],
                'common_filters': ['item_id', 'location_id', 'status', 'date_created'],
                'recommended_indexes': [
                    ('inventory', ['item_id', 'location_id'], 'Inventory lookups by item and location'),
                    ('inventory', ['status', 'date_created'], 'Active inventory queries'),
                    ('item', ['sku', 'item_type'], 'Item searches by SKU and type')
                ]
            },
            'order_processing': {
                'tables': ['orders', 'order_lines', 'picking_tasks'],
                'common_filters': ['order_id', 'status', 'priority', 'created_date'],
                'recommended_indexes': [
                    ('orders', ['status', 'priority', 'created_date'], 'Order queue processing'),
                    ('order_lines', ['order_id', 'item_id'], 'Order line lookups'),
                    ('picking_tasks', ['order_id', 'status', 'assigned_user'], 'Pick task management')
                ]
            },
            'location_management': {
                'tables': ['locations', 'location_types', 'zones'],
                'common_filters': ['location_id', 'zone_id', 'status', 'capacity'],
                'recommended_indexes': [
                    ('locations', ['zone_id', 'status'], 'Available location searches'),
                    ('locations', ['location_type', 'capacity'], 'Capacity-based location queries')
                ]
            },
            'work_management': {
                'tables': ['work_assignments', 'tasks', 'users'],
                'common_filters': ['user_id', 'status', 'priority', 'assigned_date'],
                'recommended_indexes': [
                    ('work_assignments', ['user_id', 'status'], 'User work queue queries'),
                    ('tasks', ['status', 'priority', 'created_date'], 'Task prioritization')
                ]
            }
        }
    
    def set_engine(self, engine: Engine):
        """Set database engine for analysis"""
        self.engine = engine
    
    async def analyze_query_performance(self, sql: str, 
                                      execution_stats: Dict[str, Any] = None) -> Dict[str, Any]:
        """Comprehensive query performance analysis"""
        analysis = {
            'query_classification': self._classify_wms_query(sql),
            'performance_issues': await self._identify_performance_issues(sql),
            'index_recommendations': await self._generate_index_recommendations(sql),
            'optimization_suggestions': self._get_optimization_suggestions(sql),
            'estimated_improvement': self._estimate_performance_improvement(sql),
            'monitoring_recommendations': self._get_monitoring_recommendations(sql)
        }
        
        # Add execution stats analysis if available
        if execution_stats:
            analysis['execution_analysis'] = self._analyze_execution_stats(execution_stats)
        
        return analysis
    
    def _classify_wms_query(self, sql: str) -> Dict[str, Any]:
        """Classify query based on WMS operations"""
        sql_upper = sql.upper()
        classification = {
            'category': 'unknown',
            'operation_type': 'read',
            'complexity': 'simple',
            'wms_function': 'general'
        }
        
        # Identify WMS functional area
        for function, pattern in self.wms_query_patterns.items():
            if any(table.upper() in sql_upper for table in pattern['tables']):
                classification['wms_function'] = function
                break
        
        # Determine operation type
        if any(keyword in sql_upper for keyword in ['INSERT', 'UPDATE', 'DELETE']):
            classification['operation_type'] = 'write'
        elif any(keyword in sql_upper for keyword in ['COUNT', 'SUM', 'AVG', 'GROUP BY']):
            classification['operation_type'] = 'aggregate'
        
        # Assess complexity
        join_count = sql_upper.count('JOIN')
        subquery_count = sql_upper.count('SELECT') - 1
        
        if join_count > 3 or subquery_count > 2:
            classification['complexity'] = 'complex'
        elif join_count > 1 or subquery_count > 0:
            classification['complexity'] = 'moderate'
        
        return classification
    
    async def _identify_performance_issues(self, sql: str) -> List[Dict[str, Any]]:
        """Identify potential performance issues"""
        issues = []
        sql_upper = sql.upper()
        
        # Check for common anti-patterns
        performance_checks = [
            {
                'check': 'SELECT *' in sql_upper,
                'issue': 'SELECT_STAR',
                'severity': 'MEDIUM',
                'description': 'SELECT * can impact performance and network traffic',
                'solution': 'Specify only needed columns'
            },
            {
                'check': any(pattern in sql_upper for pattern in ["LIKE '%", "LIKE N'%"]),
                'issue': 'LEADING_WILDCARD',
                'severity': 'HIGH',
                'description': 'Leading wildcards prevent index usage',
                'solution': 'Use full-text search or restructure query'
            },
            {
                'check': 'ORDER BY' in sql_upper and 'WHERE' not in sql_upper,
                'issue': 'UNFILTERED_SORT',
                'severity': 'HIGH',
                'description': 'Sorting entire table without filtering',
                'solution': 'Add WHERE clause to filter before sorting'
            },
            {
                'check': ' OR ' in sql_upper and 'WHERE' in sql_upper,
                'issue': 'OR_CONDITIONS',
                'severity': 'MEDIUM', 
                'description': 'OR conditions can prevent index usage',
                'solution': 'Consider UNION or separate queries'
            },
            {
                'check': any(func in sql_upper for func in ['UPPER(', 'LOWER(', 'SUBSTRING(']),
                'issue': 'FUNCTIONS_IN_WHERE',
                'severity': 'MEDIUM',
                'description': 'Functions in WHERE clause prevent index usage',
                'solution': 'Use computed columns or function-based indexes'
            }
        ]
        
        for check in performance_checks:
            if check['check']:
                issues.append({
                    'issue_type': check['issue'],
                    'severity': check['severity'],
                    'description': check['description'],
                    'recommended_solution': check['solution']
                })
        
        # WMS-specific performance checks
        wms_issues = await self._check_wms_specific_issues(sql)
        issues.extend(wms_issues)
        
        return issues
    
    async def _check_wms_specific_issues(self, sql: str) -> List[Dict[str, Any]]:
        """Check for WMS-specific performance issues"""
        issues = []
        sql_upper = sql.upper()
        
        # Check for common WMS anti-patterns
        if 'INVENTORY' in sql_upper and 'DATE' not in sql_upper:
            issues.append({
                'issue_type': 'INVENTORY_WITHOUT_DATE',
                'severity': 'MEDIUM',
                'description': 'Inventory queries without date filtering can be slow',
                'recommended_solution': 'Add date range filters for current operational data'
            })
        
        if 'ORDERS' in sql_upper and 'STATUS' not in sql_upper:
            issues.append({
                'issue_type': 'ORDERS_WITHOUT_STATUS',
                'severity': 'LOW',
                'description': 'Order queries often benefit from status filtering',
                'recommended_solution': 'Consider filtering by order status'
            })
        
        if any(table in sql_upper for table in ['WORK_ASSIGNMENTS', 'TASKS']) and 'USER' not in sql_upper:
            issues.append({
                'issue_type': 'WORK_WITHOUT_USER',
                'severity': 'LOW',
                'description': 'Work queries are often user-specific',
                'recommended_solution': 'Consider user-based filtering for better performance'
            })
        
        return issues
    
    async def _generate_index_recommendations(self, sql: str) -> List[IndexRecommendation]:
        """Generate intelligent index recommendations"""
        recommendations = []
        sql_upper = sql.upper()
        
        # Extract table and column information
        tables = self._extract_tables_from_query(sql)
        where_columns = self._extract_where_columns(sql)
        join_columns = self._extract_join_columns(sql)
        order_columns = self._extract_order_columns(sql)
        
        for table in tables:
            # Recommend indexes for WHERE clause columns
            table_where_cols = [col for col in where_columns if col['table'] == table]
            if table_where_cols:
                columns = [col['column'] for col in table_where_cols]
                recommendations.append(IndexRecommendation(
                    table_name=table,
                    columns=columns,
                    index_type=IndexType.NONCLUSTERED,
                    priority='HIGH',
                    reason='Columns used in WHERE clause',
                    estimated_benefit='Significant improvement in query filtering',
                    sql_create_statement=self._generate_create_index_sql(table, columns, IndexType.NONCLUSTERED)
                ))
            
            # Recommend indexes for JOIN columns
            table_join_cols = [col for col in join_columns if col['table'] == table]
            if table_join_cols:
                columns = [col['column'] for col in table_join_cols]
                recommendations.append(IndexRecommendation(
                    table_name=table,
                    columns=columns,
                    index_type=IndexType.NONCLUSTERED,
                    priority='HIGH',
                    reason='Columns used in JOIN operations',
                    estimated_benefit='Faster join processing',
                    sql_create_statement=self._generate_create_index_sql(table, columns, IndexType.NONCLUSTERED)
                ))
        
        # Add WMS-specific recommendations
        wms_recommendations = self._get_wms_specific_recommendations(sql)
        recommendations.extend(wms_recommendations)
        
        # Remove duplicates and prioritize
        recommendations = self._deduplicate_recommendations(recommendations)
        
        return recommendations[:10]  # Limit to top 10 recommendations
    
    def _extract_tables_from_query(self, sql: str) -> List[str]:
        """Extract table names from SQL query"""
        tables = []
        sql_upper = sql.upper()
        
        # Simple pattern matching for table extraction
        from_match = re.search(r'FROM\s+(\w+)', sql_upper)
        if from_match:
            tables.append(from_match.group(1))
        
        # Extract tables from JOINs
        join_matches = re.findall(r'JOIN\s+(\w+)', sql_upper)
        tables.extend(join_matches)
        
        return list(set(tables))
    
    def _extract_where_columns(self, sql: str) -> List[Dict[str, str]]:
        """Extract columns used in WHERE clause"""
        columns = []
        sql_upper = sql.upper()
        
        # Find WHERE clause
        where_pos = sql_upper.find('WHERE')
        if where_pos == -1:
            return columns
        
        where_clause = sql_upper[where_pos:]
        
        # Simple pattern matching for column extraction
        column_patterns = [
            r'(\w+)\.(\w+)\s*[=<>!]',  # table.column comparisons
            r'(\w+)\s*[=<>!]',         # column comparisons
        ]
        
        for pattern in column_patterns:
            matches = re.findall(pattern, where_clause)
            for match in matches:
                if isinstance(match, tuple) and len(match) == 2:
                    columns.append({'table': match[0], 'column': match[1]})
                elif isinstance(match, str):
                    columns.append({'table': 'unknown', 'column': match})
        
        return columns
    
    def _extract_join_columns(self, sql: str) -> List[Dict[str, str]]:
        """Extract columns used in JOIN conditions"""
        columns = []
        sql_upper = sql.upper()
        
        # Find JOIN conditions
        join_pattern = r'JOIN\s+(\w+)\s+.*?ON\s+(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)'
        matches = re.findall(join_pattern, sql_upper)
        
        for match in matches:
            columns.extend([
                {'table': match[1], 'column': match[2]},
                {'table': match[3], 'column': match[4]}
            ])
        
        return columns
    
    def _extract_order_columns(self, sql: str) -> List[Dict[str, str]]:
        """Extract columns used in ORDER BY clause"""
        columns = []
        sql_upper = sql.upper()
        
        order_pos = sql_upper.find('ORDER BY')
        if order_pos == -1:
            return columns
        
        order_clause = sql_upper[order_pos:]
        
        # Extract column references
        column_pattern = r'(\w+)\.(\w+)|(\w+)'
        matches = re.findall(column_pattern, order_clause)
        
        for match in matches:
            if match[0] and match[1]:
                columns.append({'table': match[0], 'column': match[1]})
            elif match[2]:
                columns.append({'table': 'unknown', 'column': match[2]})
        
        return columns
    
    def _get_wms_specific_recommendations(self, sql: str) -> List[IndexRecommendation]:
        """Get WMS-specific index recommendations"""
        recommendations = []
        sql_upper = sql.upper()
        
        # Inventory management indexes
        if any(table in sql_upper for table in ['INVENTORY', 'STOCK']):
            recommendations.extend([
                IndexRecommendation(
                    table_name='inventory',
                    columns=['item_id', 'location_id', 'status'],
                    index_type=IndexType.NONCLUSTERED,
                    priority='HIGH',
                    reason='Core inventory lookup pattern',
                    estimated_benefit='Faster inventory queries',
                    sql_create_statement="CREATE NONCLUSTERED INDEX IX_Inventory_ItemLocationStatus ON inventory (item_id, location_id, status)"
                ),
                IndexRecommendation(
                    table_name='inventory',
                    columns=['date_created'],
                    index_type=IndexType.NONCLUSTERED,
                    priority='MEDIUM',
                    reason='Date-based inventory filtering',
                    estimated_benefit='Improved temporal queries',
                    sql_create_statement="CREATE NONCLUSTERED INDEX IX_Inventory_DateCreated ON inventory (date_created)"
                )
            ])
        
        # Order processing indexes
        if any(table in sql_upper for table in ['ORDERS', 'ORDER_LINES']):
            recommendations.extend([
                IndexRecommendation(
                    table_name='orders',
                    columns=['status', 'priority', 'created_date'],
                    index_type=IndexType.NONCLUSTERED,
                    priority='HIGH',
                    reason='Order queue processing pattern',
                    estimated_benefit='Faster order queue queries',
                    sql_create_statement="CREATE NONCLUSTERED INDEX IX_Orders_StatusPriorityDate ON orders (status, priority, created_date)"
                )
            ])
        
        return recommendations
    
    def _generate_create_index_sql(self, table: str, columns: List[str], 
                                 index_type: IndexType) -> str:
        """Generate CREATE INDEX SQL statement"""
        index_name = f"IX_{table}_{''.join(col.title() for col in columns)}"
        columns_str = ', '.join(columns)
        
        if index_type == IndexType.CLUSTERED:
            return f"CREATE CLUSTERED INDEX {index_name} ON {table} ({columns_str})"
        else:
            return f"CREATE NONCLUSTERED INDEX {index_name} ON {table} ({columns_str})"
    
    def _deduplicate_recommendations(self, recommendations: List[IndexRecommendation]) -> List[IndexRecommendation]:
        """Remove duplicate index recommendations"""
        seen = set()
        deduped = []
        
        for rec in recommendations:
            key = (rec.table_name, tuple(sorted(rec.columns)))
            if key not in seen:
                seen.add(key)
                deduped.append(rec)
        
        # Sort by priority
        priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
        deduped.sort(key=lambda x: priority_order.get(x.priority, 3))
        
        return deduped
    
    def _get_optimization_suggestions(self, sql: str) -> List[str]:
        """Get general optimization suggestions"""
        suggestions = []
        sql_upper = sql.upper()
        
        # Query rewriting suggestions
        if 'SELECT *' in sql_upper:
            suggestions.append("Replace SELECT * with specific column names")
        
        if ' OR ' in sql_upper:
            suggestions.append("Consider rewriting OR conditions as UNION for better performance")
        
        if 'ORDER BY' in sql_upper and 'LIMIT' not in sql_upper and 'TOP' not in sql_upper:
            suggestions.append("Consider adding TOP/LIMIT clause to reduce sorting overhead")
        
        # WMS-specific suggestions
        if 'INVENTORY' in sql_upper and 'DATE' not in sql_upper:
            suggestions.append("Add date range filters for current operational data")
        
        if any(table in sql_upper for table in ['ORDERS', 'TASKS']) and 'STATUS' not in sql_upper:
            suggestions.append("Consider status-based filtering for active records")
        
        return suggestions
    
    def _estimate_performance_improvement(self, sql: str) -> Dict[str, Any]:
        """Estimate potential performance improvement"""
        sql_upper = sql.upper()
        improvement = {
            'estimated_speedup': '1x',
            'confidence': 'low',
            'factors': []
        }
        
        # Estimate based on common patterns
        if 'WHERE' not in sql_upper:
            improvement.update({
                'estimated_speedup': '10-100x',
                'confidence': 'high',
                'factors': ['Adding WHERE clause filtering']
            })
        
        if any(pattern in sql_upper for pattern in ["LIKE '%", 'SELECT *']):
            improvement.update({
                'estimated_speedup': '5-50x',
                'confidence': 'medium',
                'factors': improvement['factors'] + ['Removing performance anti-patterns']
            })
        
        return improvement
    
    def _get_monitoring_recommendations(self, sql: str) -> List[str]:
        """Get monitoring recommendations for the query"""
        recommendations = [
            "Monitor query execution time and plan changes",
            "Set up alerts for queries exceeding 30 seconds",
            "Track index usage statistics",
            "Monitor for table scans in execution plans"
        ]
        
        sql_upper = sql.upper()
        
        # Query-specific monitoring
        if any(table in sql_upper for table in ['INVENTORY', 'ORDERS']):
            recommendations.append("Monitor for blocking on high-transaction tables")
        
        if 'JOIN' in sql_upper:
            recommendations.append("Watch for join performance degradation")
        
        return recommendations
    
    def _analyze_execution_stats(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze actual execution statistics"""
        analysis = {
            'performance_rating': 'unknown',
            'bottlenecks': [],
            'recommendations': []
        }
        
        execution_time = stats.get('execution_time', 0)
        row_count = stats.get('row_count', 0)
        
        # Performance rating based on execution time
        if execution_time < 1.0:
            analysis['performance_rating'] = 'excellent'
        elif execution_time < 5.0:
            analysis['performance_rating'] = 'good'
        elif execution_time < 30.0:
            analysis['performance_rating'] = 'acceptable'
        else:
            analysis['performance_rating'] = 'poor'
            analysis['recommendations'].append('Query optimization needed')
        
        # Analyze rows per second
        if execution_time > 0:
            rows_per_second = row_count / execution_time
            if rows_per_second < 100:
                analysis['bottlenecks'].append('Low throughput - possible I/O bottleneck')
        
        return analysis


# Global instance
_performance_optimizer: Optional[WMSPerformanceOptimizer] = None


def get_performance_optimizer(engine: Engine = None) -> WMSPerformanceOptimizer:
    """Get or create global performance optimizer instance"""
    global _performance_optimizer
    
    if _performance_optimizer is None:
        _performance_optimizer = WMSPerformanceOptimizer(engine)
    elif engine and _performance_optimizer.engine != engine:
        _performance_optimizer.set_engine(engine)
    
    return _performance_optimizer