"""Redact high-risk identifiers and encoded image payloads from log messages."""

import logging
import re


_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")
_LICENCE = re.compile(r"\b[A-Z]{2}[- ]?\d{2}[- ]?[A-Z0-9 -]{6,16}\b", re.IGNORECASE)
_OTP = re.compile(
    r"\b((?:otp|verification(?:\s+code)?|one[- ]time(?:\s+password)?|code)"
    r"\s*(?:is\s*)?[:=]?\s*)\d{6}\b",
    re.IGNORECASE,
)
_BASE64_IMAGE = re.compile(
    r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=]{64,}|(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{512,}={0,2}"
)


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        message = _BASE64_IMAGE.sub("[REDACTED_IMAGE]", message)
        message = _LICENCE.sub("[REDACTED_LICENCE]", message)
        message = _PHONE.sub("[REDACTED_PHONE]", message)
        message = _OTP.sub(r"\1[REDACTED_OTP]", message)
        record.msg = message
        record.args = ()
        return True


def install_sensitive_data_filter() -> None:
    root = logging.getLogger()
    if not any(isinstance(item, SensitiveDataFilter) for item in root.filters):
        root.addFilter(SensitiveDataFilter())
    for handler in root.handlers:
        if not any(isinstance(item, SensitiveDataFilter) for item in handler.filters):
            handler.addFilter(SensitiveDataFilter())
