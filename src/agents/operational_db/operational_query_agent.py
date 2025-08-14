"""
Operational Database Query Agent
Specialized agent for executing queries against the operational WMS database.
"""

from typing import Dict, List, Optional, Any
import json

from langchain.agents import AgentExecutor
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ...core.logging import LoggerMixin
from ...operational_db.sql_executor import get_sql_executor, ConnectionInfo, ExecutionResult
from ..base import WMSBaseAgent, WMSBaseTool


class OperationalQueryInput(BaseModel):
    """Input for operational database queries"""
    query: str = Field(description="Natural language query to execute against operational database")
    category: Optional[str] = Field(default=None, description="WMS category to focus the query on")
    max_rows: Optional[int] = Field(default=1000, description="Maximum number of rows to return")


class DataSummaryInput(BaseModel):
    """Input for data summary queries"""
    table_category: str = Field(description="WMS category/table type to summarize")
    time_period: Optional[str] = Field(default="today", description="Time period for summary (today, this week, this month)")


class ReportingInput(BaseModel):
    """Input for reporting queries"""
    report_type: str = Field(description="Type of report (inventory, performance, operational)")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Additional filters for the report")


class OperationalQueryTool(WMSBaseTool):
    """Tool for executing natural language queries against operational database"""
    
    name = "operational_query"
    description = "Execute natural language queries against the operational WMS database to retrieve real-time data"
    args_schema = OperationalQueryInput
    
    def _run(self, query: str, category: Optional[str] = None, 
            max_rows: Optional[int] = 1000) -> str:
        """Execute operational database query"""
        import asyncio
        return asyncio.run(self._arun(query, category, max_rows))
    
    async def _arun(self, query: str, category: Optional[str] = None, 
                   max_rows: Optional[int] = 1000) -> str:
        """Execute operational database query asynchronously"""
        try:
            executor = get_sql_executor()
            
            if not executor.engine:
                return "Error: Operational database connection not established. Please configure database connection first."
            
            # Execute the query
            result = await executor.execute_natural_query(
                natural_query=query,
                category=category,
                max_rows=max_rows
            )
            
            if not result.success:
                return f"Query failed: {result.error}\nSuggestions: {', '.join(result.warnings)}"
            
            # Format result for agent consumption
            formatted_result = executor.format_result_for_display(result)
            
            summary = formatted_result['summary']
            response = f"Query executed successfully!\n\n"
            response += f"Results: {summary['showing']} of {summary['total']} rows ({summary['execution_time']})\n\n"
            
            # Add sample of data if available
            if result.data and len(result.data) > 0:
                response += "Sample data:\n"
                sample_size = min(3, len(result.data))
                for i, row in enumerate(result.data[:sample_size]):
                    response += f"Row {i+1}: {json.dumps(row, default=str, indent=2)}\n"
                
                if len(result.data) > sample_size:
                    response += f"... and {len(result.data) - sample_size} more rows\n"
            
            # Add warnings if any
            if result.warnings:
                response += f"\nWarnings: {', '.join(result.warnings)}"
            
            return response
            
        except Exception as e:
            return f"Error executing query: {str(e)}"


class DataSummaryTool(WMSBaseTool):
    """Tool for generating data summaries from operational database"""
    
    name = "data_summary"
    description = "Generate summary reports from operational database for specific WMS categories"
    args_schema = DataSummaryInput
    
    def _run(self, table_category: str, time_period: Optional[str] = "today") -> str:
        """Generate data summary"""
        import asyncio
        return asyncio.run(self._arun(table_category, time_period))
    
    async def _arun(self, table_category: str, time_period: Optional[str] = "today") -> str:
        """Generate data summary asynchronously"""
        try:
            executor = get_sql_executor()
            
            if not executor.engine:
                return "Error: Operational database connection not established."
            
            # Create summary query based on category and time period
            summary_queries = {
                'inventory': f"Show inventory summary for {time_period} including total items, quantities, and value",
                'orders': f"Show order summary for {time_period} including order count, status distribution, and volume",
                'receipts': f"Show receiving summary for {time_period} including receipt count and quantities received",
                'shipments': f"Show shipping summary for {time_period} including shipment count and quantities shipped",
                'work': f"Show work task summary for {time_period} including task count by status and completion rate",
                'locations': f"Show location utilization summary including occupancy and capacity",
                'items': f"Show item activity summary for {time_period} including movement frequency and categories"
            }
            
            # Map common category names
            category_map = {
                'inventory_management': 'inventory',
                'picking': 'orders',
                'receiving': 'receipts',
                'shipping': 'shipments',
                'locations': 'locations',
                'items': 'items',
                'work': 'work'
            }
            
            mapped_category = category_map.get(table_category.lower(), table_category.lower())
            query = summary_queries.get(mapped_category, 
                f"Show summary statistics for {table_category} data from {time_period}")
            
            # Execute summary query
            result = await executor.execute_natural_query(
                natural_query=query,
                category=table_category,
                max_rows=100  # Summaries typically don't need many rows
            )
            
            if not result.success:
                return f"Summary generation failed: {result.error}"
            
            # Format summary response
            response = f"Data Summary - {table_category.title()} ({time_period})\n"
            response += "=" * 50 + "\n\n"
            
            if result.data:
                if len(result.data) == 1:
                    # Single row summary (aggregated data)
                    summary_row = result.data[0]
                    for key, value in summary_row.items():
                        response += f"{key}: {value}\n"
                else:
                    # Multiple rows - show key metrics
                    response += f"Total records: {result.row_count}\n"
                    response += f"Sample breakdown:\n"
                    for i, row in enumerate(result.data[:5]):
                        response += f"  {i+1}. {json.dumps(row, default=str, indent=4)}\n"
            
            response += f"\nExecution time: {result.execution_time:.3f} seconds"
            
            return response
            
        except Exception as e:
            return f"Error generating summary: {str(e)}"


