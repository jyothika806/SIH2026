"""
Async Database Configuration with SQLAlchemy + PostGIS

This module sets up:
- Async PostgreSQL engine with asyncpg driver
- PostGIS extension for spatial queries
- Async session management
- Database connection pooling

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData, text
from typing import AsyncGenerator
import logging

from app.core.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create async engine
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout,
    pool_recycle=settings.database_pool_recycle,
    echo=settings.debug,
    future=True
)

# Create async session maker
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Create declarative base for models
Base = declarative_base()

# Metadata for custom operations
metadata = MetaData()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to get async database session.
    
    Yields:
        AsyncSession: Async database session
        
    Example:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {str(e)}")
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database tables and extensions.
    
    Creates all tables and ensures PostGIS extension is enabled.
    Should be called on application startup.
    """
    try:
        async with engine.begin() as conn:
            # Enable PostGIS extension
            await conn.execute(
                text("CREATE EXTENSION IF NOT EXISTS postgis")
            )
            logger.info("PostGIS extension enabled")
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
            
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise


async def close_db() -> None:
    """
    Close database connections.
    
    Should be called on application shutdown.
    """
    try:
        await engine.dispose()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Error closing database: {str(e)}")


async def check_db_connection() -> bool:
    """
    Check database connection health.
    
    Returns:
        bool: True if connection is healthy, False otherwise
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Database connection check failed: {str(e)}")
        return False


class DatabaseManager:
    """
    Database manager for advanced operations.
    
    Provides utility methods for common database operations.
    """
    
    @staticmethod
    async def truncate_table(table_name: str) -> None:
        """
        Truncate a table (use with caution in production).
        
        Args:
            table_name: Name of the table to truncate
        """
        async with AsyncSessionLocal() as session:
            await session.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
            await session.commit()
            logger.info(f"Table {table_name} truncated")
    
    @staticmethod
    async def get_table_size(table_name: str) -> int:
        """
        Get the number of rows in a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            int: Number of rows in the table
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(f"SELECT COUNT(*) FROM {table_name}")
            )
            return result.scalar()
    
    @staticmethod
    async def vacuum_analyze(table_name: str) -> None:
        """
        Run VACUUM ANALYZE on a table.
        
        Args:
            table_name: Name of the table to vacuum
        """
        async with AsyncSessionLocal() as session:
            await session.execute(text(f"VACUUM ANALYZE {table_name}"))
            await session.commit()
            logger.info(f"VACUUM ANALYZE completed for {table_name}")


# Global database manager instance
db_manager = DatabaseManager()


if __name__ == "__main__":
    import asyncio
    
    async def test_database():
        """Test database connection and initialization."""
        print("Testing Database Configuration...")
        
        # Test connection
        connection_ok = await check_db_connection()
        print(f"Database connection: {'OK' if connection_ok else 'FAILED'}")
        
        # Initialize database (commented out for safety)
        # await init_db()
        # print("Database initialized")
        
        print("\nDatabase configuration test completed!")
    
    asyncio.run(test_database())
