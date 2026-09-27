"""
Twilio SMS Gateway Integration for OTP Delivery

This module implements:
- Twilio SMS API integration
- OTP generation and delivery
- Delivery status tracking
- Fallback SMS service

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

import httpx
import random
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import secrets

from app.core.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()


class OTPService:
    """
    OTP generation and validation service.
    
    Provides methods for:
    - Generating secure OTP codes
    - Validating OTP codes
    - Managing OTP expiration
    """
    
    def __init__(self):
        """Initialize OTP service."""
        self.otp_length = 6
        self.otp_expire_minutes = settings.otp_expire_minutes
    
    def generate_otp(self) -> str:
        """
        Generate a secure 6-digit OTP code.
        
        Returns:
            6-digit OTP code as string
        """
        # Generate cryptographically secure random OTP
        otp = ''.join([str(random.randint(0, 9)) for _ in range(self.otp_length)])
        return otp
    
    def generate_secure_token(self) -> str:
        """
        Generate a secure token for authentication.
        
        Returns:
            Secure token string
        """
        return secrets.token_urlsafe(32)
    
    def calculate_expiry(self) -> datetime:
        """
        Calculate OTP expiration time.
        
        Returns:
            Expiration datetime
        """
        return datetime.now() + timedelta(minutes=self.otp_expire_minutes)
    
    def is_expired(self, expires_at: datetime) -> bool:
        """
        Check if OTP has expired.
        
        Args:
            expires_at: Expiration datetime
            
        Returns:
            True if expired, False otherwise
        """
        return datetime.now() > expires_at
    
    def validate_otp(self, provided_otp: str, expected_otp: str) -> bool:
        """
        Validate OTP code.
        
        Args:
            provided_otp: OTP provided by user
            expected_otp: Expected OTP code
            
        Returns:
            True if valid, False otherwise
        """
        return provided_otp == expected_otp and len(provided_otp) == self.otp_length


class TwilioService:
    """
    Twilio SMS service for OTP delivery.
    
    Provides methods for:
    - Sending SMS via Twilio API
    - Delivery status tracking
    - OTP SMS formatting
    """
    
    def __init__(self):
        """Initialize Twilio service."""
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.phone_number = settings.twilio_phone_number
        self.api_base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"
        
        if self.account_sid and self.auth_token:
            logger.info("Twilio service initialized")
        else:
            logger.warning("Twilio credentials not configured, SMS will be disabled")
    
    async def send_sms(
        self,
        to_phone: str,
        message: str
    ) -> Dict[str, any]:
        """
        Send SMS via Twilio API.
        
        Args:
            to_phone: Recipient phone number (with country code)
            message: SMS message content
            
        Returns:
            Dictionary with delivery status
        """
        if not self.account_sid or not self.auth_token:
            logger.warning("Twilio not configured, skipping SMS")
            return {
                "success": False,
                "error": "Twilio not configured",
                "status": "skipped"
            }
        
        try:
            # Build request URL
            url = f"{self.api_base_url}/Messages.json"
            
            # Prepare request data
            data = {
                "From": self.phone_number,
                "To": to_phone,
                "Body": message
            }
            
            # Send request
            auth = (self.account_sid, self.auth_token)
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    url,
                    auth=auth,
                    data=data
                )
                response.raise_for_status()
                
                result = response.json()
            
            logger.info(f"SMS sent successfully to {to_phone}")
            return {
                "success": True,
                "message_sid": result.get("sid"),
                "status": result.get("status"),
                "to": result.get("to"),
                "from": result.get("from")
            }
            
        except httpx.HTTPError as e:
            logger.error(f"Twilio HTTP error: {str(e)}")
            return {
                "success": False,
                "error": f"HTTP error: {str(e)}",
                "status": "failed"
            }
        except Exception as e:
            logger.error(f"Error sending SMS: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status": "failed"
            }
    
    async def send_otp_sms(
        self,
        to_phone: str,
        otp: str,
        app_name: str = "OptimalRide"
    ) -> Dict[str, any]:
        """
        Send OTP via SMS.
        
        Args:
            to_phone: Recipient phone number
            otp: OTP code
            app_name: Application name for message
            
        Returns:
            Dictionary with delivery status
        """
        message = (
            f"Your {app_name} verification code is: {otp}\n"
            f"Valid for {settings.otp_expire_minutes} minutes.\n"
            f"Do not share this code with anyone."
        )
        
        return await self.send_sms(to_phone, message)
    
    async def send_ride_notification_sms(
        self,
        to_phone: str,
        message: str
    ) -> Dict[str, any]:
        """
        Send ride notification via SMS.
        
        Args:
            to_phone: Recipient phone number
            message: Notification message
            
        Returns:
            Dictionary with delivery status
        """
        return await self.send_sms(to_phone, message)
    
    async def check_delivery_status(
        self,
        message_sid: str
    ) -> Dict[str, any]:
        """
        Check SMS delivery status.
        
        Args:
            message_sid: Twilio message SID
            
        Returns:
            Dictionary with delivery status
        """
        if not self.account_sid or not self.auth_token:
            return {
                "success": False,
                "error": "Twilio not configured"
            }
        
        try:
            url = f"{self.api_base_url}/Messages/{message_sid}.json"
            
            auth = (self.account_sid, self.auth_token)
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, auth=auth)
                response.raise_for_status()
                
                result = response.json()
            
            return {
                "success": True,
                "status": result.get("status"),
                "error_code": result.get("error_code"),
                "error_message": result.get("error_message")
            }
            
        except Exception as e:
            logger.error(f"Error checking delivery status: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


class SMSService:
    """
    High-level SMS service combining OTP generation and Twilio delivery.
    
    Provides convenience methods for:
    - OTP generation and delivery
    - SMS notification sending
    - Delivery status management
    """
    
    def __init__(self):
        """Initialize SMS service."""
        self.otp_service = OTPService()
        self.twilio_service = TwilioService()
    
    async def send_otp(
        self,
        phone: str,
        user_id: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Generate and send OTP to phone number.
        
        Args:
            phone: Phone number
            user_id: Optional user ID for logging
            
        Returns:
            Dictionary with OTP and delivery status
        """
        # Generate OTP
        otp = self.otp_service.generate_otp()
        expires_at = self.otp_service.calculate_expiry()
        
        # Send OTP via SMS
        delivery_result = await self.twilio_service.send_otp_sms(phone, otp)
        
        logger.info(
            f"OTP sent to {phone} for user {user_id or 'unknown'}, "
            f"delivery: {delivery_result.get('status', 'unknown')}"
        )
        
        return {
            "success": delivery_result.get("success", False),
            "otp": otp,
            "expires_at": expires_at.isoformat(),
            "delivery_status": delivery_result.get("status"),
            "message_sid": delivery_result.get("message_sid")
        }
    
    async def validate_otp(
        self,
        provided_otp: str,
        expected_otp: str,
        expires_at: datetime
    ) -> Dict[str, any]:
        """
        Validate OTP code.
        
        Args:
            provided_otp: OTP provided by user
            expected_otp: Expected OTP code
            expires_at: OTP expiration time
            
        Returns:
            Dictionary with validation result
        """
        # Check expiration
        if self.otp_service.is_expired(expires_at):
            return {
                "success": False,
                "error": "OTP has expired",
                "valid": False
            }
        
        # Validate OTP
        is_valid = self.otp_service.validate_otp(provided_otp, expected_otp)
        
        return {
            "success": is_valid,
            "valid": is_valid,
            "error": None if is_valid else "Invalid OTP"
        }
    
    async def send_notification(
        self,
        phone: str,
        message: str
    ) -> Dict[str, any]:
        """
        Send notification SMS.
        
        Args:
            phone: Phone number
            message: Notification message
            
        Returns:
            Dictionary with delivery status
        """
        return await self.twilio_service.send_ride_notification_sms(phone, message)
    
    async def send_safety_alert(
        self,
        phone: str,
        alert_type: str,
        message: str
    ) -> Dict[str, any]:
        """
        Send safety alert SMS.
        
        Args:
            phone: Phone number
            alert_type: Type of safety alert
            message: Alert message
            
        Returns:
            Dictionary with delivery status
        """
        full_message = f"[SAFETY ALERT - {alert_type}]\n{message}"
        return await self.twilio_service.send_ride_notification_sms(phone, full_message)


# Global SMS service instance
sms_service = SMSService()


if __name__ == "__main__":
    import asyncio
    
    async def test_sms_service():
        """Test SMS service."""
        print("Testing SMS Service...")
        
        service = SMSService()
        
        # Test OTP generation
        print("\nTesting OTP generation...")
        otp = service.otp_service.generate_otp()
        print(f"Generated OTP: {otp}")
        
        # Test OTP validation
        print("\nTesting OTP validation...")
        valid = service.otp_service.validate_otp(otp, otp)
        print(f"Valid OTP: {valid}")
        
        invalid = service.otp_service.validate_otp("000000", otp)
        print(f"Invalid OTP: {invalid}")
        
        # Test SMS sending (will fail without Twilio credentials)
        print("\nTesting SMS sending...")
        result = await service.send_otp("+1234567890")
        print(f"Result: {result}")
        
        print("\nSMS service test completed!")
    
    asyncio.run(test_sms_service())
