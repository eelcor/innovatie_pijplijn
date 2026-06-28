"""Tests voor admin en health-check endpoints."""

import pytest


class TestHealthCheck:
    """Test de health check endpoint."""

    async def test_health_returns_200(self, test_client):
        response = await test_client.get("/health")
        assert response.status_code == 200

    async def test_health_status_is_healthy(self, test_client):
        response = await test_client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    async def test_health_has_components(self, test_client):
        response = await test_client.get("/health")
        data = response.json()
        assert "components" in data
        assert "database" in data["components"]
        assert "ai" in data["components"]

    async def test_health_database_is_healthy(self, test_client):
        response = await test_client.get("/health")
        data = response.json()
        assert data["components"]["database"]["status"] == "healthy"

    async def test_health_has_timestamp(self, test_client):
        response = await test_client.get("/health")
        data = response.json()
        assert "timestamp" in data


class TestAdminStatus:
    """Test de admin status endpoint."""

    async def test_status_returns_200(self, test_client):
        response = await test_client.get("/api/admin/status")
        assert response.status_code == 200

    async def test_status_has_version(self, test_client):
        response = await test_client.get("/api/admin/status")
        data = response.json()
        assert "version" in data

    async def test_status_has_counts(self, test_client):
        response = await test_client.get("/api/admin/status")
        data = response.json()
        counts = data["counts"]
        assert "initiatives" in counts
        assert "hypotheses" in counts
        assert "curations" in counts

    async def test_status_counts_are_correct(self, test_client):
        # Maak een initiatief aan
        await test_client.post("/api/initiatieven/create", json={"title": "Test"})

        response = await test_client.get("/api/admin/status")
        data = response.json()
        assert data["counts"]["initiatives"] >= 1


class TestAdminConfig:
    """Test de admin config endpoint."""

    async def test_config_returns_200(self, test_client):
        response = await test_client.get("/api/admin/config")
        assert response.status_code == 200

    async def test_config_has_sections(self, test_client):
        response = await test_client.get("/api/admin/config")
        data = response.json()
        assert "app" in data
        assert "database" in data
        assert "ai" in data
        assert "logging" in data

    async def test_config_does_not_expose_secrets(self, test_client):
        """API key moet niet volledig worden getoond."""
        response = await test_client.get("/api/admin/config")
        data = response.json()
        # api_key_set is een boolean, geen echte key
        assert "api_key" not in str(data["ai"]).lower() or "api_key_set" in str(data["ai"])


class TestAdminBackup:
    """Test de backup endpoints."""

    async def test_backup_returns_success(self, test_client):
        response = await test_client.post("/api/admin/backup")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "database_backup" in data

    async def test_list_backups_returns_list(self, test_client):
        response = await test_client.get("/api/admin/backups")
        assert response.status_code == 200
        data = response.json()
        assert "backups" in data
        assert isinstance(data["backups"], list)

    async def test_delete_nonexistent_backup_returns_404(self, test_client):
        response = await test_client.delete(
            "/api/admin/backups/nonexistent_file.db"
        )
        assert response.status_code == 404
