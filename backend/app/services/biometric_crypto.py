"""Authenticated encryption helpers for driver licence fields and embeddings."""

from cryptography.fernet import Fernet

from backend.app.api.v1.core.config import get_settings


def _fernet() -> Fernet:
    key = get_settings().fernet_key
    if not key:
        raise RuntimeError("FERNET_KEY is required for sensitive-data encryption")
    return Fernet(key.encode("ascii"))


def encrypt_bytes(value: bytes) -> bytes:
    return _fernet().encrypt(value)


def decrypt_bytes(value: bytes) -> bytes:
    return _fernet().decrypt(value)


def encrypt_text(value: str) -> str:
    return encrypt_bytes(value.encode("utf-8")).decode("ascii")


def decrypt_text(value: str) -> str:
    return decrypt_bytes(value.encode("ascii")).decode("utf-8")
