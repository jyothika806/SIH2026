"""SMS delivery through the configured real provider; no mock success path."""

import logging
import ipaddress
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.app.api.v1.core.config import get_settings
from backend.app.services.otp_service import mask_phone

logger = logging.getLogger(__name__)
settings = get_settings()


class TwilioService:
    def __init__(self) -> None:
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.phone_number = settings.twilio_phone_number

    async def send_sms(self, to_phone: str, message: str) -> dict[str, Any]:
        if not self.account_sid or not self.auth_token or not self.phone_number:
            logger.warning("Twilio SMS unavailable for %s: provider is not configured", mask_phone(to_phone))
            return {"success": False, "status": "unavailable"}

        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{self.account_sid}/Messages.json"
        )
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    url,
                    auth=(self.account_sid, self.auth_token),
                    data={"From": self.phone_number, "To": to_phone, "Body": message},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as error:
            logger.error("Twilio request failed (%s)", type(error).__name__)
            return {"success": False, "status": "failed"}
        except ValueError:
            logger.error("Twilio returned an invalid response")
            return {"success": False, "status": "failed"}

        logger.info("SMS delivery accepted for %s", mask_phone(to_phone))
        return {
            "success": True,
            "message_sid": payload.get("sid"),
            "status": payload.get("status", "accepted"),
        }

    async def send_otp_sms(
        self,
        to_phone: str,
        otp: str,
        app_name: str = "OptimalRide",
    ) -> dict[str, Any]:
        message = (
            f"Your {app_name} verification code is: {otp}\n"
            f"Valid for {settings.otp_expire_minutes} minutes.\n"
            "Do not share this code with anyone."
        )
        return await self.send_sms(to_phone, message)

    async def send_ride_notification_sms(
        self, to_phone: str, message: str
    ) -> dict[str, Any]:
        return await self.send_sms(to_phone, message)


class SMSService:
    def __init__(self) -> None:
        self.twilio_service = TwilioService()

    async def send_otp(
        self, phone: str, otp: str, user_id: int | None = None
    ) -> dict[str, Any]:
        if settings.environment.lower() == "test" and settings.test_sms_sink_url:
            result = await self._send_to_test_sink(phone, otp)
            logger.info(
                "OTP test delivery status=%s phone=%s user_id=%s",
                result.get("status", "unknown"),
                mask_phone(phone),
                user_id or "unknown",
            )
            return {
                "success": result.get("success", False),
                "delivery_status": result.get("status"),
                "message_sid": None,
            }

        result = await self.twilio_service.send_otp_sms(phone, otp)
        logger.info(
            "OTP delivery status=%s phone=%s user_id=%s",
            result.get("status", "unknown"),
            mask_phone(phone),
            user_id or "unknown",
        )
        return {
            "success": result.get("success", False),
            "delivery_status": result.get("status"),
            "message_sid": result.get("message_sid"),
        }

    async def _send_to_test_sink(self, phone: str, otp: str) -> dict[str, Any]:
        url = settings.test_sms_sink_url
        parsed = urlparse(url or "")
        try:
            address = ipaddress.ip_address(parsed.hostname or "")
            is_loopback = address.is_loopback
        except ValueError:
            is_loopback = parsed.hostname == "localhost"
        if parsed.scheme != "http" or not is_loopback or parsed.username or parsed.password:
            logger.error("Test SMS sink must use an unauthenticated loopback HTTP address")
            return {"success": False, "status": "unavailable"}

        message = (
            f"Your OptimalRide verification code is: {otp}\n"
            f"Valid for {settings.otp_expire_minutes} minutes.\n"
            "Do not share this code with anyone."
        )
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    url,
                    json={"phone": phone, "message": message},
                )
                response.raise_for_status()
        except httpx.HTTPError as error:
            logger.error("Test SMS sink failed (%s)", type(error).__name__)
            return {"success": False, "status": "failed"}
        return {"success": True, "status": "sent"}

    async def send_notification(self, phone: str, message: str) -> dict[str, Any]:
        return await self.twilio_service.send_ride_notification_sms(phone, message)

    async def send_safety_alert(
        self, phone: str, alert_type: str, message: str
    ) -> dict[str, Any]:
        return await self.twilio_service.send_ride_notification_sms(
            phone, f"[SAFETY ALERT - {alert_type}]\n{message}"
        )


sms_service = SMSService()
