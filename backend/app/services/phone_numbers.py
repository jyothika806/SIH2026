"""Canonical phone-number validation and E.164 formatting."""

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat


def normalize_phone(phone: str, default_region: str = "IN") -> str:
    try:
        parsed = phonenumbers.parse(phone, default_region)
    except NumberParseException as error:
        raise ValueError("Phone number is invalid") from error
    if not phonenumbers.is_valid_number(parsed):
        raise ValueError("Phone number is invalid")
    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
