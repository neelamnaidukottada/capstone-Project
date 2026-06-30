"""Role-based access checks for request handlers."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user

ROLE_ORDER = {
    "viewer": 10,
    "manager": 20,
    "admin": 30,
}


def require_role(minimum_role: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Require the authenticated user to have at least minimum_role."""

    def _checker(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        role = str(user.get("role", "viewer"))
        if ROLE_ORDER.get(role, 0) < ROLE_ORDER.get(minimum_role, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role '{minimum_role}'",
            )
        return user

    return _checker


def require_organization(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    org_id = user.get("organization_id")
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context is required",
        )
    return user
