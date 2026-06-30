"""Authentication routes for email/password, OAuth, token lifecycle, and recovery."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.rbac import require_organization, require_role
from app.core.security import get_current_user
from app.models.auth import (
    AddOrganizationMemberRequest,
    AuthUser,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    OrganizationMember,
    OAuthStartResponse,
    OAuthSessionExchangeRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordConfirmRequest,
    TokenResponse,
)
from app.services.auth_service import auth_service

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register(payload: RegisterRequest):
    return auth_service.register(payload)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    return auth_service.login(payload)


@router.get("/me", response_model=AuthUser)
async def get_me(user: dict = Depends(get_current_user)):
    return auth_service.get_user_profile(str(user["sub"]))


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshTokenRequest):
    return auth_service.refresh(payload.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(payload: RefreshTokenRequest):
    auth_service.logout(payload.refresh_token)
    return MessageResponse(message="Logged out")


@router.get("/oauth/{provider}/start", response_model=OAuthStartResponse)
async def start_oauth(provider: str):
    url = auth_service.start_oauth(provider)
    return OAuthStartResponse(provider=provider, authorization_url=url)


@router.post("/oauth/session", response_model=TokenResponse)
async def exchange_oauth_session(payload: OAuthSessionExchangeRequest):
    return auth_service.exchange_oauth_session(payload.access_token)


@router.post("/verify-email/resend", response_model=MessageResponse)
async def resend_verification(payload: ResendVerificationRequest):
    auth_service.resend_verification(payload.email)
    return MessageResponse(message="Verification email sent")


@router.post("/password/forgot", response_model=MessageResponse)
async def forgot_password(payload: ForgotPasswordRequest):
    auth_service.forgot_password(payload.email)
    return MessageResponse(message="Password reset email sent")


@router.post("/password/reset", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordConfirmRequest):
    auth_service.confirm_reset_password(
        access_token=payload.access_token,
        refresh_token=payload.refresh_token,
        new_password=payload.new_password,
    )
    return MessageResponse(message="Password reset successful")


@router.get("/organization/members", response_model=list[OrganizationMember])
async def list_organization_members(user: dict = Depends(require_organization)):
    return auth_service.list_organization_members(str(user["organization_id"]))


@router.post("/organization/members", response_model=OrganizationMember)
async def add_organization_member(
    payload: AddOrganizationMemberRequest,
    user: dict = Depends(require_role("admin")),
):
    return auth_service.add_organization_member(
        organization_id=str(user["organization_id"]),
        email=payload.email,
        role=payload.role,
    )
