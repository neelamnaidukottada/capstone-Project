"""Unit tests for authentication service."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.models.auth import AuthUser, RegisterRequest, TokenResponse
from app.services.auth_service import AuthService


@pytest.fixture
def auth_service():
    """Create an auth service instance."""
    return AuthService()


@pytest.fixture
def mock_supabase_admin(monkeypatch):
    """Mock Supabase admin client."""
    mock = MagicMock()
    monkeypatch.setattr("app.services.auth_service.get_supabase_admin_client", lambda: mock)
    return mock


@pytest.fixture
def mock_supabase_anon(monkeypatch):
    """Mock Supabase anon client."""
    mock = MagicMock()
    monkeypatch.setattr("app.services.auth_service.get_supabase_anon_client", lambda: mock)
    return mock


class TestRegisterFlow:
    """Test cases for user registration flow."""

    def test_register_duplicate_email_check(self, auth_service, mock_supabase_admin):
        """Test that registration checks for existing emails."""
        # Mock existing user
        existing_response = MagicMock()
        existing_response.data = [{"id": "existing-user"}]

        mock_supabase_admin.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            existing_response
        )

        payload = RegisterRequest(
            email="existing@example.com",
            password="SecurePass123!",
            full_name="Test User",
            organization_name="Test Org",
        )

        with pytest.raises(HTTPException) as exc_info:
            auth_service.register(payload)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in exc_info.value.detail.lower()

    def test_register_supabase_auth_failure(self, auth_service, mock_supabase_admin, mock_supabase_anon):
        """Test registration handles Supabase auth API errors."""
        from supabase_auth.errors import AuthApiError

        # Mock no existing user
        no_user_response = MagicMock()
        no_user_response.data = []
        mock_supabase_admin.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            no_user_response
        )

        # Mock auth failure
        mock_supabase_anon.auth.sign_up.side_effect = AuthApiError(
            "Invalid password (too weak)",
            400,
            "weak_password",
        )

        payload = RegisterRequest(
            email="newuser@example.com",
            password="StrongPass123!",
            full_name="Test User",
            organization_name="Test Org",
        )

        with pytest.raises(HTTPException) as exc_info:
            auth_service.register(payload)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_organization_creation_failure(self, auth_service, mock_supabase_admin, mock_supabase_anon):
        """Test registration handles organization creation failures."""
        # Mock no existing user
        no_user_response = MagicMock()
        no_user_response.data = []
        mock_supabase_admin.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            no_user_response
        )

        # Mock successful Supabase auth
        user_id = str(uuid4())
        auth_user = MagicMock()
        auth_user.id = user_id
        auth_user.email_confirmed_at = None

        sign_up_response = MagicMock()
        sign_up_response.user = auth_user
        mock_supabase_anon.auth.sign_up.return_value = sign_up_response

        # Mock organization creation failure
        org_insert_response = MagicMock()
        org_insert_response.data = []
        mock_supabase_admin.table.return_value.insert.return_value.execute.return_value = org_insert_response

        payload = RegisterRequest(
            email="newuser@example.com",
            password="SecurePass123!",
            full_name="Test User",
            organization_name="Test Org",
        )

        with pytest.raises(HTTPException) as exc_info:
            auth_service.register(payload)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_register_missing_user_membership(self, auth_service, mock_supabase_admin, mock_supabase_anon):
        """Test registration fails if user membership cannot be created."""
        # Mock no existing user
        no_user_response = MagicMock()
        no_user_response.data = []
        mock_supabase_admin.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            no_user_response
        )

        # Mock successful Supabase auth
        user_id = str(uuid4())
        auth_user = MagicMock()
        auth_user.id = user_id
        auth_user.email_confirmed_at = None

        sign_up_response = MagicMock()
        sign_up_response.user = auth_user
        mock_supabase_anon.auth.sign_up.return_value = sign_up_response

        # Mock organization creation success
        org_id = str(uuid4())
        org_insert_response = MagicMock()
        org_insert_response.data = [{"id": org_id, "name": "Test Org"}]
        mock_supabase_admin.table.return_value.insert.return_value.execute.return_value = org_insert_response

        # Mock membership creation success
        membership_response = MagicMock()
        membership_response.data = None
        mock_supabase_admin.table.return_value.upsert.return_value.execute.return_value = membership_response

        # Mock app_users upsert failure
        user_upsert_response = MagicMock()
        user_upsert_response.data = []
        
        app_users_table = MagicMock()
        app_users_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = no_user_response
        app_users_table.upsert.return_value.execute.return_value = user_upsert_response

        default_table = MagicMock()
        default_table.insert.return_value.execute.return_value = org_insert_response
        default_table.upsert.return_value.execute.return_value = membership_response

        # Setup side effects for different table calls
        def table_side_effect(table_name):
            if table_name == "app_users":
                return app_users_table
            return default_table

        mock_supabase_admin.table.side_effect = table_side_effect

        payload = RegisterRequest(
            email="newuser@example.com",
            password="SecurePass123!",
            full_name="Test User",
            organization_name="Test Org",
        )

        with pytest.raises(HTTPException) as exc_info:
            auth_service.register(payload)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_register_email_case_insensitive(self, auth_service, mock_supabase_admin, mock_supabase_anon):
        """Test that email is normalized to lowercase."""
        # Mock no existing user
        no_user_response = MagicMock()
        no_user_response.data = []

        # Capture the email passed to the database
        captured_emails = []

        def email_check_side_effect(field, email):
            if field == "email":
                captured_emails.append(email)
            mock_eq = MagicMock()
            mock_eq.limit.return_value.execute.return_value = no_user_response
            return mock_eq

        select_mock = MagicMock()
        select_mock.eq.side_effect = email_check_side_effect
        mock_supabase_admin.table.return_value.select.return_value = select_mock

        payload = RegisterRequest(
            email="NewUser@EXAMPLE.COM",
            password="SecurePass123!",
            full_name="Test User",
            organization_name="Test Org",
        )

        # Mock auth and skip the full flow
        mock_supabase_anon.auth.sign_up.side_effect = Exception("Skip full flow")

        try:
            auth_service.register(payload)
        except Exception:
            pass

        # Verify email was normalized
        assert len(captured_emails) > 0
        assert captured_emails[0] == "newuser@example.com"

    def test_register_password_hashing(self, auth_service):
        """Test that passwords are properly hashed."""
        plain_password = "SecurePass123!"
        hashed = auth_service.hash_password(plain_password)

        # Verify hash is different from plain text
        assert hashed != plain_password

        # Verify password verification works
        assert auth_service.verify_password(plain_password, hashed) is True

        # Verify wrong password fails verification
        assert auth_service.verify_password("WrongPass123!", hashed) is False


class TestTokenGeneration:
    """Test cases for token generation and JWT handling."""

    def test_access_token_encoding(self, auth_service):
        """Test access token is properly encoded."""
        user_id = "test-user-id"
        role = "admin"
        organization_id = "test-org-id"
        email = "test@example.com"

        token = auth_service._encode_access_token(
            user_id=user_id,
            role=role,
            organization_id=organization_id,
            email=email,
        )

        # Verify token is a string
        assert isinstance(token, str)
        assert len(token) > 0

        # Verify token can be decoded
        from jose import jwt

        from app.core.config import settings

        decoded = jwt.decode(token, settings.API_SECRET_KEY, algorithms=["HS256"])
        assert decoded["sub"] == user_id
        assert decoded["role"] == role
        assert decoded["organization_id"] == organization_id
        assert decoded["email"] == email
        assert decoded["token_type"] == "access"

    def test_refresh_token_encoding(self, auth_service):
        """Test refresh token is properly encoded."""
        user_id = "test-user-id"
        organization_id = "test-org-id"

        token = auth_service._encode_refresh_token(
            user_id=user_id,
            organization_id=organization_id,
        )

        # Verify token is a string
        assert isinstance(token, str)
        assert len(token) > 0

        # Verify token can be decoded
        from jose import jwt

        from app.core.config import settings

        decoded = jwt.decode(token, settings.API_SECRET_KEY, algorithms=["HS256"])
        assert decoded["sub"] == user_id
        assert decoded["organization_id"] == organization_id
        assert decoded["token_type"] == "refresh"
        assert "jti" in decoded

    def test_token_expiration(self, auth_service):
        """Test token expiration times are set correctly."""
        from datetime import UTC, datetime

        from jose import jwt

        from app.core.config import settings

        user_id = "test-user-id"

        # Test access token expiration
        access_token = auth_service._encode_access_token(
            user_id=user_id,
            role="admin",
            organization_id="org-id",
            email="test@example.com",
        )

        decoded = jwt.decode(access_token, settings.API_SECRET_KEY, algorithms=["HS256"])
        exp_time = datetime.fromtimestamp(decoded["exp"], tz=UTC)
        now = datetime.now(UTC)

        # Verify expiration is in the future (within reasonable bounds)
        assert exp_time > now
        # Access token should expire in ~15 minutes
        time_diff_minutes = (exp_time - now).total_seconds() / 60
        assert 14 <= time_diff_minutes <= 16

    def test_issue_tokens_creates_refresh_token_record(self, auth_service, mock_supabase_admin):
        """Test that issuing tokens creates a refresh token record in DB."""
        user = AuthUser(
            id="test-user-id",
            email="test@example.com",
            full_name="Test User",
            role="admin",
            organization_id="test-org-id",
            organization_name="Test Org",
            email_verified=True,
        )

        # Mock refresh token insert
        insert_response = MagicMock()
        insert_response.execute.return_value = MagicMock()
        mock_supabase_admin.table.return_value.insert.return_value = insert_response

        response = auth_service._issue_tokens(user)

        # Verify response structure
        assert isinstance(response, TokenResponse)
        assert response.access_token
        assert response.refresh_token
        assert response.token_type == "bearer"
        assert response.expires_in > 0
        assert response.user == user

        # Verify refresh token was stored
        mock_supabase_admin.table.assert_called_with("refresh_tokens")


class TestOrganizationSetup:
    """Test cases for organization setup during registration."""

    def test_organization_auto_naming(self, auth_service, mock_supabase_admin):
        """Test organization naming when duplicate names exist."""
        user_id = "test-user-id"

        # Mock first insert fails with duplicate key error
        mock_supabase_admin.table.return_value.insert.return_value.execute.side_effect = [
            Exception("duplicate key error on slug"),  # First attempt fails
            MagicMock(data=[{"id": "org-id-2", "name": "Test Org-abc"}]),  # Second attempt succeeds
        ]

        # Mock membership upsert
        mock_supabase_admin.table.return_value.upsert.return_value.execute.return_value = MagicMock()

        org_id, org_name = auth_service._ensure_organization(
            user_id=user_id,
            organization_name="Test Org",
        )

        assert org_id is not None
        assert org_name is not None

    def test_organization_empty_name_fallback(self, auth_service, mock_supabase_admin):
        """Test organization gets default name if empty."""
        user_id = "test-user-id"

        # Mock successful insert with default name
        org_id_val = str(uuid4())
        mock_response = MagicMock()
        mock_response.data = [{"id": org_id_val, "name": "My Organization"}]
        mock_supabase_admin.table.return_value.insert.return_value.execute.return_value = mock_response

        # Mock membership upsert
        mock_supabase_admin.table.return_value.upsert.return_value.execute.return_value = MagicMock()

        org_id, org_name = auth_service._ensure_organization(
            user_id=user_id,
            organization_name="",  # Empty name
        )

        assert org_id == org_id_val
        assert org_name == "My Organization"
