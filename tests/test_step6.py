"""Tests voor Stap 6: Curaties (F6)."""

import pytest


class TestCurationCreate:
    """Test curatie aanmaken."""

    async def test_create_curation(self, test_client):
        response = await test_client.post("/api/curaties/create", json={
            "name": "Show & tell juli",
            "purpose": "Demonstratie voor directie",
            "description": "Een verzameling van de meest interessante initiatieven.",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        assert data["name"] == "Show & tell juli"

    async def test_create_curation_minimal(self, test_client):
        response = await test_client.post("/api/curaties/create", json={
            "name": "Minimale curatie",
        })
        assert response.status_code == 200

    async def test_create_curation_requires_name(self, test_client):
        response = await test_client.post("/api/curaties/create", json={})
        assert response.status_code == 422


class TestCurationUpdate:
    """Test curatie bijwerken."""

    async def test_update_curation_name(self, test_client):
        create_resp = await test_client.post("/api/curaties/create", json={
            "name": "Originele naam",
        })
        curation_id = create_resp.json()["id"]

        response = await test_client.put(f"/api/curaties/{curation_id}", json={
            "name": "Gewijzigde naam",
        })
        assert response.status_code == 200

    async def test_update_curation_description(self, test_client):
        create_resp = await test_client.post("/api/curaties/create", json={
            "name": "Test curatie",
        })
        curation_id = create_resp.json()["id"]

        response = await test_client.put(f"/api/curaties/{curation_id}", json={
            "description": "Nieuwe beschrijving.",
        })
        assert response.status_code == 200

    async def test_update_nonexistent(self, test_client):
        response = await test_client.put("/api/curaties/nonexistent-id", json={
            "name": "Test",
        })
        assert response.status_code == 404


class TestCurationDelete:
    """Test curatie verwijderen."""

    async def test_delete_curation(self, test_client):
        create_resp = await test_client.post("/api/curaties/create", json={
            "name": "Te verwijderen",
        })
        curation_id = create_resp.json()["id"]

        response = await test_client.delete(f"/api/curaties/{curation_id}")
        assert response.status_code == 200

    async def test_delete_nonexistent(self, test_client):
        response = await test_client.delete("/api/curaties/nonexistent-id")
        assert response.status_code == 404


class TestCurationItems:
    """Test curatie items."""

    async def test_add_item_to_curation(self, test_client):
        # Maak curatie + initiatief
        c_resp = await test_client.post("/api/curaties/create", json={
            "name": "Test curatie",
        })
        c_id = c_resp.json()["id"]

        i_resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Initiatief A"},
        )
        i_id = i_resp.json()["id"]

        response = await test_client.post(f"/api/curaties/{c_id}/items/add", json={
            "initiative_id": i_id,
            "position": 1,
            "note": "Dit initiatief is relevant omdat...",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        assert data["position"] == 1

    async def test_add_item_invalid_curation(self, test_client):
        i_resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Initiatief A"},
        )
        i_id = i_resp.json()["id"]

        response = await test_client.post("/api/curaties/nonexistent-id/items/add", json={
            "initiative_id": i_id,
            "position": 1,
        })
        assert response.status_code == 404

    async def test_add_item_invalid_initiative(self, test_client):
        c_resp = await test_client.post("/api/curaties/create", json={
            "name": "Test curatie",
        })
        c_id = c_resp.json()["id"]

        response = await test_client.post(f"/api/curaties/{c_id}/items/add", json={
            "initiative_id": "nonexistent-id",
            "position": 1,
        })
        assert response.status_code == 404

    async def test_update_item_note(self, test_client):
        c_resp = await test_client.post("/api/curaties/create", json={
            "name": "Test curatie",
        })
        c_id = c_resp.json()["id"]

        i_resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Initiatief A"},
        )
        i_id = i_resp.json()["id"]

        add_resp = await test_client.post(f"/api/curaties/{c_id}/items/add", json={
            "initiative_id": i_id,
            "position": 1,
            "note": "Originele notitie",
        })
        item_id = add_resp.json()["id"]

        response = await test_client.put(
            f"/api/curaties/{c_id}/items/{item_id}",
            json={"note": "Gewijzigde notitie"},
        )
        assert response.status_code == 200

    async def test_update_item_position(self, test_client):
        c_resp = await test_client.post("/api/curaties/create", json={
            "name": "Test curatie",
        })
        c_id = c_resp.json()["id"]

        i_resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Initiatief A"},
        )
        i_id = i_resp.json()["id"]

        add_resp = await test_client.post(f"/api/curaties/{c_id}/items/add", json={
            "initiative_id": i_id,
            "position": 1,
        })
        item_id = add_resp.json()["id"]

        response = await test_client.put(
            f"/api/curaties/{c_id}/items/{item_id}",
            json={"position": 5},
        )
        assert response.status_code == 200

    async def test_delete_item_from_curation(self, test_client):
        c_resp = await test_client.post("/api/curaties/create", json={
            "name": "Test curatie",
        })
        c_id = c_resp.json()["id"]

        i_resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Initiatief A"},
        )
        i_id = i_resp.json()["id"]

        add_resp = await test_client.post(f"/api/curaties/{c_id}/items/add", json={
            "initiative_id": i_id,
            "position": 1,
        })
        item_id = add_resp.json()["id"]

        response = await test_client.delete(
            f"/api/curaties/{c_id}/items/{item_id}",
        )
        assert response.status_code == 200

    async def test_multiple_items_ordered(self, test_client):
        c_resp = await test_client.post("/api/curaties/create", json={
            "name": "Test curatie",
        })
        c_id = c_resp.json()["id"]

        init_ids = []
        for i in range(3):
            i_resp = await test_client.post(
                "/api/initiatieven/create", json={"title": f"Initiatief {i}"},
            )
            init_ids.append(i_resp.json()["id"])

        # Voeg items toe in specifieke volgorde
        for pos, iid in enumerate(init_ids, start=1):
            await test_client.post(f"/api/curaties/{c_id}/items/add", json={
                "initiative_id": iid,
                "position": pos,
            })

        # Check JSON endpoint
        response = await test_client.get("/api/curaties/json")
        data = response.json()
        assert len(data) == 1
        assert data[0]["item_count"] == 3


class TestCurationList:
    """Test curaties lijst."""

    async def test_list_curations(self, test_client):
        for i in range(3):
            await test_client.post("/api/curaties/create", json={
                "name": f"Curatie {i}",
            })

        response = await test_client.get("/api/curaties/json")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    async def test_empty_curations_list(self, test_client):
        response = await test_client.get("/api/curaties/json")
        assert response.status_code == 200
        assert response.json() == []

    async def test_curation_in_multiple_curations(self, test_client):
        """Initiatief kan in meerdere curaties zitten."""
        init_resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Gedeeld initiatief"},
        )
        init_id = init_resp.json()["id"]

        for i in range(2):
            c_resp = await test_client.post("/api/curaties/create", json={
                "name": f"Curatie {i}",
            })
            c_id = c_resp.json()["id"]

            await test_client.post(f"/api/curaties/{c_id}/items/add", json={
                "initiative_id": init_id,
                "position": 1,
            })

        response = await test_client.get("/api/curaties/json")
        data = response.json()
        assert len(data) == 2
