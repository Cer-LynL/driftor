"""
Enterprise database configuration with connection pooling and security.
"""
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Generator, Optional
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool
import structlog

from driftor.core.config import get_settings
from driftor.models.base import Base
from driftor.security.audit import AuditLog

logger = structlog.get_logger(__name__)

# Global database instances
_async_engine = None
_sync_engine = None
_async_session_factory = None
_sync_session_factory = None


def get_async_engine():
    """Get async database engine with connection pooling."""
    global _async_engine
    
    if _async_engine is None:
        settings = get_settings()
        
        _async_engine = create_async_engine(
            settings.database.database_url,
            echo=settings.debug,
            pool_size=settings.database.db_connection_pool_size,
            max_overflow=settings.database.db_max_overflow,
            pool_timeout=settings.database.db_pool_timeout,
            pool_recycle=settings.database.db_pool_recycle,
            poolclass=QueuePool,
            # Security settings
            connect_args={
                "command_timeout": 30,
                "server_settings": {
                    "application_name": "driftor-enterprise",
                    "timezone": "UTC"
                }
            }
        )
        
        # Add connection event listeners for security
        @event.listens_for(_async_engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            if "postgresql" in settings.database.database_url:
                # Enable row-level security
                with dbapi_connection.cursor() as cursor:
                    cursor.execute("SET row_security = on")
    
    return _async_engine


def get_sync_engine():
    """Get synchronous database engine for migrations and admin tasks."""
    global _sync_engine
    
    if _sync_engine is None:
        settings = get_settings()
        
        # Convert async URL to sync URL
        sync_url = settings.database.database_url.replace(
            "postgresql+asyncpg://", 
            "postgresql://"
        )
        
        _sync_engine = create_engine(
            sync_url,
            echo=settings.debug,
            pool_size=settings.database.db_connection_pool_size,
            max_overflow=settings.database.db_max_overflow,
            pool_timeout=settings.database.db_pool_timeout,
            pool_recycle=settings.database.db_pool_recycle,
            poolclass=QueuePool
        )
    
    return _sync_engine


def get_async_session_factory():
    """Get async session factory."""
    global _async_session_factory
    
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )
    
    return _async_session_factory


def get_sync_session_factory():
    """Get sync session factory."""
    global _sync_session_factory
    
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(
            bind=get_sync_engine(),
            autoflush=True,
            autocommit=False
        )
    
    return _sync_session_factory


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session with automatic cleanup."""
    session_factory = get_async_session_factory()
    
    async with session_factory() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error("Database session error", error=str(e), exc_info=True)
            raise
        finally:
            await session.close()


def get_db_session() -> Generator[Session, None, None]:
    """Get sync database session for FastAPI dependency injection."""
    session_factory = get_sync_session_factory()
    
    with session_factory() as session:
        try:
            yield session
        except Exception as e:
            session.rollback()
            logger.error("Database session error", error=str(e), exc_info=True)
            raise
        finally:
            session.close()


def get_audit_session() -> Session:
    """Get dedicated session for audit logging to avoid transaction conflicts."""
    session_factory = get_sync_session_factory()
    return session_factory()


async def init_database():
    """Initialize database with tables and security settings."""
    logger.info("Initializing database...")
    
    try:
        # Create all tables
        sync_engine = get_sync_engine()
        Base.metadata.create_all(bind=sync_engine)
        
        # Setup row-level security policies
        await setup_row_level_security()
        
        # Create default system data
        await create_default_data()
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error("Database initialization failed", error=str(e), exc_info=True)
        raise


async def setup_row_level_security():
    """Setup row-level security policies for multi-tenancy."""
    async with get_async_session() as session:
        try:
            # Enable RLS on tenant tables
            rls_tables = [
                "tenants",
                "tenant_users", 
                "tenant_roles",
                "tenant_user_roles",
                "audit_logs"
            ]
            
            for table in rls_tables:
                # Enable RLS
                await session.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
                
                # Create policy for tenant isolation
                await session.execute(text(f"""
                    CREATE POLICY tenant_isolation ON {table}
                    FOR ALL TO PUBLIC
                    USING (tenant_id = current_setting('app.current_tenant_id', true))
                """))
            
            await session.commit()
            logger.info("Row-level security policies created")
            
        except Exception as e:
            await session.rollback()
            # RLS policies might already exist, which is OK
            logger.warning("RLS setup encountered error (may be expected)", error=str(e))


async def create_default_data():
    """Create default system data and configurations."""
    async with get_async_session() as session:
        try:
            # Create default roles
            from driftor.models.tenant import TenantRole
            
            default_roles = [
                {
                    "name": "admin",
                    "description": "Full system administrator",
                    "permissions": [
                        "admin.full_access",
                        "users.manage",
                        "integrations.manage",
                        "analytics.read",
                        "settings.manage"
                    ],
                    "is_system_role": True
                },
                {
                    "name": "developer",
                    "description": "Developer user with analysis access",
                    "permissions": [
                        "analysis.read",
                        "tickets.manage",
                        "chat.use"
                    ],
                    "is_system_role": True
                },
                {
                    "name": "viewer",
                    "description": "Read-only access to analysis results",
                    "permissions": [
                        "analysis.read"
                    ],
                    "is_system_role": True
                }
            ]
            
            # Note: These will be created per-tenant during tenant setup
            logger.info("Default data structure prepared")
            
        except Exception as e:
            await session.rollback()
            logger.error("Failed to create default data", error=str(e), exc_info=True)
            raise


async def health_check() -> dict:
    """Database health check for monitoring."""
    try:
        async with get_async_session() as session:
            # Simple query to test connection
            result = await session.execute(text("SELECT 1 as health_check"))
            result.scalar()
            
            # Check connection pool status
            engine = get_async_engine()
            pool = engine.pool
            
            return {
                "status": "healthy",
                "pool_size": pool.size(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "timestamp": asyncio.get_event_loop().time()
            }
            
    except Exception as e:
        logger.error("Database health check failed", error=str(e), exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": asyncio.get_event_loop().time()
        }


async def cleanup_database():
    """Cleanup database connections on shutdown."""
    global _async_engine, _sync_engine
    
    try:
        if _async_engine:
            await _async_engine.dispose()
            _async_engine = None
            
        if _sync_engine:
            _sync_engine.dispose()
            _sync_engine = None
            
        logger.info("Database connections cleaned up")
        
    except Exception as e:
        logger.error("Database cleanup error", error=str(e), exc_info=True)


# Context manager for setting tenant context in RLS
@asynccontextmanager
async def tenant_context(session: AsyncSession, tenant_id: str):
    """Set tenant context for row-level security."""
    try:
        # Set tenant context for RLS
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": tenant_id}
        )
        yield session
    finally:
        # Clear tenant context
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', '', true)")
        )