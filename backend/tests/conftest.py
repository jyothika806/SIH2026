import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.db.models import Base


@pytest_asyncio.fixture
async def phase2_db() -> AsyncIterator[async_sessionmaker]:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to an isolated local PostGIS test database")
    admin_engine = create_async_engine(url)
    if (
        admin_engine.url.database != "phase2_test"
        or admin_engine.url.host not in {
        "localhost",
        "127.0.0.1",
        "::1",
        }
        or admin_engine.url.port != 55432
    ):
        await admin_engine.dispose()
        raise RuntimeError(
            "Tests refuse to modify databases other than local phase2_test on port 55432"
        )
    async with admin_engine.connect() as connection:
        postgis_available = await connection.scalar(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='postgis')")
        )
    if not postgis_available:
        await admin_engine.dispose()
        pytest.skip("The isolated phase2_test database needs the PostGIS extension")

    schema = f"phase2_test_{uuid.uuid4().hex}"
    try:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    except Exception:
        await admin_engine.dispose()
        raise
    engine = create_async_engine(
        url,
        connect_args={"server_settings": {"search_path": f"{schema},public"}},
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield sessions
    finally:
        await engine.dispose()
        try:
            async with admin_engine.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        finally:
            await admin_engine.dispose()
