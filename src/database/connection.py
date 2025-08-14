"""
Database connection management with async support and connection pooling.
Provides both async and sync database sessions for different use cases.
"""

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from ..core.config import get_database_settings
from ..core.logging import get_logger
from .models import Base

logger = get_logger(__name__)


class DatabaseManager:
    """Database connection and session management"""
    
    def __init__(self):
        self.settings = get_database_settings()
        self._async_engine = None
        self._sync_engine = None
        self._async_session_factory = None
        self._sync_session_factory = None
    
    def _create_async_engine(self):
        """Create async database engine with optimized settings"""
        if self._async_engine is None:
            self._async_engine = create_async_engine(
                self.settings.postgres_url,
                echo=False,  # Set to True for SQL logging in development
                pool_size=20,
                max_overflow=30,
                pool_timeout=30,
                pool_recycle=3600,  # 1 hour
                pool_pre_ping=True,
                poolclass=QueuePool,
                # Async specific settings
                future=True,
            )
            
            # Add event listeners for connection management
            @event.listens_for(self._async_engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                """Set database-specific configurations"""
                if hasattr(dbapi_connection, "set_isolation_level"):
                    # PostgreSQL specific settings
                    pass
            
            logger.info("Async database engine created")
        
        return self._async_engine
    
    def _create_sync_engine(self):
        """Create synchronous database engine for migrations and maintenance"""
        if self._sync_engine is None:
            self._sync_engine = create_engine(
                self.settings.postgres_sync_url,
                echo=False,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True,
                poolclass=QueuePool,
            )
            
            logger.info("Sync database engine created")
        
        return self._sync_engine
    
    def get_async_session_factory(self):
        """Get async session factory"""
        if self._async_session_factory is None:
            engine = self._create_async_engine()
            self._async_session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False,
            )
        
        return self._async_session_factory
    
    def get_sync_session_factory(self):
        """Get sync session factory"""
        if self._sync_session_factory is None:
            engine = self._create_sync_engine()
            self._sync_session_factory = sessionmaker(
                engine,
                autoflush=True,
                autocommit=False,
            )
        
        return self._sync_session_factory
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session with automatic cleanup"""
        session_factory = self.get_async_session_factory()
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()
    
    @contextmanager
    def get_sync_session(self) -> Generator[Session, None, None]:
        """Get sync database session with automatic cleanup"""
        session_factory = self.get_sync_session_factory()
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    async def create_tables(self):
        """Create all database tables"""
        engine = self._create_async_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")
    
    async def drop_tables(self):
        """Drop all database tables (use with caution!)"""
        engine = self._create_async_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.warning("Database tables dropped")
    
    async def check_connection(self) -> bool:
        """Check database connectivity"""
        try:
            async with self.get_async_session() as session:
                result = await session.execute("SELECT 1")
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
    
    def check_sync_connection(self) -> bool:
        """Check database connectivity (synchronous)"""
        try:
            with self.get_sync_session() as session:
                result = session.execute("SELECT 1")
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
    
    async def initialize_seed_data(self):
        """Initialize seed data for WMS categories and roles"""
        async with self.get_async_session() as session:
            await self._create_wms_categories(session)
            await self._create_default_roles(session)
            logger.info("Seed data initialized")
    
    async def _create_wms_categories(self, session: AsyncSession):
        """Create the 16 WMS categories and their sub-categories"""
        from .models import WMSCategory, WMSSubCategory
        
        categories_data = [
            (1, 'WMS Introduction', 'INTRO', 'System overview and general WMS concepts'),
            (2, 'Locations', 'LOC', 'Location management and warehouse layout'),
            (3, 'Items', 'ITEMS', 'Item master data and product information'),
            (4, 'Receiving', 'REC', 'Inbound operations and receipt processing'),
            (5, 'Locating and Putaway', 'PUT', 'Putaway strategies and location assignment'),
            (6, 'Work Management', 'WORK', 'Labor management and task assignment'),
            (7, 'Inventory Management', 'INV', 'Stock tracking and inventory control'),
            (8, 'Cycle Counting', 'COUNT', 'Inventory counting and accuracy management'),
            (9, 'Wave Management', 'WAVE', 'Wave planning and release strategies'),
            (10, 'Allocation', 'ALLOC', 'Inventory allocation and shortage management'),
            (11, 'Replenishment', 'REPL', 'Stock replenishment and min/max planning'),
            (12, 'Picking', 'PICK', 'Pick operations and path optimization'),
            (13, 'Packing', 'PACK', 'Packing operations and cartonization'),
            (14, 'Shipping and Carrier Management', 'SHIP', 'Outbound operations and carrier integration'),
            (15, 'Yard Management', 'YARD', 'Dock scheduling and yard operations'),
            (16, 'Other (Data Categorization)', 'OTHER', 'Data categorization, validation, and uncategorized information'),
        ]
        
        sub_categories_data = [
            ('FUNC', 'Functional', 'Functional aspects and business processes'),
            ('TECH', 'Technical', 'Technical specifications and system details'),
            ('CONF', 'Configuration', 'System configuration and setup'),
            ('REL', 'Relationships', 'Integration and relationship with other modules'),
            ('NOTES', 'Notes and Remarks', 'Additional notes, best practices, and remarks'),
        ]
        
        # Create categories
        for cat_id, name, code, desc in categories_data:
            # Check if category already exists
            existing = await session.get(WMSCategory, cat_id)
            if not existing:
                category = WMSCategory(
                    category_id=cat_id,
                    category_name=name,
                    category_code=code,
                    description=desc
                )
                session.add(category)
        
        await session.flush()  # Ensure categories are created before sub-categories
        
        # Create sub-categories for each category
        for cat_id, _, _, _ in categories_data:
            for sub_code, sub_name, sub_desc in sub_categories_data:
                # Check if sub-category already exists
                from sqlalchemy import select
                stmt = select(WMSSubCategory).where(
                    WMSSubCategory.category_id == cat_id,
                    WMSSubCategory.sub_category_code == sub_code
                )
                existing = await session.execute(stmt)
                if not existing.scalar():
                    sub_category = WMSSubCategory(
                        category_id=cat_id,
                        sub_category_name=sub_name,
                        sub_category_code=sub_code,
                        description=sub_desc
                    )
                    session.add(sub_category)
    
    async def _create_default_roles(self, session: AsyncSession):
        """Create default user roles"""
        from .models import Role
        
        roles_data = [
            ('end_user', 'End User', 'Basic warehouse operations user', ['read', 'basic_query']),
            ('operations_user', 'Operations User', 'Warehouse operations specialist', ['read', 'write', 'execute_operations']),
            ('admin_user', 'Admin User', 'System administrator', ['read', 'write', 'delete', 'configure', 'manage_users']),
            ('management_user', 'Management User', 'Warehouse management', ['read', 'analyze', 'report']),
            ('ceo_user', 'CEO User', 'Executive level access', ['read', 'strategic_analysis']),
        ]
        
        for role_name, description, role_desc, permissions in roles_data:
            # Check if role already exists
            from sqlalchemy import select
            stmt = select(Role).where(Role.role_name == role_name)
            existing = await session.execute(stmt)
            if not existing.scalar():
                role = Role(
                    role_name=role_name,
                    role_description=role_desc,
                    permissions=permissions
                )
                session.add(role)
    
    async def close(self):
        """Close all database connections"""
        if self._async_engine:
            await self._async_engine.dispose()
        if self._sync_engine:
            self._sync_engine.dispose()
        logger.info("Database connections closed")


# Global database manager instance
_db_manager = None


def get_database_manager() -> DatabaseManager:
    """Get global database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


# Dependency for FastAPI
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions"""
    db_manager = get_database_manager()
    async with db_manager.get_async_session() as session:
        yield session


# Utility functions for common database operations
async def execute_with_retry(operation, max_retries: int = 3, delay: float = 1.0):
    """Execute database operation with retry logic"""
    import asyncio
    
    for attempt in range(max_retries):
        try:
            return await operation()
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Database operation failed after {max_retries} attempts: {e}")
                raise
            
            logger.warning(f"Database operation failed (attempt {attempt + 1}/{max_retries}): {e}")
            await asyncio.sleep(delay * (2 ** attempt))  # Exponential backoff


async def health_check() -> dict:
    """Database health check for monitoring"""
    db_manager = get_database_manager()
    
    try:
        start_time = time.time()
        is_connected = await db_manager.check_connection()
        response_time = time.time() - start_time
        
        return {
            "status": "healthy" if is_connected else "unhealthy",
            "response_time_ms": round(response_time * 1000, 2),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }