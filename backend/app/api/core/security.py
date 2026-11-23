"""Authenticated principal dependencies backed by the canonical JWT auth router."""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.auth import get_current_user as auth_get_current_user
from backend.app.api.v1.core.database import get_db
from backend.app.db.models import User


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user_id: int
    role: str
    phone: str | None


async def get_authenticated_principal(
    user: dict = Depends(auth_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedPrincipal:
    subject = user.get("sub")
    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    account = await db.scalar(select(User).where(User.id == user_id))
    if account is None or not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is unavailable",
        )
    return AuthenticatedPrincipal(
        user_id=user_id,
        role=account.role.value,
        phone=account.phone,
    )


async def get_current_user(user: dict = Depends(auth_get_current_user)) -> dict:
    payload = dict(user)
    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    try:
        payload["id"] = int(subject)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    return payload
