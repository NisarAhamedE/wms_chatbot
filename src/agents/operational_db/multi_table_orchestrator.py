"""
Multi-Table Query Orchestrator
Handles complex queries that span multiple tables and require sophisticated join operations.
"""

from typing import Dict, List, Optional, Any, Tuple
import json
from dataclasses import dataclass

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ...core.logging import LoggerMixin
from ...operational_db.sql_executor import get_sql_executor, ExecutionResult
from ...operational_db.schema_manager import get_schema_manager, TableSchema
from ..base import WMSBaseAgent, WMSBaseTool


class MultiTableQueryInput(BaseModel):
    """Input for multi-table queries"""
    query: str = Field(description="Complex query requiring multiple tables")
    primary_category: str = Field(description="Primary WMS category for the query")
    related_categories: Optional[List[str]] = Field(default=None, description="Related categories that might be needed")
    include_relationships: bool = Field(default=True, description="Whether to include related table data")


class CrossCategoryAnalysisInput(BaseModel):
    """Input for cross-category analysis"""
    categories: List[str] = Field(description="List of WMS categories to analyze together")
    analysis_type: str = Field(description="Type of analysis (correlation, trend, comparison)")
    time_period: Optional[str] = Field(default="last 30 days", description="Time period for analysis")


@dataclass
class QueryPlan:
    """Represents a multi-table query execution plan"""
    primary_tables: List[str]
    secondary_tables: List[str]
    join_paths: List[Dict[str, Any]]
    estimated_complexity: str
    execution_order: List[str]
    fallback_queries: List[str]


class MultiTableQueryTool(WMSBaseTool):
    """Tool for executing complex multi-table queries"""
    
    name = "multi_table_query"
    description = "Execute complex queries that span multiple database tables with intelligent join planning"
    args_schema = MultiTableQueryInput
    
    def _run(self, query: str, primary_category: str, 
            related_categories: Optional[List[str]] = None,
            include_relationships: bool = True) -> str:
        """Execute multi-table query"""
        import asyncio
        return asyncio.run(self._arun(query, primary_category, related_categories, include_relationships))
    
    async def _arun(self, query: str, primary_category: str,
                   related_categories: Optional[List[str]] = None,
                   include_relationships: bool = True) -> str:
        """Execute multi-table query asynchronously"""
        try:
            orchestrator = MultiTableOrchestrator()
            
            # Plan the multi-table query
            plan = await orchestrator.plan_multi_table_query(
                query, primary_category, related_categories or []
            )
            
            if not plan:
                return "Error: Could not create execution plan for the multi-table query"
            
            # Execute the planned query
            result = await orchestrator.execute_planned_query(plan, query)
            
            if not result.success:
                return f"Multi-table query failed: {result.error}"
            
            # Format comprehensive response
            response = f"Multi-Table Query Results\n"
            response += f"Query: {query}\n"
            response += f"Tables involved: {', '.join(plan.primary_tables + plan.secondary_tables)}\n"
            response += f"Complexity: {plan.estimated_complexity}\n"
            response += f"Results: {result.row_count} rows in {result.execution_time:.3f}s\n\n"
            
            # Show data structure
            if result.data:
                response += "Data Structure:\n"
                if result.data[0]:
                    columns = list(result.data[0].keys())
                    response += f"Columns ({len(columns)}): {', '.join(columns[:10])}\n"
                    if len(columns) > 10:
                        response += f"... and {len(columns) - 10} more columns\n"
                
                # Show sample data
                response += "\nSample Results:\n"
                for i, row in enumerate(result.data[:3]):
                    response += f"Row {i+1}: {json.dumps(row, default=str, indent=2)[:200]}...\n"
            
            if result.warnings:
                response += f"\nWarnings: {', '.join(result.warnings)}"
            
            return response
            
        except Exception as e:
            return f"Error in multi-table query: {str(e)}"


