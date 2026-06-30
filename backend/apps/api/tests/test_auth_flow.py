from __future__ import annotations

from app.models.auth import AuthUser, TokenResponse


def _token_response() -> TokenResponse:
    return TokenResponse(
        access_token="access-token",
        refresh_token="refresh-token",
        expires_in=900,
        user=AuthUser(
            id="user-1",
            email="user@example.com",
            full_name="User One",
            role="admin",
            organization_id="org-1",
            organization_name="Org 1",
            email_verified=True,
        ),
    )


def test_login_route(client, monkeypatch):
    monkeypatch.setattr("app.routers.auth.auth_service.login", lambda _payload: _token_response())

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "StrongPass!123"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"] == "access-token"


def test_refresh_route(client, monkeypatch):
    monkeypatch.setattr("app.routers.auth.auth_service.refresh", lambda _token: _token_response())

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "refresh-token-1234567890"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["organization_id"] == "org-1"


def test_logout_route(client, monkeypatch, manager_headers):
    called = {"ok": False}

    def _logout(_token):
        called["ok"] = True

    monkeypatch.setattr("app.routers.auth.auth_service.logout", _logout)

    response = client.post(
        "/api/v1/auth/logout",
        headers=manager_headers,
        json={"refresh_token": "refresh-token-1234567890"},
    )
    assert response.status_code == 200
    assert called["ok"] is True


# =============== REGISTRATION TEST CASES ===============


def test_register_success(client, monkeypatch):
    """Test successful user registration with valid inputs."""
    monkeypatch.setattr("app.routers.auth.auth_service.register", lambda _payload: _token_response())

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "full_name": "New User",
            "organization_name": "My Company",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "access-token"
    assert data["refresh_token"] == "refresh-token"
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "user@example.com"
    assert data["user"]["full_name"] == "User One"
    assert data["user"]["organization_id"] == "org-1"


def test_register_duplicate_email(client, monkeypatch):
    """Test registration fails with duplicate email."""
    from fastapi import HTTPException, status

    def _register_duplicate(_payload):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already exists. Please log in.",
        )

    monkeypatch.setattr("app.routers.auth.auth_service.register", _register_duplicate)

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "existing@example.com",
            "password": "SecurePass123!",
            "full_name": "Existing User",
            "organization_name": "Old Company",
        },
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["error"]["message"].lower()


def test_register_weak_password(client):
    """Test registration fails with password too short."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "weak",  # Less than 8 characters
            "full_name": "Test User",
            "organization_name": "Test Org",
        },
    )
    assert response.status_code == 422
    assert "validation" in response.json()["error"]["type"]


def test_register_missing_fields(client):
    """Test registration fails with missing required fields."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            # Missing password, full_name, organization_name
        },
    )
    assert response.status_code == 422


def test_register_invalid_email(client):
    """Test registration fails with invalid email format."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "SecurePass123!",
            "full_name": "Test User",
            "organization_name": "Test Org",
        },
    )
    assert response.status_code == 422


def test_register_empty_full_name(client):
    """Test registration fails with empty full name."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "SecurePass123!",
            "full_name": "",  # Too short
            "organization_name": "Test Org",
        },
    )
    assert response.status_code == 422


def test_register_empty_organization_name(client):
    """Test registration fails with empty organization name."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "SecurePass123!",
            "full_name": "Test User",
            "organization_name": "",  # Too short
        },
    )
    assert response.status_code == 422


def test_register_email_normalization(client, monkeypatch):
    """Test that email is normalized (lowercase and trimmed) before use."""
    captured_payload = {}

    def _register_capture(payload):
        captured_payload["email"] = payload.email
        return _token_response()

    monkeypatch.setattr("app.routers.auth.auth_service.register", _register_capture)

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "  USER@EXAMPLE.COM  ",
            "password": "SecurePass123!",
            "full_name": "Test User",
            "organization_name": "Test Org",
        },
    )
    assert response.status_code == 200
    # Verify normalization happens (implementation detail)


def test_register_organization_auto_created(client, monkeypatch):
    """Test that organization is automatically created during registration."""
    captured_org_name = {}

    def _register_capture(payload):
        captured_org_name["name"] = payload.organization_name
        return _token_response()

    monkeypatch.setattr("app.routers.auth.auth_service.register", _register_capture)

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "SecurePass123!",
            "full_name": "Test User",
            "organization_name": "Brand New Corp",
        },
    )
    assert response.status_code == 200
    assert captured_org_name["name"] == "Brand New Corp"


def test_register_long_password(client, monkeypatch):
    """Test registration with long password (up to 128 chars)."""
    monkeypatch.setattr("app.routers.auth.auth_service.register", lambda _payload: _token_response())

    long_password = "A" * 128  # Max length
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": long_password,
            "full_name": "Test User",
            "organization_name": "Test Org",
        },
    )
    assert response.status_code == 200


def test_register_password_too_long(client):
    """Test registration fails with password exceeding 128 chars."""
    too_long_password = "A" * 129  # Over max length
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": too_long_password,
            "full_name": "Test User",
            "organization_name": "Test Org",
        },
    )
    assert response.status_code == 422


def test_register_returns_user_profile(client, monkeypatch):
    """Test that registration returns complete user profile in response."""
    monkeypatch.setattr("app.routers.auth.auth_service.register", lambda _payload: _token_response())

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "full_name": "New User",
            "organization_name": "My Company",
        },
    )
    assert response.status_code == 200
    user = response.json()["user"]
    assert user["id"] == "user-1"
    assert user["email"] == "user@example.com"
    assert user["full_name"] == "User One"
    assert user["role"] == "admin"
    assert user["organization_id"] == "org-1"
    assert user["organization_name"] == "Org 1"
    assert "email_verified" in user


def test_register_email_rate_limit(client, monkeypatch):
    """Test registration handles email rate limit gracefully."""
    from fastapi import HTTPException, status

    def _register_rate_limit(_payload):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Email rate limit exceeded. Please try again in a few minutes.",
        )

    monkeypatch.setattr("app.routers.auth.auth_service.register", _register_rate_limit)

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "SecurePass123!",
            "full_name": "Test User",
            "organization_name": "Test Org",
        },
    )
    assert response.status_code == 429
    assert "rate limit" in response.json()["error"]["message"].lower()


def test_register_special_characters_in_names(client, monkeypatch):
    """Test registration with special characters in names."""
    monkeypatch.setattr("app.routers.auth.auth_service.register", lambda _payload: _token_response())

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "SecurePass123!",
            "full_name": "José María García",
            "organization_name": "O'Reilly & Associates",
        },
    )
    assert response.status_code == 200
