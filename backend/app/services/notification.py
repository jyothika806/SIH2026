"""
Firebase Cloud Messaging (FCM) Notification Service

This module implements:
- FCM push notification sender
- Multi-device notification support
- Notification payload management
- Delivery status tracking

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

import httpx
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import asyncio

from backend.app.api.core.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()


class NotificationType(str):
    """Notification type constants."""
    RIDE_REQUEST = "ride_request"
    RIDE_ACCEPTED = "ride_accepted"
    RIDE_STARTED = "ride_started"
    RIDE_COMPLETED = "ride_completed"
    DRIVER_ARRIVED = "driver_arrived"
    MID_ROUTE_REQUEST = "mid_route_request"
    MID_ROUTE_CONSENT = "mid_route_consent"
    OTP_DELIVERY = "otp_delivery"
    MODAL_SHIFT_SUGGESTION = "modal_shift_suggestion"
    SAFETY_ALERT = "safety_alert"


class FCMService:
    """
    Firebase Cloud Messaging service for push notifications.
    
    Provides methods for:
    - Sending push notifications to individual devices
    - Sending notifications to multiple devices
    - Topic-based messaging
    - Notification payload management
    """
    
    def __init__(self):
        """Initialize FCM service."""
        self.api_key = settings.fcm_api_key
        self.project_id = settings.fcm_project_id
        self.fcm_endpoint = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        
        if self.api_key:
            self.fcm_endpoint = self.fcm_endpoint.format(project_id=self.project_id)
            logger.info("FCM service initialized with project ID")
        else:
            logger.warning("FCM API key not configured, notifications will be disabled")
    
    async def send_notification(
        self,
        fcm_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        notification_type: Optional[str] = None,
        priority: str = "high"
    ) -> Dict[str, Any]:
        """
        Send push notification to a single device.
        
        Args:
            fcm_token: Device FCM token
            title: Notification title
            body: Notification body
            data: Additional data payload
            notification_type: Type of notification
            priority: Notification priority (high/normal)
            
        Returns:
            Dictionary with delivery status
        """
        if not self.api_key:
            logger.warning("FCM not configured, skipping notification")
            return {"success": False, "error": "FCM not configured"}
        
        try:
            # Build message payload
            message = {
                "message": {
                    "token": fcm_token,
                    "notification": {
                        "title": title,
                        "body": body
                    },
                    "data": data or {},
                    "android": {
                        "priority": priority,
                        "notification": {
                            "notification_count": 1,
                            "sound": "default"
                        }
                    },
                    "apns": {
                        "payload": {
                            "aps": {
                                "alert": {
                                    "title": title,
                                    "body": body
                                },
                                "sound": "default",
                                "badge": 1
                            }
                        }
                    }
                }
            }
            
            # Add notification type to data
            if notification_type:
                message["message"]["data"]["type"] = notification_type
                message["message"]["data"]["timestamp"] = datetime.now().isoformat()
            
            # Send to FCM
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.fcm_endpoint,
                    headers=headers,
                    json=message
                )
                response.raise_for_status()
                
                result = response.json()
            
            logger.info(f"Notification sent successfully to token: {fcm_token[:20]}...")
            return {
                "success": True,
                "message_id": result.get("name"),
                "status": "sent"
            }
            
        except httpx.HTTPError as e:
            logger.error(f"FCM HTTP error: {str(e)}")
            return {
                "success": False,
                "error": f"HTTP error: {str(e)}",
                "status": "failed"
            }
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status": "failed"
            }
    
    async def send_multicast_notification(
        self,
        fcm_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        notification_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send push notification to multiple devices.
        
        Args:
            fcm_tokens: List of FCM tokens
            title: Notification title
            body: Notification body
            data: Additional data payload
            notification_type: Type of notification
            
        Returns:
            Dictionary with delivery status for each token
        """
        if not fcm_tokens:
            return {"success": False, "error": "No tokens provided"}
        
        # Send notifications concurrently
        tasks = [
            self.send_notification(
                token,
                title,
                body,
                data,
                notification_type
            )
            for token in fcm_tokens
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate results
        success_count = sum(
            1 for result in results
            if isinstance(result, dict) and result.get("success")
        )
        
        return {
            "success": success_count > 0,
            "total_tokens": len(fcm_tokens),
            "successful": success_count,
            "failed": len(fcm_tokens) - success_count,
            "results": results
        }
    
    async def send_topic_notification(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        notification_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send push notification to a topic.
        
        Args:
            topic: FCM topic name
            title: Notification title
            body: Notification body
            data: Additional data payload
            notification_type: Type of notification
            
        Returns:
            Dictionary with delivery status
        """
        if not self.api_key:
            logger.warning("FCM not configured, skipping topic notification")
            return {"success": False, "error": "FCM not configured"}
        
        try:
            # Build message payload
            message = {
                "message": {
                    "topic": topic,
                    "notification": {
                        "title": title,
                        "body": body
                    },
                    "data": data or {}
                }
            }
            
            # Add notification type to data
            if notification_type:
                message["message"]["data"]["type"] = notification_type
                message["message"]["data"]["timestamp"] = datetime.now().isoformat()
            
            # Send to FCM
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.fcm_endpoint,
                    headers=headers,
                    json=message
                )
                response.raise_for_status()
                
                result = response.json()
            
            logger.info(f"Topic notification sent successfully to topic: {topic}")
            return {
                "success": True,
                "message_id": result.get("name"),
                "topic": topic,
                "status": "sent"
            }
            
        except Exception as e:
            logger.error(f"Error sending topic notification: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status": "failed"
            }
    
    async def send_ride_request_notification(
        self,
        fcm_token: str,
        ride_id: int,
        driver_name: str,
        vehicle_type: str,
        eta_minutes: int
    ) -> Dict[str, Any]:
        """
        Send ride request notification to passenger.
        
        Args:
            fcm_token: Passenger FCM token
            ride_id: Ride ID
            driver_name: Driver name
            vehicle_type: Vehicle type
            eta_minutes: Estimated arrival time
            
        Returns:
            Dictionary with delivery status
        """
        return await self.send_notification(
            fcm_token=fcm_token,
            title="Ride Request Accepted",
            body=f"Driver {driver_name} ({vehicle_type}) will arrive in {eta_minutes} minutes",
            data={
                "ride_id": str(ride_id),
                "driver_name": driver_name,
                "vehicle_type": vehicle_type,
                "eta_minutes": str(eta_minutes)
            },
            notification_type=NotificationType.RIDE_ACCEPTED
        )
    
    async def send_mid_route_consent_notification(
        self,
        fcm_token: str,
        ride_id: int,
        new_passenger_count: int,
        detour_minutes: float
    ) -> Dict[str, Any]:
        """
        Send mid-route consent request notification.
        
        Args:
            fcm_token: Passenger FCM token
            ride_id: Ride ID
            new_passenger_count: Number of new passengers
            detour_minutes: Estimated detour time
            
        Returns:
            Dictionary with delivery status
        """
        return await self.send_notification(
            fcm_token=fcm_token,
            title="Mid-Route Pickup Request",
            body=f"A passenger wants to join your ride. Detour: {detour_minutes:.1f} min",
            data={
                "ride_id": str(ride_id),
                "new_passenger_count": str(new_passenger_count),
                "detour_minutes": str(detour_minutes),
                "action_required": "consent"
            },
            notification_type=NotificationType.MID_ROUTE_CONSENT
        )
    
    async def send_otp_notification(
        self,
        fcm_token: str,
        ride_id: int,
        otp: str,
        expires_in_minutes: int
    ) -> Dict[str, Any]:
        """
        Send OTP notification to passenger.
        
        Args:
            fcm_token: Passenger FCM token
            ride_id: Ride ID
            otp: OTP code
            expires_in_minutes: OTP validity in minutes
            
        Returns:
            Dictionary with delivery status
        """
        return await self.send_notification(
            fcm_token=fcm_token,
            title="Your Ride OTP",
            body=f"Your OTP is: {otp}. Valid for {expires_in_minutes} minutes",
            data={
                "ride_id": str(ride_id),
                "otp": otp,
                "expires_in_minutes": str(expires_in_minutes)
            },
            notification_type=NotificationType.OTP_DELIVERY
        )
    
    async def send_safety_alert_notification(
        self,
        fcm_token: str,
        ride_id: int,
        alert_type: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Send safety alert notification.
        
        Args:
            fcm_token: User FCM token
            ride_id: Ride ID
            alert_type: Type of safety alert
            message: Alert message
            
        Returns:
            Dictionary with delivery status
        """
        return await self.send_notification(
            fcm_token=fcm_token,
            title=f"Safety Alert: {alert_type}",
            body=message,
            data={
                "ride_id": str(ride_id),
                "alert_type": alert_type,
                "urgency": "high"
            },
            notification_type=NotificationType.SAFETY_ALERT,
            priority="high"
        )


class NotificationManager:
    """
    High-level notification manager.
    
    Provides convenience methods for common notification scenarios.
    """
    
    def __init__(self):
        """Initialize notification manager."""
        self.fcm_service = FCMService()
    
    async def notify_ride_accepted(
        self,
        passenger_token: str,
        ride_id: int,
        driver_name: str,
        vehicle_type: str,
        eta_minutes: int
    ) -> Dict[str, Any]:
        """Notify passenger that ride was accepted."""
        return await self.fcm_service.send_ride_request_notification(
            passenger_token,
            ride_id,
            driver_name,
            vehicle_type,
            eta_minutes
        )
    
    async def notify_driver_arrived(
        self,
        passenger_token: str,
        ride_id: int,
        driver_name: str
    ) -> Dict[str, Any]:
        """Notify passenger that driver has arrived."""
        return await self.fcm_service.send_notification(
            fcm_token=passenger_token,
            title="Driver Arrived",
            body=f"Driver {driver_name} has arrived at your pickup location",
            data={
                "ride_id": str(ride_id),
                "driver_name": driver_name
            },
            notification_type=NotificationType.DRIVER_ARRIVED
        )
    
    async def request_mid_route_consent(
        self,
        passenger_tokens: List[str],
        ride_id: int,
        new_passenger_count: int,
        detour_minutes: float
    ) -> Dict[str, Any]:
        """Request consent from existing passengers for mid-route pickup."""
        return await self.fcm_service.send_multicast_notification(
            fcm_tokens=passenger_tokens,
            title="Mid-Route Pickup Request",
            body=f"A passenger wants to join. Detour: {detour_minutes:.1f} min",
            data={
                "ride_id": str(ride_id),
                "new_passenger_count": str(new_passenger_count),
                "detour_minutes": str(detour_minutes),
                "action_required": "consent"
            },
            notification_type=NotificationType.MID_ROUTE_CONSENT
        )
    
    async def deliver_otp(
        self,
        passenger_token: str,
        ride_id: int,
        otp: str
    ) -> Dict[str, Any]:
        """Deliver OTP to passenger after driver liveness verification."""
        return await self.fcm_service.send_otp_notification(
            passenger_token,
            ride_id,
            otp,
            settings.otp_expire_minutes
        )


# Global notification manager instance
notification_manager = NotificationManager()


if __name__ == "__main__":
    import asyncio
    
    async def test_notification_service():
        """Test notification service."""
        print("Testing Notification Service...")
        
        manager = NotificationManager()
        
        # Test basic notification (will fail without API key)
        print("\nTesting basic notification...")
        result = await manager.fcm_service.send_notification(
            fcm_token="test_token",
            title="Test Notification",
            body="This is a test notification"
        )
        print(f"Result: {result}")
        
        print("\nNotification service test completed!")
    
    asyncio.run(test_notification_service())
