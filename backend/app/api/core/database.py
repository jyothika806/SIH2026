"""Compatibility re-exports for the single SQLAlchemy base and engine."""

from backend.app.api.v1.core.database import (
    AsyncSessionLocal,
    Base,
    DatabaseManager,
    check_db_connection,
    close_db,
    db_manager,
    engine,
    get_db,
    init_db,
)

metadata = Base.metadata

__all__ = [
    "AsyncSessionLocal",
    "Base",
    "DatabaseManager",
    "check_db_connection",
    "close_db",
    "db_manager",
    "engine",
    "get_db",
    "init_db",
    "metadata",
]
