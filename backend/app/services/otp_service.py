"""OTP generation and keyed hashing; plaintext OTPs never enter persistence."""

import hashlib
import hmac
import secrets

from backend.app.api.v1.core.config import get_settings

settings = get_settings()


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(code: str, purpose: str, subject: str) -> str:
    key = settings.otp_hmac_key
    if not key:
        raise RuntimeError("OTP_HMAC_KEY is required to create or verify OTPs")
    message = f"{purpose}:{subject}:{code}".encode("utf-8")
    return hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_otp(code: str, expected_hash: str | None, purpose: str, subject: str) -> bool:
    if expected_hash is None or len(code) != 6 or not code.isdigit():
        return False
    candidate = hash_otp(code, purpose, subject)
    return hmac.compare_digest(candidate, expected_hash)


def mask_phone(phone: str) -> str:
    digits = "".join(character for character in phone if character.isdigit())
    return f"***{digits[-4:]}" if len(digits) >= 4 else "***"
