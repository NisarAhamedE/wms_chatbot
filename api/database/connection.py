import os
import asyncio
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
import logging
from sqlalchemy import create_engine, text, inspect, MetaData
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
import asyncpg
import pymssql

logger = logging.getLogger(__name__)

Base = declarative_base()

class DatabaseManager:
    """Manages database connections for both PostgreSQL and MS SQL"""
    
    def __init__(self):
        self.pg_engine: Optional[AsyncEngine] = None
        self.mssql_engine = None
        self.pg_session_factory = None
        self.metadata = MetaData()
        
    async def initialize(self):
        """Initialize database connections"""
        try:
            # PostgreSQL connection
            pg_url = f"postgresql+asyncpg://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
            self.pg_engine = create_async_engine(
                pg_url,
                echo=False,
                pool_pre_ping=True,
                pool_size=20,
                max_overflow=10
            )
            
            self.pg_session_factory = sessionmaker(
                self.pg_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables if not exist
            async with self.pg_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("PostgreSQL initialized successfully")
            
            # MS SQL connection for operational database
            if os.getenv("MSSQL_HOST"):
                self.mssql_engine = create_engine(
                    f"mssql+pymssql://{os.getenv('MSSQL_USER')}:{os.getenv('MSSQL_PASSWORD')}@{os.getenv('MSSQL_HOST')}/{os.getenv('MSSQL_DB')}",
                    poolclass=NullPool,
                    echo=False
                )
                logger.info("MS SQL initialized successfully")
                
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    @asynccontextmanager
    async def get_pg_session(self):
        """Get PostgreSQL session"""
        async with self.pg_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def execute_pg_query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute PostgreSQL query"""
        async with self.get_pg_session() as session:
            result = await session.execute(text(query), params or {})
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]
    
    def execute_mssql_query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute MS SQL query (synchronous)"""
        if not self.mssql_engine:
            raise ValueError("MS SQL not configured")
        
        with self.mssql_engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]
    
    async def get_mssql_schema(self, table_name: Optional[str] = None) -> Dict[str, Any]:
        """Get MS SQL database schema"""
        if not self.mssql_engine:
            raise ValueError("MS SQL not configured")
        
        inspector = inspect(self.mssql_engine)
        
        if table_name:
            columns = inspector.get_columns(table_name)
            indexes = inspector.get_indexes(table_name)
            pk = inspector.get_pk_constraint(table_name)
            fks = inspector.get_foreign_keys(table_name)
            
            return {
                "table": table_name,
                "columns": columns,
                "indexes": indexes,
                "primary_key": pk,
                "foreign_keys": fks
            }
        else:
            tables = inspector.get_table_names()
            schema = {}
            for table in tables:
                schema[table] = {
                    "columns": inspector.get_columns(table),
                    "indexes": inspector.get_indexes(table)
                }
            return schema
    
    async def test_connections(self) -> Dict[str, bool]:
        """Test all database connections"""
        results = {"postgresql": False, "mssql": False}
        
        # Test PostgreSQL
        try:
            async with self.get_pg_session() as session:
                await session.execute(text("SELECT 1"))
                results["postgresql"] = True
        except Exception as e:
            logger.error(f"PostgreSQL test failed: {e}")
        
        # Test MS SQL
        if self.mssql_engine:
            try:
                with self.mssql_engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                    results["mssql"] = True
            except Exception as e:
                logger.error(f"MS SQL test failed: {e}")
        
        return results
    
    async def close(self):
        """Close all database connections"""
        if self.pg_engine:
            await self.pg_engine.dispose()
        
        if self.mssql_engine:
            self.mssql_engine.dispose()

# Global instance
db_manager = DatabaseManager()

