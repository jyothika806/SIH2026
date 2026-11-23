"""Compatibility re-exports for the single application settings object."""

from backend.app.api.v1.core.config import Settings, get_settings, settings

__all__ = ["Settings", "get_settings", "settings"]
