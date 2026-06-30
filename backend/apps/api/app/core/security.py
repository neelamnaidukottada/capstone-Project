"""JWT authentication middleware and helpers."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

ALGORITHM = "HS256"


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Attach decoded JWT claims to request.state.user for protected paths."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        open_paths = {
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/api/v1/auth/logout",
            "/api/v1/auth/oauth/google/start",
            "/api/v1/auth/oauth/github/start",
            "/api/v1/auth/oauth/session",
            "/api/v1/auth/verify-email/resend",
            "/api/v1/auth/password/forgot",
            "/api/v1/auth/password/reset",
        }

        try:
            if any(path.startswith(prefix) for prefix in open_paths):
                return await call_next(request)

            if path.startswith("/api/v1"):
                auth_header = request.headers.get("Authorization", "")
                if not auth_header.startswith("Bearer "):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Missing bearer token",
                    )

                token = auth_header.split(" ", 1)[1]
                request.state.user = decode_token(token, expected_type="access")

            return await call_next(request)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": {"type": "http_error", "message": exc.detail}},
            )
        except Exception:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": {"type": "internal_error", "message": "An unexpected error occurred"}},
            )


def decode_token(token: str, *, expected_type: str = "access") -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.API_SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject is missing",
        )

    token_type = payload.get("token_type")
    if token_type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token type: expected {expected_type}",
        )

    return payload


def get_current_user(request: Request) -> dict[str, Any]:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user
