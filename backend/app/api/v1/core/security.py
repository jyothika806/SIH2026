"""Re-export canonical authenticated-principal dependencies."""

from backend.app.api.core.security import (
    AuthenticatedPrincipal,
    get_authenticated_principal,
    get_current_user,
)

__all__ = [
    "AuthenticatedPrincipal",
    "get_authenticated_principal",
    "get_current_user",
]