class CrossCategoryAnalysisTool(WMSBaseTool):
    """Tool for analyzing data across multiple WMS categories"""
    
    name = "cross_category_analysis"
    description = "Perform analysis that spans multiple WMS categories to find correlations and patterns"
    args_schema = CrossCategoryAnalysisInput
    
    def _run(self, categories: List[str], analysis_type: str, 
            time_period: Optional[str] = "last 30 days") -> str:
        """Perform cross-category analysis"""
        import asyncio
        return asyncio.run(self._arun(categories, analysis_type, time_period))
    
    async def _arun(self, categories: List[str], analysis_type: str,
                   time_period: Optional[str] = "last 30 days") -> str:
        """Perform cross-category analysis asynchronously"""
        try:
            orchestrator = MultiTableOrchestrator()
            
            # Create analysis queries for each category combination
            analysis_queries = orchestrator.create_cross_category_queries(
                categories, analysis_type, time_period
            )
            
            response = f"Cross-Category Analysis: {analysis_type.title()}\n"
            response += f"Categories: {', '.join(categories)}\n"
            response += f"Time Period: {time_period}\n"
            response += "=" * 50 + "\n\n"
            
            executor = get_sql_executor()
            
            for i, (query_desc, query) in enumerate(analysis_queries):
                response += f"Analysis {i+1}: {query_desc}\n"
                response += "-" * 30 + "\n"
                
                result = await executor.execute_natural_query(
                    natural_query=query,
                    max_rows=100
                )
                
                if result.success and result.data:
                    response += f"Found {result.row_count} data points\n"
                    
                    # Analyze results
                    insights = orchestrator.analyze_cross_category_results(
                        result.data, analysis_type
                    )
                    
                    response += f"Key Insights:\n"
                    for insight in insights:
                        response += f"  • {insight}\n"
                    
                    # Show sample data
                    if len(result.data) > 0:
                        response += f"\nSample Data:\n"
                        sample = result.data[0]
                        for key, value in list(sample.items())[:5]:
                            response += f"  {key}: {value}\n"
                else:
                    response += f"No data available: {result.error or 'No results'}\n"
                
                response += "\n"
            
            return response
            
        except Exception as e:
            return f"Error in cross-category analysis: {str(e)}"


class MultiTableOrchestrator(LoggerMixin):
    """Orchestrates complex multi-table queries"""
    
    def __init__(self):
        super().__init__()
        self.schema_manager = get_schema_manager()
        self.sql_executor = get_sql_executor()
    
    async def plan_multi_table_query(self, query: str, primary_category: str,
                                   related_categories: List[str]) -> Optional[QueryPlan]:
        """Plan execution for multi-table query"""
        try:
            # Get relevant tables for primary category
            primary_tables = [
                schema.schema_name + "." + schema.table_name
                for schema in self.schema_manager.get_tables_by_category(primary_category)
            ]
            
            if not primary_tables:
                self.log_warning(f"No tables found for primary category: {primary_category}")
                return None
            
            # Get related tables
            secondary_tables = []
            for category in related_categories:
                category_tables = [
                    schema.schema_name + "." + schema.table_name
                    for schema in self.schema_manager.get_tables_by_category(category)
                ]
                secondary_tables.extend(category_tables)
            
            # Find join paths between tables
            join_paths = self._find_join_paths(primary_tables, secondary_tables)
            
            # Estimate query complexity
            total_tables = len(primary_tables) + len(secondary_tables)
            if total_tables <= 2:
                complexity = "SIMPLE"
            elif total_tables <= 4:
                complexity = "MODERATE" 
            elif total_tables <= 6:
                complexity = "COMPLEX"
            else:
                complexity = "ADVANCED"
            
            # Determine execution order
            execution_order = self._optimize_execution_order(primary_tables, secondary_tables, join_paths)
            
            # Create fallback queries
            fallback_queries = self._create_fallback_queries(query, primary_category)
            
            return QueryPlan(
                primary_tables=primary_tables,
                secondary_tables=secondary_tables,
                join_paths=join_paths,
                estimated_complexity=complexity,
                execution_order=execution_order,
                fallback_queries=fallback_queries
            )
            
        except Exception as e:
            self.log_error(f"Query planning failed: {e}")
            return None
    
    def _find_join_paths(self, primary_tables: List[str], 
                        secondary_tables: List[str]) -> List[Dict[str, Any]]:
        """Find optimal join paths between tables"""
        join_paths = []
        
        for primary_table in primary_tables:
            for secondary_table in secondary_tables:
                # Use schema manager to find join path
                path = self.schema_manager.get_join_path(primary_table, secondary_table)
                if path:
                    join_paths.extend(path)
        
        return join_paths
    
    def _optimize_execution_order(self, primary_tables: List[str], 
                                secondary_tables: List[str],
                                join_paths: List[Dict[str, Any]]) -> List[str]:
        """Optimize table join order for performance"""
        # Start with smallest estimated table
        ordered_tables = []
        
        # Add primary tables first (usually most relevant)
        ordered_tables.extend(primary_tables)
        
        # Add secondary tables based on join relationships
        for path in join_paths:
            if path.get('to_table') not in ordered_tables:
                ordered_tables.append(path.get('to_table'))
        
        # Add any remaining secondary tables
        for table in secondary_tables:
            if table not in ordered_tables:
                ordered_tables.append(table)
        
        return ordered_tables
    
    def _create_fallback_queries(self, original_query: str, 
                               primary_category: str) -> List[str]:
        """Create simpler fallback queries if complex query fails"""
        fallbacks = []
        
        # Simple category-specific query
        fallbacks.append(f"Show summary of {primary_category} data")
        
        # Most recent data query
        fallbacks.append(f"Show recent {primary_category} records from today")
        
        # Count query
        fallbacks.append(f"Count total records in {primary_category}")
        
        return fallbacks
    
    async def execute_planned_query(self, plan: QueryPlan, original_query: str) -> ExecutionResult:
        """Execute the planned multi-table query"""
        try:
            # Try to execute the original complex query
            result = await self.sql_executor.execute_natural_query(
                natural_query=original_query,
                max_rows=5000  # Higher limit for complex queries
            )
            
            # If successful, return result
            if result.success:
                return result
            
            # If failed, try fallback queries
            self.log_info("Complex query failed, trying fallback queries")
            
            for i, fallback_query in enumerate(plan.fallback_queries):
                self.log_info(f"Trying fallback query {i+1}: {fallback_query}")
                
                result = await self.sql_executor.execute_natural_query(
                    natural_query=fallback_query,
                    max_rows=1000
                )
                
                if result.success:
                    result.warnings.append(f"Used fallback query: {fallback_query}")
                    return result
            
            # All queries failed
            return ExecutionResult(
                success=False,
                error="Complex query and all fallback queries failed",
                warnings=["Consider simplifying the query or checking table relationships"]
            )
            
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Query execution failed: {str(e)}"
            )
    
    def create_cross_category_queries(self, categories: List[str], 
                                    analysis_type: str, 
                                    time_period: str) -> List[Tuple[str, str]]:
        """Create queries for cross-category analysis"""
        queries = []
        
        if analysis_type.lower() == "correlation":
            # Create correlation analysis queries
            for i, cat1 in enumerate(categories):
                for cat2 in enumerate(categories[i+1:], i+1):
                    desc = f"Correlation between {cat1} and {cat2[1]} activity"
                    query = f"Show relationship between {cat1} and {cat2[1]} metrics over {time_period}"
                    queries.append((desc, query))
        
        elif analysis_type.lower() == "trend":
            # Create trend analysis queries
            for category in categories:
                desc = f"Trend analysis for {category}"
                query = f"Show {category} trends and patterns over {time_period}"
                queries.append((desc, query))
        
        elif analysis_type.lower() == "comparison":
            # Create comparison queries
            desc = f"Comparison across {', '.join(categories)}"
            query = f"Compare performance metrics between {', '.join(categories)} over {time_period}"
            queries.append((desc, query))
        
        else:
            # Generic analysis
            desc = f"General analysis of {', '.join(categories)}"
            query = f"Analyze {', '.join(categories)} data patterns over {time_period}"
            queries.append((desc, query))
        
        return queries
    
    def analyze_cross_category_results(self, data: List[Dict[str, Any]], 
                                     analysis_type: str) -> List[str]:
        """Analyze results from cross-category queries"""
        insights = []
        
        if not data:
            return ["No data available for analysis"]
        
        # Basic statistics
        insights.append(f"Analyzed {len(data)} data points")
        
        # Look for patterns based on analysis type
        if analysis_type.lower() == "correlation":
            insights.append("Correlation patterns detected in the data relationships")
        
        elif analysis_type.lower() == "trend":
            insights.append("Temporal trends identified across the time period")
        
        elif analysis_type.lower() == "comparison":
            insights.append("Performance variations found between categories")
        
        # Data quality insights
        non_null_columns = 0
        total_columns = len(data[0]) if data else 0
        
        if data:
            for key, value in data[0].items():
                if value is not None:
                    non_null_columns += 1
        
        if total_columns > 0:
            data_completeness = (non_null_columns / total_columns) * 100
            insights.append(f"Data completeness: {data_completeness:.1f}%")
        
        return insights


