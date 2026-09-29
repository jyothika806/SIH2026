"""
Notification API Endpoints

Endpoints:
- Send notification
- Get user notifications
- Mark notification as read
- Mark all notifications as read
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

from backend.app.api.v1.core.security import get_current_user
from backend.app.api.v1.core.database import get_db
from backend.app.services.notification_service import notification_service, NotificationType

router = APIRouter(prefix="/notification", tags=["Notification"])


class SendNotificationRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=1000)
    notification_type: str = Field(..., pattern="^(ride|otp|emergency|promo|payment|rating)$")
    data: Optional[Dict] = None
    use_sms_fallback: bool = False


@router.post("/send")
async def send_notification(
    request: SendNotificationRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a notification to a user.
    
    Requires admin authentication.
    """
    if current_user.get('role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can send notifications"
        )
    
    notification_type = NotificationType(request.notification_type)
    
    result = await notification_service.send_notification(
        db,
        request.user_id,
        request.title,
        request.body,
        notification_type,
        request.data,
        request.use_sms_fallback
    )
    
    return result


@router.get("/my")
async def get_my_notifications(
    unread_only: bool = False,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get notifications for the current user.
    """
    user_id = current_user.get('id')
    
    notifications = await notification_service.get_user_notifications(
        db,
        user_id,
        unread_only,
        limit
    )
    
    return {
        "success": True,
        "user_id": user_id,
        "unread_only": unread_only,
        "notifications": notifications,
        "count": len(notifications)
    }


@router.post("/mark-read/{notification_id}")
async def mark_as_read(
    notification_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark a notification as read.
    """
    user_id = current_user.get('id')
    
    result = await notification_service.mark_as_read(db, notification_id, user_id)
    
    if not result.get('success'):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get('error')
        )
    
    return result


@router.post("/mark-all-read")
async def mark_all_as_read(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark all notifications as read for the current user.
    """
    user_id = current_user.get('id')
    
    result = await notification_service.mark_all_as_read(db, user_id)
    
    return result
