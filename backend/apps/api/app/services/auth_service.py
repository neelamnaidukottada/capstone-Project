"""Authentication service integrating Supabase Auth + local JWT + org RBAC."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from supabase_auth.errors import AuthApiError

from app.core.config import settings
from app.core.logging import get_logger
from app.core.supabase_client import get_supabase_admin_client, get_supabase_anon_client
from app.models.auth import AuthUser, LoginRequest, OrganizationMember, RegisterRequest, TokenResponse

logger = get_logger(__name__)
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS)


class AuthService:
    def __init__(self) -> None:
        self._admin = None
        self._anon = None

    @property
    def admin(self):
        if self._admin is None:
            self._admin = get_supabase_admin_client()
        return self._admin

    @property
    def anon(self):
        if self._anon is None:
            self._anon = get_supabase_anon_client()
        return self._anon

    def hash_password(self, plain_password: str) -> str:
        return pwd_context.hash(plain_password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def _jwt_exp(self, delta: timedelta) -> datetime:
        return datetime.now(UTC) + delta

    def _encode_access_token(self, *, user_id: str, role: str, organization_id: str, email: str) -> str:
        payload = {
            "sub": user_id,
            "role": role,
            "organization_id": organization_id,
            "email": email,
            "token_type": "access",
            "exp": self._jwt_exp(timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)),
            "iat": datetime.now(UTC),
        }
        return jwt.encode(payload, settings.API_SECRET_KEY, algorithm=ALGORITHM)

    def _encode_refresh_token(self, *, user_id: str, organization_id: str) -> str:
        payload = {
            "sub": user_id,
            "organization_id": organization_id,
            "token_type": "refresh",
            "jti": token_urlsafe(24),
            "exp": self._jwt_exp(timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)),
            "iat": datetime.now(UTC),
        }
        return jwt.encode(payload, settings.API_SECRET_KEY, algorithm=ALGORITHM)

    def _ensure_organization(self, *, user_id: str, organization_name: str) -> tuple[str, str]:
        base_name = organization_name.strip() or "My Organization"
        create_error: Exception | None = None

        for attempt in range(3):
            candidate_name = base_name if attempt == 0 else f"{base_name}-{token_urlsafe(3).lower()}"
            try:
                org_row = (
                    self.admin.table("app_organizations")
                    .insert({"name": candidate_name, "owner_user_id": user_id})
                    .execute()
                )
                if not org_row.data:
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to create organization")

                org = org_row.data[0]
                org_id = str(org["id"])
                org_name = str(org["name"])

                self.admin.table("organization_memberships").upsert(
                    {
                        "organization_id": org_id,
                        "user_id": user_id,
                        "role": "admin",
                    },
                    on_conflict="organization_id,user_id",
                ).execute()

                return org_id, org_name
            except Exception as exc:
                create_error = exc
                message = str(exc).lower()
                # app_organizations.slug is generated from name and must be unique.
                if "duplicate key" in message and "slug" in message and attempt < 2:
                    continue
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to create organization") from exc

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to create organization") from create_error

    def _get_user_and_membership(self, user_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        user_rows = self.admin.table("app_users").select("*").eq("id", user_id).limit(1).execute()
        if not user_rows.data:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User profile is not configured")
        user = user_rows.data[0]

        memberships = (
            self.admin.table("organization_memberships")
            .select("organization_id, role, app_organizations(name)")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if not memberships.data:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active organization membership")

        return user, memberships.data[0]

    def _build_user(self, user_row: dict[str, Any], membership_row: dict[str, Any]) -> AuthUser:
        org_id = str(membership_row["organization_id"])
        role = str(membership_row.get("role") or "viewer")
        org_info = membership_row.get("app_organizations")
        organization_name = org_info.get("name") if isinstance(org_info, dict) else None
        return AuthUser(
            id=str(user_row["id"]),
            email=str(user_row["email"]),
            full_name=str(user_row.get("full_name") or ""),
            role=role,  # type: ignore[arg-type]
            organization_id=org_id,
            organization_name=organization_name,
            email_verified=bool(user_row.get("email_verified", False)),
        )

    def _issue_tokens(self, user: AuthUser) -> TokenResponse:
        access_token = self._encode_access_token(
            user_id=user.id,
            role=user.role,
            organization_id=user.organization_id,
            email=user.email,
        )
        refresh_token = self._encode_refresh_token(user_id=user.id, organization_id=user.organization_id)
        refresh_hash = self.hash_password(refresh_token)

        self.admin.table("refresh_tokens").insert(
            {
                "id": str(uuid4()),
                "user_id": user.id,
                "organization_id": user.organization_id,
                "token_hash": refresh_hash,
                "expires_at": self._jwt_exp(timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)).isoformat(),
                "revoked": False,
            }
        ).execute()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user,
        )

    def get_user_profile(self, user_id: str) -> AuthUser:
        user_row, membership_row = self._get_user_and_membership(user_id)
        return self._build_user(user_row, membership_row)

    def register(self, payload: RegisterRequest) -> TokenResponse:
        normalized_email = payload.email.strip().lower()
        logger.info("register_attempt", email=normalized_email, organization_name=payload.organization_name)
        
        try:
            try:
                existing = self.admin.table("app_users").select("id").eq("email", normalized_email).limit(1).execute()
            except Exception as conn_exc:
                # Handle network/connection errors
                error_msg = str(conn_exc).lower()
                logger.error(
                    "register_supabase_connection_error",
                    email=normalized_email,
                    error=str(conn_exc),
                    error_type=type(conn_exc).__name__,
                )
                
                # Check for DNS/network errors
                if "getaddrinfo failed" in error_msg or "11001" in error_msg:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Database service is unavailable. Please check: 1) Internet connection 2) Firewall settings 3) SUPABASE_URL in .env file",
                    ) from conn_exc
                elif "connection refused" in error_msg or "refused" in error_msg:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Cannot connect to database. Please verify SUPABASE_URL and credentials.",
                    ) from conn_exc
                else:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"Database connection error: {str(conn_exc)}",
                    ) from conn_exc
            
            if existing.data:
                logger.warning("register_duplicate_email", email=normalized_email)
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already exists. Please log in.")

            sign_up_user = None
            try:
                logger.info("register_supabase_signup", email=normalized_email)
                sign_up = self.anon.auth.sign_up(
                    {
                        "email": normalized_email,
                        "password": payload.password,
                        "options": {
                            "data": {"full_name": payload.full_name},
                            "email_redirect_to": f"{settings.FRONTEND_URL}/auth/verify",
                        },
                    }
                )
                sign_up_user = getattr(sign_up, "user", None)
            except AuthApiError as exc:
                message = str(exc)
                message_lower = message.lower()
                logger.warning("register_auth_api_error", email=normalized_email, error=message)
                if "already registered" in message_lower or "already exists" in message_lower:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already exists. Please log in.") from exc
                if "email rate limit exceeded" in message.lower():
                    # Dev fallback: create the auth user via service-role admin API, then continue normally.
                    if settings.ENVIRONMENT == "development" and settings.SUPABASE_SERVICE_ROLE_KEY:
                        try:
                            logger.info("register_admin_fallback_create_user", email=normalized_email)
                            admin_created = self.admin.auth.admin.create_user(
                                {
                                    "email": normalized_email,
                                    "password": payload.password,
                                    "email_confirm": True,
                                    "user_metadata": {"full_name": payload.full_name},
                                }
                            )
                            sign_up_user = getattr(admin_created, "user", None)
                        except Exception as admin_exc:
                            logger.exception(
                                "register_rate_limit_admin_fallback_failed",
                                email=normalized_email,
                                error=str(admin_exc),
                            )
                            raise HTTPException(
                                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Email rate limit exceeded. Please try again in a few minutes.",
                            ) from admin_exc
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Email rate limit exceeded. Please try again in a few minutes.",
                        ) from exc
                else:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

            auth_user = sign_up_user
            if not auth_user or not getattr(auth_user, "id", None):
                logger.error("register_no_auth_user", email=normalized_email)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to register user")

            user_id = str(auth_user.id)
            logger.info("register_auth_user_created", user_id=user_id, email=normalized_email)
            
            try:
                logger.info("register_ensure_organization", user_id=user_id, organization_name=payload.organization_name)
                org_id, _org_name = self._ensure_organization(user_id=user_id, organization_name=payload.organization_name)
                logger.info("register_organization_created", user_id=user_id, org_id=org_id, org_name=_org_name)

                logger.info("register_upsert_app_user", user_id=user_id, email=normalized_email)
                app_user_result = self.admin.table("app_users").upsert(
                    {
                        "id": user_id,
                        "email": normalized_email,
                        "full_name": payload.full_name,
                        "organization_id": org_id,
                        "email_verified": bool(getattr(auth_user, "email_confirmed_at", None)),
                        "password_hash": self.hash_password(payload.password),
                        "auth_provider": "email",
                    },
                    on_conflict="id",
                ).execute()
                
                if not app_user_result.data:
                    logger.error("register_upsert_failed", user_id=user_id, email=normalized_email)
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save user profile")

                logger.info("register_get_user_membership", user_id=user_id)
                user_row, membership_row = self._get_user_and_membership(user_id)
                user = self._build_user(user_row, membership_row)
                logger.info("register_success", user_id=user_id, organization_id=user.organization_id)
                return self._issue_tokens(user)
            except HTTPException:
                raise
            except Exception as exc:
                logger.exception("register_profile_setup_failed", user_id=user_id, error=str(exc))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Unable to finish account setup. Please try a different organization name.",
                ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("register_unexpected_error", email=normalized_email, error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred during registration.",
            ) from exc

    def exchange_oauth_session(self, supabase_access_token: str) -> TokenResponse:
        try:
            user_res = self.anon.auth.get_user(supabase_access_token)
        except AuthApiError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Supabase session") from exc
        auth_user = getattr(user_res, "user", None)
        if not auth_user or not getattr(auth_user, "id", None) or not getattr(auth_user, "email", None):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Supabase session")

        user_id = str(auth_user.id)
        email = str(auth_user.email)
        full_name = ""
        user_metadata = getattr(auth_user, "user_metadata", None) or {}
        if isinstance(user_metadata, dict):
            full_name = str(user_metadata.get("full_name") or "")

        existing_user = self.admin.table("app_users").select("id").eq("id", user_id).limit(1).execute()
        if not existing_user.data:
            org_id, _org_name = self._ensure_organization(
                user_id=user_id,
                organization_name=(full_name and f"{full_name}'s Organization") or "Personal Organization",
            )
            self.admin.table("app_users").insert(
                {
                    "id": user_id,
                    "email": email,
                    "full_name": full_name,
                    "organization_id": org_id,
                    "email_verified": bool(getattr(auth_user, "email_confirmed_at", None)),
                    "auth_provider": "oauth",
                }
            ).execute()
        else:
            self.admin.table("app_users").update(
                {
                    "email": email,
                    "full_name": full_name,
                    "email_verified": bool(getattr(auth_user, "email_confirmed_at", None)),
                    "last_login_at": datetime.now(UTC).isoformat(),
                }
            ).eq("id", user_id).execute()

        user_row, membership_row = self._get_user_and_membership(user_id)
        user = self._build_user(user_row, membership_row)
        return self._issue_tokens(user)

    def login(self, payload: LoginRequest) -> TokenResponse:
        try:
            auth_res = self.anon.auth.sign_in_with_password({"email": payload.email, "password": payload.password})
        except AuthApiError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials") from exc
        auth_user = getattr(auth_res, "user", None)
        if not auth_user or not getattr(auth_user, "id", None):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        user_id = str(auth_user.id)
        user_row, membership_row = self._get_user_and_membership(user_id)

        stored_hash = str(user_row.get("password_hash") or "")
        if stored_hash and not self.verify_password(payload.password, stored_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        self.admin.table("app_users").update(
            {"last_login_at": datetime.now(UTC).isoformat(), "email_verified": bool(getattr(auth_user, "email_confirmed_at", None))}
        ).eq("id", user_id).execute()

        user = self._build_user(user_row, membership_row)
        return self._issue_tokens(user)

    def refresh(self, refresh_token: str) -> TokenResponse:
        """Refresh access token using a valid refresh token."""
        from app.core.security import decode_token

        try:
            claims = decode_token(refresh_token, expected_type="refresh")
            user_id = str(claims["sub"])

            token_rows = (
                self.admin.table("refresh_tokens")
                .select("*")
                .eq("user_id", user_id)
                .eq("revoked", False)
                .order("created_at", desc=True)
                .limit(20)
                .execute()
            )

            matched_token_id = None
            now = datetime.now(UTC)
            for row in token_rows.data or []:
                expires_at = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
                if expires_at < now:
                    continue
                if self.verify_password(refresh_token, str(row["token_hash"])):
                    matched_token_id = row["id"]
                    break

            if not matched_token_id:
                logger.warning("refresh_token_not_found", user_id=user_id)
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

            self.admin.table("refresh_tokens").update({"revoked": True}).eq("id", matched_token_id).execute()

            user_row, membership_row = self._get_user_and_membership(user_id)
            user = self._build_user(user_row, membership_row)
            logger.info("token_refreshed", user_id=user_id)
            return self._issue_tokens(user)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("refresh_token_failed", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to refresh token",
            ) from exc

    def logout(self, refresh_token: str) -> None:
        from app.core.security import decode_token

        claims = decode_token(refresh_token, expected_type="refresh")
        user_id = str(claims["sub"])
        self.admin.table("refresh_tokens").update({"revoked": True}).eq("user_id", user_id).execute()

    def start_oauth(self, provider: str) -> str:
        if provider not in {"google", "github"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported OAuth provider")

        oauth = self.anon.auth.sign_in_with_oauth(
            {
                "provider": provider,
                "options": {
                    "redirect_to": settings.SUPABASE_AUTH_REDIRECT_URL,
                },
            }
        )
        url = ""
        data = getattr(oauth, "data", None)
        if isinstance(data, dict):
            url = str(data.get("url") or "")
        if not url:
            url = str(getattr(oauth, "url", ""))

        if not url:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create OAuth URL")

        return url

    def resend_verification(self, email: str) -> None:
        self.anon.auth.resend({"type": "signup", "email": email, "options": {"email_redirect_to": f"{settings.FRONTEND_URL}/auth/verify"}})

    def forgot_password(self, email: str) -> None:
        """Send a password reset email via Supabase."""
        try:
            # Supabase Python SDK v2.x uses reset_password_for_email
            self.anon.auth.reset_password_for_email(
                email,
                {
                    "redirect_to": f"{settings.FRONTEND_URL}/auth/reset",
                },
            )
        except AttributeError:
            # Fallback for older SDK versions
            self.anon.auth.reset_password_email(
                email,
                {
                    "redirect_to": f"{settings.FRONTEND_URL}/auth/reset",
                },
            )
        except Exception as exc:
            logger.exception("forgot_password_failed", email=email, error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send password reset email: {str(exc)}",
            ) from exc

    def confirm_reset_password(self, *, access_token: str, refresh_token: str, new_password: str) -> None:
        """Confirm password reset with tokens from Supabase email link."""
        try:
            # Decode the JWT token without verification to extract user_id
            try:
                # jwt.decode requires a key even with verify_signature=False
                # Use empty string as key since we're not verifying
                payload = jwt.decode(
                    access_token,
                    key="",
                    algorithms=["HS256", "HS512", "none"],
                    options={"verify_signature": False}
                )
                user_id = payload.get("sub")
            except Exception as decode_err:
                logger.warning("jwt_decode_failed", error=str(decode_err), access_token_sample=access_token[:50])
                raise ValueError("Invalid access token") from decode_err
            
            if not user_id:
                raise ValueError("Invalid token: missing user_id")

            # Update the password_hash in our app_users table
            # For production, you'd also want to update it in Supabase Auth directly
            result = self.admin.table("app_users").update(
                {"password_hash": self.hash_password(new_password)}
            ).eq("id", user_id).execute()
            
            if not result.data:
                logger.warning("password_update_no_rows", user_id=user_id)
                raise ValueError(f"User {user_id} not found")
            
            logger.info("password_reset_success", user_id=user_id)
        except Exception as exc:
            logger.exception("confirm_reset_password_failed", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to reset password: {str(exc)}",
            ) from exc

    def list_organization_members(self, organization_id: str) -> list[OrganizationMember]:
        rows = (
            self.admin.table("organization_memberships")
            .select("user_id, role, app_users(email, full_name)")
            .eq("organization_id", organization_id)
            .eq("is_active", True)
            .execute()
        )

        members: list[OrganizationMember] = []
        for row in rows.data or []:
            user = row.get("app_users") or {}
            members.append(
                OrganizationMember(
                    user_id=str(row.get("user_id")),
                    email=str(user.get("email") or "unknown@example.com"),
                    full_name=str(user.get("full_name") or ""),
                    role=str(row.get("role") or "viewer"),  # type: ignore[arg-type]
                )
            )
        return members

    def add_organization_member(self, *, organization_id: str, email: str, role: str) -> OrganizationMember:
        user_rows = self.admin.table("app_users").select("id, email, full_name").eq("email", email).limit(1).execute()
        if not user_rows.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user = user_rows.data[0]
        self.admin.table("organization_memberships").upsert(
            {
                "organization_id": organization_id,
                "user_id": user["id"],
                "role": role,
                "is_active": True,
            },
            on_conflict="organization_id,user_id",
        ).execute()

        return OrganizationMember(
            user_id=str(user["id"]),
            email=str(user["email"]),
            full_name=str(user.get("full_name") or ""),
            role=role,  # type: ignore[arg-type]
        )


auth_service = AuthService()
