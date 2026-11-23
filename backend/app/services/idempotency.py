"""Database-backed idempotency claims for booking and cancellation requests."""

import hashlib
import json

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import IdempotencyRecord


def request_digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


async def claim_idempotency(
    db: AsyncSession,
    user_id: int,
    route: str,
    key: str | None,
    payload: object,
) -> tuple[IdempotencyRecord | None, dict | None]:
    if not key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    if len(key) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key is too long")

    digest = request_digest(payload)
    record = await db.scalar(
        select(IdempotencyRecord)
        .where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.route == route,
            IdempotencyRecord.key == key,
        )
        .with_for_update()
    )
    if record is not None:
        if record.request_hash != digest:
            raise HTTPException(status_code=422, detail="Idempotency key was used with a different request")
        if record.status == "completed" and record.response_json is not None:
            return None, record.response_json
        raise HTTPException(status_code=409, detail="Request with this idempotency key is still in flight")

    record = IdempotencyRecord(
        user_id=user_id,
        route=route,
        key=key,
        request_hash=digest,
        status="in_flight",
    )
    db.add(record)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Request with this idempotency key is still in flight")
    return record, None


def complete_idempotency(record: IdempotencyRecord, response: dict) -> None:
    record.response_json = response
    record.status = "completed"
