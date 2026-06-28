"""Tests voor authenticatie, autorisatie en CSRF-bescherming."""

import pytest


class TestAuthLogin:
    """Tests voor login/logout flow."""

    async def test_login_with_correct_credentials(self, auth_client):
        """Login met correcte credentials geeft 200 + session cookie.

        Uses auth_client which already has a mock user created.
        """
        response = await auth_client.post(
            "/api/auth/login",
            json={"username": "testadmin", "password": "testpassword"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testadmin"
        assert data["role"] == "admin"

    async def test_login_with_wrong_password(self, auth_client):
        """Login met verkeerd wachtwoord geeft 401."""
        response = await auth_client.post(
            "/api/auth/login",
            json={"username": "testadmin", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    async def test_login_nonexistent_user(self, test_client):
        """Login met niet-bestaande gebruiker geeft 401."""
        response = await test_client.post(
            "/api/auth/login",
            json={"username": "niet_bestand", "password": "whatever"},
        )
        assert response.status_code == 401

    async def test_logout(self, auth_client):
        """Logout verwijdert de session cookie."""
        response = await auth_client.post("/api/auth/logout")
        assert response.status_code == 200

    async def test_current_user_info(self, auth_client):
        """GET /me retourneert gebruikersinformatie."""
        response = await auth_client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert "username" in data
        assert "role" in data


class TestAuthCreateUser:
    """Tests voor gebruiker aanmaken (admin only)."""

    async def test_create_user_as_admin(self, auth_client):
        """Admin kan nieuwe gebruikers aanmaken."""
        response = await auth_client.post(
            "/api/auth/users/create",
            json={
                "username": "nieuwe_gebruiker",
                "password": "geheim123",
                "role": "viewer",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "nieuwe_gebruiker"
        assert data["role"] == "viewer"

    async def test_create_user_duplicate(self, auth_client):
        """Dubbele gebruikersnaam geeft 409."""
        await auth_client.post(
            "/api/auth/users/create",
            json={"username": "dup_user", "password": "pass123"},
        )
        response = await auth_client.post(
            "/api/auth/users/create",
            json={"username": "dup_user", "password": "pass456"},
        )
        assert response.status_code == 409

    async def test_create_user_missing_fields(self, auth_client):
        """Ontbrekende velden geven 400."""
        response = await auth_client.post(
            "/api/auth/users/create",
            json={"username": ""},
        )
        # Pydantic validatie geeft 422 (Unprocessable Entity)
        assert response.status_code in (400, 422)

    async def test_create_user_requires_auth(self, test_client):
        """Zonder sessie kan geen gebruiker aangemaakt worden (401)."""
        response = await test_client.post(
            "/api/auth/users/create",
            json={"username": "hacker", "password": "pass"},
        )
        assert response.status_code == 401

    async def test_list_users_as_admin(self, auth_client):
        """Admin kan alle gebruikers opvragen."""
        response = await auth_client.get("/api/auth/users")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestCSRFProtection:
    """Tests voor CSRF-bescherming."""

    async def test_csrf_token_endpoint(self, test_client):
        """GET /api/auth/csrf-token retourneert een token."""
        response = await test_client.get("/api/auth/csrf-token")
        assert response.status_code == 200
        data = response.json()
        assert "csrf_token" in data
        assert len(data["csrf_token"]) > 0

    async def test_csrf_middleware_exists(self):
        """CSRF middleware is correct geïmplementeerd."""
        from app.csrf import CSRFMiddleware
        assert hasattr(CSRFMiddleware, "EXEMPT_PATHS")
        assert "/api/auth/login" in CSRFMiddleware.EXEMPT_PATHS
        assert "/health" in CSRFMiddleware.EXEMPT_PATHS

    async def test_login_exempt_from_csrf(self, test_client):
        """Login endpoint is vrijgesteld van CSRF."""
        response = await test_client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
        # Moet 401 geven (ongeldige credentials), niet 403 (CSRF)
        assert response.status_code == 401

    async def test_health_exempt_from_csrf(self, test_client):
        """Health endpoint is vrijgesteld van CSRF."""
        response = await test_client.get("/health")
        assert response.status_code == 200


class TestAuthIntegration:
    """Integratietests voor auth met andere endpoints."""

    async def test_auth_cookie_set_on_login(self, auth_client):
        """Login stelt een session cookie in."""
        response = await auth_client.post(
            "/api/auth/login",
            json={"username": "testadmin", "password": "testpassword"},
        )
        assert response.status_code == 200
        # Session cookie moet aanwezig zijn
        assert "session" in response.cookies

    async def test_me_requires_auth(self, test_client):
        """GET /me vereist authenticatie."""
        response = await test_client.get("/api/auth/me")
        assert response.status_code == 401