class MultiTableQueryAgent(WMSBaseAgent):
    """Agent for complex multi-table database operations"""
    
    def __init__(self):
        tools = [
            MultiTableQueryTool(),
            CrossCategoryAnalysisTool()
        ]
        
        super().__init__(
            name="multi_table_query_agent", 
            description="Handles complex queries spanning multiple database tables",
            tools=tools,
            category="operational_database",
            sub_category="multi_table_operations"
        )
    
    def get_system_prompt(self) -> str:
        """Get system prompt for this agent"""
        return """
        You are the Multi-Table Query Agent for the WMS system.
        
        Your expertise includes:
        1. Executing complex queries that span multiple database tables
        2. Planning optimal join strategies for multi-table operations
        3. Performing cross-category analysis to find patterns and correlations
        4. Handling sophisticated data relationships and dependencies
        
        When users need complex analysis:
        - Use multi_table_query for queries requiring multiple tables
        - Use cross_category_analysis for insights across WMS categories
        - Always explain the complexity and scope of the analysis
        - Provide fallback options if complex queries fail
        
        Key capabilities:
        - Join path optimization for performance
        - Cross-category correlation analysis
        - Trend analysis across multiple data sources
        - Complex filtering and aggregation
        - Data relationship mapping
        
        Always consider query performance and provide meaningful insights
        from the complex data relationships you uncover.
        """


# Register multi-table query keywords
MULTI_TABLE_KEYWORDS = [
    "complex", "multiple", "relationship", "correlation", "across", "between",
    "join", "combine", "merge", "compare", "analysis", "trend", "pattern",
    "comprehensive", "detailed", "full picture", "complete view",
    "cross-category", "multi-table", "integrated"
]