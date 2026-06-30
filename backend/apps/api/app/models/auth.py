"""Authentication and authorization API models."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=120)
    organization_name: str = Field(..., min_length=2, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=20)


class OAuthStartResponse(BaseModel):
    provider: Literal["google", "github"]
    authorization_url: str


class OAuthSessionExchangeRequest(BaseModel):
    access_token: str = Field(..., min_length=20)


class AuthUser(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: Literal["admin", "manager", "viewer"]
    organization_id: str
    organization_name: str | None = None
    email_verified: bool = False


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: AuthUser


class MessageResponse(BaseModel):
    message: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordConfirmRequest(BaseModel):
    access_token: str
    refresh_token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class OrganizationMember(BaseModel):
    user_id: str
    email: EmailStr
    full_name: str
    role: Literal["admin", "manager", "viewer"]


class AddOrganizationMemberRequest(BaseModel):
    email: EmailStr
    role: Literal["admin", "manager", "viewer"] = "viewer"