class QueryBuilder:
    """Builds safe SQL queries from natural language"""
    
    @staticmethod
    def build_select_query(
        table: str,
        columns: List[str] = None,
        conditions: Dict[str, Any] = None,
        order_by: str = None,
        limit: int = None
    ) -> tuple[str, Dict]:
        """Build a SELECT query"""
        columns_str = ", ".join(columns) if columns else "*"
        query = f"SELECT {columns_str} FROM {table}"
        params = {}
        
        if conditions:
            where_clauses = []
            for i, (key, value) in enumerate(conditions.items()):
                param_name = f"param_{i}"
                where_clauses.append(f"{key} = :{param_name}")
                params[param_name] = value
            
            query += " WHERE " + " AND ".join(where_clauses)
        
        if order_by:
            query += f" ORDER BY {order_by}"
        
        if limit:
            query += f" LIMIT {limit}"
        
        return query, params
    
    @staticmethod
    def validate_query(query: str) -> bool:
        """Validate query for safety"""
        dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE", "INSERT", "UPDATE"]
        query_upper = query.upper()
        
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                return False
        
        return True

class WMSQueryExecutor:
    """Executes WMS-specific queries"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    async def get_inventory_levels(self, sku: Optional[str] = None, warehouse: Optional[str] = None) -> List[Dict]:
        """Get inventory levels"""
        query = """
        SELECT 
            sku,
            warehouse_id,
            SUM(quantity_on_hand) as on_hand,
            SUM(quantity_available) as available,
            SUM(quantity_allocated) as allocated
        FROM inventory_items
        WHERE 1=1
        """
        params = {}
        
        if sku:
            query += " AND sku = :sku"
            params["sku"] = sku
        
        if warehouse:
            query += " AND warehouse_id = :warehouse"
            params["warehouse"] = warehouse
        
        query += " GROUP BY sku, warehouse_id"
        
        return await self.db.execute_pg_query(query, params)
    
    async def get_order_status(self, order_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict]:
        """Get order status"""
        query = """
        SELECT 
            order_id,
            status,
            created_at,
            updated_at,
            total_lines,
            total_quantity,
            priority
        FROM orders
        WHERE 1=1
        """
        params = {}
        
        if order_id:
            query += " AND order_id = :order_id"
            params["order_id"] = order_id
        
        if status:
            query += " AND status = :status"
            params["status"] = status
        
        query += " ORDER BY created_at DESC LIMIT 100"
        
        return await self.db.execute_pg_query(query, params)
    
    async def get_wave_status(self, wave_id: Optional[str] = None) -> List[Dict]:
        """Get wave status"""
        query = """
        SELECT 
            w.wave_id,
            w.status,
            w.created_at,
            w.released_at,
            COUNT(DISTINCT wo.order_id) as order_count,
            SUM(wo.total_lines) as total_lines,
            SUM(wo.picked_lines) as picked_lines
        FROM waves w
        LEFT JOIN wave_orders wo ON w.wave_id = wo.wave_id
        WHERE 1=1
        """
        params = {}
        
        if wave_id:
            query += " AND w.wave_id = :wave_id"
            params["wave_id"] = wave_id
        
        query += """
        GROUP BY w.wave_id, w.status, w.created_at, w.released_at
        ORDER BY w.created_at DESC
        LIMIT 50
        """
        
        return await self.db.execute_pg_query(query, params)
    
    async def get_picking_performance(self, user_id: Optional[str] = None, date_from: Optional[str] = None) -> List[Dict]:
        """Get picking performance metrics"""
        query = """
        SELECT 
            user_id,
            DATE(pick_timestamp) as pick_date,
            COUNT(*) as total_picks,
            AVG(pick_duration_seconds) as avg_pick_time,
            SUM(quantity_picked) as total_quantity,
            COUNT(DISTINCT order_id) as orders_picked
        FROM picking_transactions
        WHERE 1=1
        """
        params = {}
        
        if user_id:
            query += " AND user_id = :user_id"
            params["user_id"] = user_id
        
        if date_from:
            query += " AND pick_timestamp >= :date_from"
            params["date_from"] = date_from
        
        query += """
        GROUP BY user_id, DATE(pick_timestamp)
        ORDER BY pick_date DESC
        """
        
        return await self.db.execute_pg_query(query, params)

# Global query executor
wms_query_executor = WMSQueryExecutor(db_manager)