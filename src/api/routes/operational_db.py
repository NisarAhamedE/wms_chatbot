"""
Operational Database API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime

from ...operational_db.sql_executor import get_sql_executor, ConnectionInfo
from ...operational_db.schema_manager import get_schema_manager, initialize_operational_schema
from ...operational_db.performance_optimizer import get_performance_optimizer
from ..models import (
    DatabaseConnectionRequest, OperationalQueryRequest, QueryExecutionResult,
    SchemaExtractionRequest, IndexRecommendation, APIResponse
)
from ..auth import get_current_user, UserContext, require_role


router = APIRouter()


@router.post("/connect")
async def connect_to_database(
    request: DatabaseConnectionRequest,
    user_context: UserContext = Depends(require_role(['admin_user', 'management_user']))
):
    """Connect to operational database"""
    try:
        connection_info = ConnectionInfo(
            server=request.server,
            database=request.database,
            username=request.username,
            password=request.password,
            port=request.port
        )
        
        executor = get_sql_executor()
        success = executor.set_connection(connection_info)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to connect to database")
        
        return APIResponse(
            success=True,
            message="Successfully connected to operational database",
            data={
                'server': request.server,
                'database': request.database,
                'connected_at': datetime.utcnow().isoformat()
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryExecutionResult)
async def execute_query(
    request: OperationalQueryRequest,
    user_context: UserContext = Depends(get_current_user)
):
    """Execute natural language query against operational database"""
    try:
        executor = get_sql_executor()
        
        if not executor.engine:
            raise HTTPException(status_code=400, detail="Database not connected")
        
        result = await executor.execute_natural_query(
            natural_query=request.query,
            category=request.category,
            max_rows=request.max_rows
        )
        
        # Format response
        formatted_result = executor.format_result_for_display(result)
        
        return QueryExecutionResult(
            success=result.success,
            data=result.data,
            row_count=result.row_count,
            execution_time=result.execution_time,
            query_used=result.query_used,
            data_quality=formatted_result.get('data_quality'),
            performance=formatted_result.get('performance'),
            warnings=result.warnings
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schema/extract")
async def extract_database_schema(
    request: SchemaExtractionRequest,
    background_tasks: BackgroundTasks,
    user_context: UserContext = Depends(require_role(['admin_user', 'management_user']))
):
    """Extract and vectorize database schema"""
    try:
        executor = get_sql_executor()
        
        if not executor.engine:
            raise HTTPException(status_code=400, detail="Database not connected")
        
        # Run schema extraction in background
        background_tasks.add_task(
            _extract_schema_background,
            executor.connection_info.get_connection_string(),
            request.include_sample_data,
            request.sample_size
        )
        
        return APIResponse(
            success=True,
            message="Schema extraction started in background",
            data={
                'include_sample_data': request.include_sample_data,
                'sample_size': request.sample_size,
                'started_at': datetime.utcnow().isoformat()
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _extract_schema_background(connection_string: str, include_sample_data: bool, sample_size: int):
    """Background task for schema extraction"""
    try:
        await initialize_operational_schema(
            connection_string=connection_string,
            include_sample_data=include_sample_data
        )
    except Exception as e:
        # Log error but don't raise (background task)
        import logging
        logging.error(f"Background schema extraction failed: {e}")


@router.get("/schema/status")
async def get_schema_status(
    user_context: UserContext = Depends(get_current_user)
):
    """Get schema extraction status"""
    try:
        schema_manager = get_schema_manager()
        
        return APIResponse(
            success=True,
            data={
                'tables_extracted': len(schema_manager.schemas),
                'last_update': datetime.utcnow().isoformat(),  # Placeholder
                'extraction_status': 'completed' if schema_manager.schemas else 'not_started'
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/recommendations", response_model=List[IndexRecommendation])
async def get_performance_recommendations(
    query: Optional[str] = None,
    user_context: UserContext = Depends(get_current_user)
):
    """Get performance optimization recommendations"""
    try:
        optimizer = get_performance_optimizer()
        
        if query:
            # Analyze specific query
            analysis = await optimizer.analyze_query_performance(query)
            recommendations = analysis.get('index_recommendations', [])
            
            return [
                IndexRecommendation(
                    table_name=rec.table_name,
                    columns=rec.columns,
                    index_type=rec.index_type.value,
                    priority=rec.priority,
                    reason=rec.reason,
                    estimated_benefit=rec.estimated_benefit,
                    sql_create_statement=rec.sql_create_statement
                )
                for rec in recommendations
            ]
        else:
            # Return general WMS recommendations
            return [
                IndexRecommendation(
                    table_name="inventory",
                    columns=["item_id", "location_id", "status"],
                    index_type="NONCLUSTERED",
                    priority="HIGH",
                    reason="Core inventory lookup pattern",
                    estimated_benefit="50x faster inventory queries",
                    sql_create_statement="CREATE NONCLUSTERED INDEX IX_Inventory_ItemLocationStatus ON inventory (item_id, location_id, status)"
                ),
                IndexRecommendation(
                    table_name="orders",
                    columns=["status", "priority", "created_date"],
                    index_type="NONCLUSTERED",
                    priority="HIGH",
                    reason="Order queue processing",
                    estimated_benefit="10x faster order queries",
                    sql_create_statement="CREATE NONCLUSTERED INDEX IX_Orders_StatusPriorityDate ON orders (status, priority, created_date)"
                )
            ]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test-connection")
async def test_database_connection(
    user_context: UserContext = Depends(get_current_user)
):
    """Test current database connection"""
    try:
        executor = get_sql_executor()
        connection_test = await executor.test_connection()
        
        return APIResponse(
            success=connection_test['connected'],
            data=connection_test,
            message="Database connection test completed"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/query-suggestions")
async def get_query_suggestions(
    category: Optional[str] = None,
    user_context: UserContext = Depends(get_current_user)
):
    """Get suggested queries for the current database"""
    try:
        executor = get_sql_executor()
        suggestions = await executor.get_query_suggestions(category)
        
        return APIResponse(
            success=True,
            data={
                'suggestions': suggestions,
                'category': category or 'all'
            },
            message="Query suggestions retrieved"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_query_statistics(
    user_context: UserContext = Depends(get_current_user)
):
    """Get query execution statistics"""
    try:
        executor = get_sql_executor()
        stats = executor.get_execution_stats()
        
        return APIResponse(
            success=True,
            data=stats,
            message="Query statistics retrieved"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-query")
async def analyze_query_performance(
    query: str,
    user_context: UserContext = Depends(get_current_user)
):
    """Analyze query performance without executing"""
    try:
        optimizer = get_performance_optimizer()
        analysis = await optimizer.analyze_query_performance(query)
        
        return APIResponse(
            success=True,
            data=analysis,
            message="Query performance analysis completed"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables")
async def get_database_tables(
    category: Optional[str] = None,
    user_context: UserContext = Depends(get_current_user)
):
    """Get database tables by category"""
    try:
        schema_manager = get_schema_manager()
        
        if category:
            tables = schema_manager.get_tables_by_category(category)
            table_data = [
                {
                    'table_name': f"{table.schema_name}.{table.table_name}",
                    'category': table.category,
                    'row_count': table.row_count,
                    'column_count': len(table.columns),
                    'description': table.description
                }
                for table in tables
            ]
        else:
            table_data = [
                {
                    'table_name': table_name,
                    'category': schema.category,
                    'row_count': schema.row_count,
                    'column_count': len(schema.columns),
                    'description': schema.description
                }
                for table_name, schema in schema_manager.schemas.items()
            ]
        
        return APIResponse(
            success=True,
            data={
                'tables': table_data,
                'total_count': len(table_data),
                'category_filter': category
            },
            message=f"Retrieved {len(table_data)} tables"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{table_name}/schema")
async def get_table_schema(
    table_name: str,
    user_context: UserContext = Depends(get_current_user)
):
    """Get detailed schema for a specific table"""
    try:
        schema_manager = get_schema_manager()
        schema = schema_manager.get_table_schema(table_name)
        
        if not schema:
            raise HTTPException(status_code=404, detail=f"Table {table_name} not found")
        
        return APIResponse(
            success=True,
            data=schema.to_dict(),
            message=f"Schema retrieved for table {table_name}"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))