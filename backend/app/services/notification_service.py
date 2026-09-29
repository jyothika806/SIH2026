"""
Notification Service with FCM and Twilio SMS Integration

This module implements:
- FCM push notifications
- Twilio SMS fallback
- In-app notification management
- Notification history

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime
from enum import Enum
import logging
import json

from backend.app.db.models import Notification, User
from backend.app.api.core.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()


class NotificationType(str, Enum):
    RIDE = "ride"
    OTP = "otp"
    EMERGENCY = "emergency"
    PROMO = "promo"
    PAYMENT = "payment"
    RATING = "rating"


class NotificationService:
    """
    Notification service with FCM and Twilio SMS.
    
    Provides:
    - FCM push notifications
    - Twilio SMS fallback
    - In-app notification management
    - Notification history
    """
    
    def __init__(self):
        """Initialize notification service."""
        self.fcm_enabled = settings.fcm_enabled if hasattr(settings, 'fcm_enabled') else False
        self.twilio_enabled = settings.twilio_enabled if hasattr(settings, 'twilio_enabled') else False
    
    async def create_notification(
        self,
        session: AsyncSession,
        user_id: int,
        title: str,
        body: str,
        notification_type: NotificationType,
        data: Optional[Dict] = None
    ) -> Notification:
        """
        Create a notification record.
        
        Args:
            session: Async database session
            user_id: Recipient user ID
            title: Notification title
            body: Notification body
            notification_type: Type of notification
            data: Additional data payload
            
        Returns:
            Notification instance
        """
        notification = Notification(
            user_id=user_id,
            title=title,
            body=body,
            type=notification_type.value,
            data=data or {}
        )
        
        session.add(notification)
        await session.commit()
        await session.refresh(notification)
        
        logger.info(f"Created notification {notification.id} for user {user_id}")
        return notification
    
    async def send_push_notification(
        self,
        notification: Notification,
        fcm_token: Optional[str] = None
    ) -> Dict:
        """
        Send FCM push notification.
        
        Args:
            notification: Notification instance
            fcm_token: FCM token for the user
            
        Returns:
            Send result
        """
        try:
            if not self.fcm_enabled:
                logger.warning("FCM is not enabled")
                return {
                    "success": False,
                    "error": "FCM not enabled"
                }
            
            if not fcm_token:
                return {
                    "success": False,
                    "error": "No FCM token provided"
                }
            
            # Import firebase_admin if available
            try:
                import firebase_admin
                from firebase_admin import credentials, messaging
            except ImportError:
                logger.error("firebase_admin not installed")
                return {
                    "success": False,
                    "error": "firebase_admin not installed"
                }
            
            # Initialize Firebase app if not already initialized
            if not firebase_admin._apps:
                cred_path = settings.fcm_credentials_path if hasattr(settings, 'fcm_credentials_path') else None
                if cred_path:
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                else:
                    logger.warning("No FCM credentials path provided")
                    return {
                        "success": False,
                        "error": "No FCM credentials"
                    }
            
            # Create FCM message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=notification.title,
                    body=notification.body
                ),
                data=notification.data,
                token=fcm_token
            )
            
            # Send message
            response = messaging.send(message)
            
            logger.info(f"FCM notification sent: {response}")
            
            return {
                "success": True,
                "message_id": response
            }
            
        except Exception as e:
            logger.error(f"Error sending FCM notification: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def send_sms(
        self,
        phone: str,
        message: str
    ) -> Dict:
        """
        Send SMS via Twilio.
        
        Args:
            phone: Phone number (with country code)
            message: SMS message
            
        Returns:
            Send result
        """
        try:
            if not self.twilio_enabled:
                logger.warning("Twilio is not enabled")
                return {
                    "success": False,
                    "error": "Twilio not enabled"
                }
            
            # Import twilio if available
            try:
                from twilio.rest import Client
            except ImportError:
                logger.error("twilio not installed")
                return {
                    "success": False,
                    "error": "twilio not installed"
                }
            
            account_sid = settings.twilio_account_sid if hasattr(settings, 'twilio_account_sid') else None
            auth_token = settings.twilio_auth_token if hasattr(settings, 'twilio_auth_token') else None
            from_number = settings.twilio_from_number if hasattr(settings, 'twilio_from_number') else None
            
            if not all([account_sid, auth_token, from_number]):
                logger.warning("Twilio credentials not configured")
                return {
                    "success": False,
                    "error": "Twilio credentials not configured"
                }
            
            client = Client(account_sid, auth_token)
            
            message_obj = client.messages.create(
                body=message,
                from_=from_number,
                to=phone
            )
            
            logger.info(f"SMS sent to {phone}: {message_obj.sid}")
            
            return {
                "success": True,
                "message_sid": message_obj.sid
            }
            
        except Exception as e:
            logger.error(f"Error sending SMS: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def send_notification(
        self,
        session: AsyncSession,
        user_id: int,
        title: str,
        body: str,
        notification_type: NotificationType,
        data: Optional[Dict] = None,
        use_sms_fallback: bool = False
    ) -> Dict:
        """
        Send notification with FCM and SMS fallback.
        
        Args:
            session: Async database session
            user_id: Recipient user ID
            title: Notification title
            body: Notification body
            notification_type: Type of notification
            data: Additional data payload
            use_sms_fallback: Whether to use SMS fallback
            
        Returns:
            Send result
        """
        # Create notification record
        notification = await self.create_notification(
            session,
            user_id,
            title,
            body,
            notification_type,
            data
        )
        
        # Get user's FCM token and phone
        user = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = user.scalar_one_or_none()
        
        if not user:
            return {
                "success": False,
                "error": "User not found"
            }
        
        # Try FCM first
        fcm_result = await self.send_push_notification(
            notification,
            user.fcm_token
        )
        
        if fcm_result.get('success'):
            # Update notification as sent
            await session.execute(
                update(Notification)
                .where(Notification.id == notification.id)
                .values(
                    fcm_sent=True,
                    fcm_message_id=fcm_result.get('message_id')
                )
            )
            await session.commit()
            
            return {
                "success": True,
                "notification_id": notification.id,
                "channel": "fcm",
                "message_id": fcm_result.get('message_id')
            }
        
        # FCM failed, try SMS fallback
        if use_sms_fallback and user.phone:
            sms_result = await self.send_sms(user.phone, body)
            
            if sms_result.get('success'):
                return {
                    "success": True,
                    "notification_id": notification.id,
                    "channel": "sms",
                    "message_sid": sms_result.get('message_sid')
                }
        
        # Both failed
        return {
            "success": False,
            "notification_id": notification.id,
            "error": "Failed to send notification via all channels"
        }
    
    async def get_user_notifications(
        self,
        session: AsyncSession,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get notifications for a user.
        
        Args:
            session: Async database session
            user_id: User ID
            unread_only: Whether to get only unread notifications
            limit: Maximum number of notifications
            
        Returns:
            List of notifications
        """
        query = select(Notification).where(Notification.user_id == user_id)
        
        if unread_only:
            query = query.where(Notification.read == False)
        
        notifications = await session.execute(
            query.order_by(Notification.created_at.desc())
            .limit(limit)
        )
        
        notifications = notifications.scalars().all()
        
        return [
            {
                "notification_id": notif.id,
                "title": notif.title,
                "body": notif.body,
                "type": notif.type,
                "data": notif.data,
                "read": notif.read,
                "created_at": notif.created_at.isoformat()
            }
            for notif in notifications
        ]
    
    async def mark_as_read(
        self,
        session: AsyncSession,
        notification_id: int,
        user_id: int
    ) -> Dict:
        """
        Mark notification as read.
        
        Args:
            session: Async database session
            notification_id: Notification ID
            user_id: User ID (for ownership check)
            
        Returns:
            Update result
        """
        notification = await session.execute(
            select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id
                )
            )
        )
        notification = notification.scalar_one_or_none()
        
        if not notification:
            return {
                "success": False,
                "error": "Notification not found"
            }
        
        await session.execute(
            update(Notification)
            .where(Notification.id == notification_id)
            .values(read=True)
        )
        await session.commit()
        
        return {
            "success": True,
            "notification_id": notification_id
        }
    
    async def mark_all_as_read(
        self,
        session: AsyncSession,
        user_id: int
    ) -> Dict:
        """
        Mark all notifications as read for a user.
        
        Args:
            session: Async database session
            user_id: User ID
            
        Returns:
            Update result
        """
        await session.execute(
            update(Notification)
            .where(
                and_(
                    Notification.user_id == user_id,
                    Notification.read == False
                )
            )
            .values(read=True)
        )
        await session.commit()
        
        return {
            "success": True,
            "user_id": user_id
        }


# Global notification service instance
notification_service = NotificationService()


if __name__ == "__main__":
    import asyncio
    
    async def test_notification_service():
        """Test notification service."""
        print("Testing Notification Service...")
        
        service = NotificationService()
        print("Notification service initialized successfully")
        print(f"FCM enabled: {service.fcm_enabled}")
        print(f"Twilio enabled: {service.twilio_enabled}")
        
        print("\nNotification service test completed!")
    
    asyncio.run(test_notification_service())
