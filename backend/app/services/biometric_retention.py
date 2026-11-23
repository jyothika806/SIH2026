"""Restart-safe biometric template retention cleanup."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.core.config import get_settings
from backend.app.db.models import FaceTemplate, VerificationAuditLog
from backend.app.services.utc_time import as_utc, utc_now


async def cleanup_expired_biometric_templates(
    db: AsyncSession,
    now: datetime | None = None,
) -> int:
    settings = get_settings()
    now = as_utc(now) if now is not None else utc_now()
    cutoff = now - timedelta(days=settings.biometric_retention_days)
    templates = await db.scalars(
        select(FaceTemplate)
        .where(
            FaceTemplate.created_at < cutoff,
            FaceTemplate.status != "expired_retention",
        )
        .with_for_update(skip_locked=True)
    )
    expired = list(templates)
    for template in expired:
        template.encrypted_embedding = b""
        template.status = "expired_retention"
        template.activated_at = None
        db.add(
            VerificationAuditLog(
                actor_id=None,
                driver_id=template.driver_id,
                action="biometric_template_retention",
                outcome="purged",
                reason_code="retention_period_elapsed",
                detail={
                    "template_id": template.id,
                    "retention_days": settings.biometric_retention_days,
                },
            )
        )
    return len(expired)