class OperationalReportingTool(WMSBaseTool):
    """Tool for generating operational reports"""
    
    name = "operational_reporting"
    description = "Generate detailed operational reports with analytics and insights"
    args_schema = ReportingInput
    
    def _run(self, report_type: str, filters: Optional[Dict[str, Any]] = None) -> str:
        """Generate operational report"""
        import asyncio
        return asyncio.run(self._arun(report_type, filters))
    
    async def _arun(self, report_type: str, filters: Optional[Dict[str, Any]] = None) -> str:
        """Generate operational report asynchronously"""
        try:
            executor = get_sql_executor()
            
            if not executor.engine:
                return "Error: Operational database connection not established."
            
            # Define report templates
            report_templates = {
                'inventory': [
                    "Show current inventory levels by location and item",
                    "Show inventory accuracy by zone",
                    "Show slow-moving and fast-moving items",
                    "Show items below minimum stock levels"
                ],
                'performance': [
                    "Show picking productivity by user and time period",
                    "Show receiving performance metrics",
                    "Show order fulfillment rates",
                    "Show location utilization efficiency"
                ],
                'operational': [
                    "Show daily operational summary with key metrics",
                    "Show work task completion rates by category",
                    "Show system performance indicators",
                    "Show exception and error analysis"
                ]
            }
            
            queries = report_templates.get(report_type.lower(), [
                f"Show comprehensive {report_type} report with key metrics and trends"
            ])
            
            response = f"Operational Report - {report_type.title()}\n"
            response += "=" * 50 + "\n\n"
            
            # Execute each query in the report
            for i, query in enumerate(queries[:3]):  # Limit to 3 sections to avoid long reports
                section_response = f"Section {i+1}: {query}\n"
                section_response += "-" * 30 + "\n"
                
                # Apply filters if provided
                if filters:
                    filter_conditions = []
                    for key, value in filters.items():
                        filter_conditions.append(f"{key} = '{value}'")
                    if filter_conditions:
                        query += f" WHERE {' AND '.join(filter_conditions)}"
                
                result = await executor.execute_natural_query(
                    natural_query=query,
                    max_rows=50  # Reasonable limit for reports
                )
                
                if result.success and result.data:
                    section_response += f"Found {result.row_count} records\n"
                    
                    # Show summary statistics
                    if len(result.data) > 0:
                        sample_data = result.data[:3]
                        for j, row in enumerate(sample_data):
                            section_response += f"  Record {j+1}: {json.dumps(row, default=str)}\n"
                        
                        if len(result.data) > 3:
                            section_response += f"  ... and {len(result.data) - 3} more records\n"
                    
                else:
                    section_response += f"No data found: {result.error or 'Query returned no results'}\n"
                
                section_response += "\n"
                response += section_response
            
            response += f"Report generated at: {result.metadata.get('last_query_time', 'unknown')}\n"
            
            return response
            
        except Exception as e:
            return f"Error generating report: {str(e)}"


class OperationalDatabaseQueryAgent(WMSBaseAgent):
    """Agent specialized in querying operational database"""
    
    def __init__(self):
        tools = [
            OperationalQueryTool(),
            DataSummaryTool(),
            OperationalReportingTool()
        ]
        
        super().__init__(
            name="operational_database_query_agent",
            description="Executes queries against operational WMS database for real-time data access",
            tools=tools,
            category="operational_database",
            sub_category="query_execution"
        )
    
    def get_system_prompt(self) -> str:
        """Get system prompt for this agent"""
        return """
        You are the Operational Database Query Agent for the WMS system.
        
        Your primary responsibilities:
        1. Execute natural language queries against the operational WMS database
        2. Generate data summaries and reports from real-time operational data
        3. Provide insights and analytics based on current system state
        4. Ensure query safety and performance
        
        When users ask for data from the operational system:
        - Use the operational_query tool for specific data requests
        - Use data_summary tool for aggregated insights
        - Use operational_reporting tool for comprehensive reports
        
        Always explain what data you're retrieving and provide context for the results.
        If queries fail, suggest alternative approaches or help refine the request.
        
        Key WMS categories you work with:
        - Inventory Management: Stock levels, movements, accuracy
        - Locations: Bins, zones, capacity utilization  
        - Orders/Picking: Order status, picking tasks, productivity
        - Receiving: Receipts, ASNs, inbound performance
        - Shipping: Outbound orders, carrier performance
        - Work Management: Task assignments, labor productivity
        - Item Master: Product data, specifications
        
        Always prioritize data accuracy and query performance.
        """


# Register agent category keywords for routing
OPERATIONAL_DB_KEYWORDS = [
    "operational", "database", "query", "data", "real-time", "current",
    "show me", "display", "list", "find", "search", "report", "summary",
    "how many", "what are", "which", "analytics", "metrics", "performance",
    "today", "yesterday", "this week", "this month", "recent", "latest"
]