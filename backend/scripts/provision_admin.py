"""Operator-only CLI for promoting an existing account to administrator."""

import argparse
import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.api.v1.core.config import get_settings
from backend.app.db.models import User, UserRole, VerificationAuditLog
from backend.app.services.phone_numbers import normalize_phone
from backend.app.services.utc_time import utc_now


async def provision_admin(database_url: str, phone: str, operator: str) -> None:
    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session, session.begin():
            normalized_phone = normalize_phone(
                phone, get_settings().phone_default_region
            )
            account = await session.scalar(
                select(User)
                .where(User.phone == normalized_phone)
                .with_for_update()
            )
            if account is None:
                raise RuntimeError("The target account must already exist.")
            if not account.is_active:
                raise RuntimeError("An inactive account cannot be promoted.")
            previous_role = account.role.value
            account.role = UserRole.ADMIN
            session.add(
                VerificationAuditLog(
                    actor_id=None,
                    action="admin_account_provisioned",
                    outcome="success",
                    reason_code="operator_cli",
                    detail={
                        "operator": operator,
                        "target_user_id": account.id,
                        "previous_role": previous_role,
                    },
                )
            )
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    if args.confirm != "PROVISION-ADMIN":
        parser.error("--confirm must be PROVISION-ADMIN")
    operator = os.getenv("ADMIN_PROVISIONING_OPERATOR", "").strip()
    database_url = os.getenv("ADMIN_PROVISION_DATABASE_URL", "").strip()
    phone = os.getenv("ADMIN_PROVISION_TARGET_PHONE", "").strip()
    if not operator:
        parser.error("ADMIN_PROVISIONING_OPERATOR must identify the operator")
    if not database_url:
        parser.error("ADMIN_PROVISION_DATABASE_URL must be set")
    if not phone:
        parser.error("ADMIN_PROVISION_TARGET_PHONE must be set")
    if not database_url.startswith(("postgresql+asyncpg://", "postgresql://")):
        parser.error("ADMIN_PROVISION_DATABASE_URL must target PostgreSQL")
    asyncio.run(provision_admin(database_url, phone, operator))


if __name__ == "__main__":
    main()
