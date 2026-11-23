"""Create one passenger account in the disposable phase2_e2e database."""

import asyncio
import os

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.db.models import User, UserRole


def _validate_target(url: str) -> None:
    parsed = make_url(url)
    if (
        parsed.host not in {"localhost", "127.0.0.1", "::1"}
        or parsed.port != 55432
        or parsed.database != "phase2_e2e"
    ):
        raise RuntimeError(
            "Refusing to seed anything except local phase2_e2e on port 55432"
        )


async def main() -> None:
    database_url = os.getenv("PHASE2_E2E_DATABASE_URL")
    phone = os.getenv("PHASE2_E2E_TEST_PHONE")
    if not database_url or not phone:
        raise RuntimeError(
            "Set PHASE2_E2E_DATABASE_URL and PHASE2_E2E_TEST_PHONE."
        )
    _validate_target(database_url)

    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            existing = await session.scalar(
                select(User).where(User.phone == phone)
            )
            if existing is not None:
                raise RuntimeError(
                    "The test phone already exists; choose an unused test number."
                )
            session.add(User(phone=phone, role=UserRole.PASSENGER))
            await session.commit()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
