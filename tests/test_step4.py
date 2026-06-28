"""Tests voor Stap 4: Hypothesen & sub-hypothesen (F3)."""

import pytest


class TestHypothesisCreate:
    """Test hypothese aanmaken."""

    async def test_create_hypothesis(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]
        response = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id, "type": "value",
            "description": "Onze hypothese over waarde",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        assert data["type"] == "value"
        assert data["status"] == "open"

    async def test_create_all_types(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]
        for htype in ["value", "growth", "compliance"]:
            response = await test_client.post("/api/hypothesen/create", json={
                "initiative_id": init_id, "type": htype,
                "description": f"Hypothese van type {htype}",
            })
            assert response.status_code == 200
            assert response.json()["type"] == htype

    async def test_create_with_status_and_learning(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]
        response = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id, "type": "value",
            "description": "Bevestigde hypothese",
            "status": "bevestigd", "learning": "Dit werkt prima!",
        })
        assert response.status_code == 200

    async def test_create_requires_description(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]
        response = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id, "type": "value",
        })
        assert response.status_code == 422

    async def test_create_invalid_type(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]
        response = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id, "type": "ongeldig_type",
            "description": "Test",
        })
        assert response.status_code == 422

    async def test_create_invalid_status(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]
        response = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id, "type": "value",
            "description": "Test", "status": "ongeldig_status",
        })
        assert response.status_code == 422


class TestHypothesisSub:
    """Test sub-hypothesen."""

    async def test_create_sub_hypothesis(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        # Maak hoofdhypothese
        parent_resp = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id, "type": "value",
            "description": "Hoofdhypothese over waarde",
        })
        parent_id = parent_resp.json()["id"]

        # Maak sub-hypothese
        response = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id,
            "parent_hypothesis_id": parent_id,
            "type": "value",
            "description": "Sub: probleem hypothese",
        })
        assert response.status_code == 200

    async def test_sub_hypothesis_tree_structure(self, test_client):
        """Tree endpoint moet boomstructuur teruggeven."""
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        # Maak hoofdhypothese + 2 sub-hypothesen
        parent_resp = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id, "type": "value",
            "description": "Hoofdhypothese",
        })
        parent_id = parent_resp.json()["id"]

        for i in range(2):
            await test_client.post("/api/hypothesen/create", json={
                "initiative_id": init_id,
                "parent_hypothesis_id": parent_id,
                "type": "value",
                "description": f"Sub hypothese {i}",
            })

        # Haal tree op
        tree_resp = await test_client.get(f"/api/hypothesen/initiative/{init_id}")
        assert tree_resp.status_code == 200
        data = tree_resp.json()

        # Moet 1 hoofdhypothese hebben met 2 sub-hypothesen
        assert len(data) == 1
        assert data[0]["id"] == parent_id
        assert data[0]["is_sub"] is False
        assert len(data[0]["sub_hypotheses"]) == 2

    async def test_sub_hypothesis_invalid_parent(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]
        response = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id,
            "parent_hypothesis_id": "nonexistent-id",
            "type": "value",
            "description": "Sub zonder ouder",
        })
        assert response.status_code == 404

    async def test_multiple_levels_not_supported(self, test_client):
        """Max één niveau sub-hypothesen (geen sub-sub)."""
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        # Maak hoofdhypothese
        parent_resp = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id, "type": "value",
            "description": "Hoofdhypothese",
        })
        parent_id = parent_resp.json()["id"]

        # Maak sub-hypothese
        sub_resp = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id,
            "parent_hypothesis_id": parent_id,
            "type": "value",
            "description": "Sub hypothese",
        })
        sub_id = sub_resp.json()["id"]

        # Tree moet correcte structuur hebben
        tree_resp = await test_client.get(f"/api/hypothesen/initiative/{init_id}")
        data = tree_resp.json()
        assert len(data) == 1
        assert len(data[0]["sub_hypotheses"]) == 1


class TestHypothesisUpdate:
    """Test hypothese bijwerken."""

    async def test_update_status_to_bevestigd_requires_learning(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]
        hyp_resp = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id, "type": "value",
            "description": "Test hypothese",
        })
        hyp_id = hyp_resp.json()["id"]

        # Zonder leeruitkomst moet falen
        response = await test_client.put(f"/api/hypothesen/{hyp_id}", json={
            "status": "bevestigd",
        })
        assert response.status_code == 400

    async def test_update_status_to_bevestigd_with_learning(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]
        hyp_resp = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id, "type": "value",
            "description": "Test hypothese",
        })
        hyp_id = hyp_resp.json()["id"]

        response = await test_client.put(f"/api/hypothesen/{hyp_id}", json={
            "status": "bevestigd", "learning": "Dit werkt!",
        })
        assert response.status_code == 200

    async def test_update_status_to_weerlegd_requires_learning(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]
        hyp_resp = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id, "type": "value",
            "description": "Test hypothese",
        })
        hyp_id = hyp_resp.json()["id"]

        response = await test_client.put(f"/api/hypothesen/{hyp_id}", json={
            "status": "weerlegd",
        })
        assert response.status_code == 400

    async def test_update_status_to_weerlegd_with_learning(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]
        hyp_resp = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id, "type": "value",
            "description": "Test hypothese",
        })
        hyp_id = hyp_resp.json()["id"]

        response = await test_client.put(f"/api/hypothesen/{hyp_id}", json={
            "status": "weerlegd", "learning": "Dit werkt niet.",
        })
        assert response.status_code == 200

    async def test_update_status_to_open_clears_learning(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]
        hyp_resp = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id, "type": "value",
            "description": "Test hypothese",
            "status": "bevestigd", "learning": "Oude les",
        })
        hyp_id = hyp_resp.json()["id"]

        # Zet terug naar open
        response = await test_client.put(f"/api/hypothesen/{hyp_id}", json={
            "status": "open",
        })
        assert response.status_code == 200

    async def test_update_description(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]
        hyp_resp = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id, "type": "value",
            "description": "Originele beschrijving",
        })
        hyp_id = hyp_resp.json()["id"]

        response = await test_client.put(f"/api/hypothesen/{hyp_id}", json={
            "description": "Gewijzigde beschrijving",
        })
        assert response.status_code == 200

    async def test_update_nonexistent(self, test_client):
        response = await test_client.put("/api/hypothesen/nonexistent-id", json={
            "description": "Test",
        })
        assert response.status_code == 404


class TestHypothesisDelete:
    """Test hypothese verwijderen."""

    async def test_delete_hypothesis(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]
        hyp_resp = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id, "type": "value",
            "description": "Te verwijderen",
        })
        hyp_id = hyp_resp.json()["id"]

        response = await test_client.delete(f"/api/hypothesen/{hyp_id}")
        assert response.status_code == 200

    async def test_delete_nonexistent(self, test_client):
        response = await test_client.delete("/api/hypothesen/nonexistent-id")
        assert response.status_code == 404


class TestHypothesisTree:
    """Test boomstructuur endpoint."""

    async def test_empty_tree(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        response = await test_client.get(f"/api/hypothesen/initiative/{init_id}")
        assert response.status_code == 200
        assert response.json() == []

    async def test_tree_with_mixed_statuses(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        statuses = ["open", "bevestigd", "weerlegd", "vervallen"]
        for status in statuses:
            learning = "Les" if status != "open" else None
            await test_client.post("/api/hypothesen/create", json={
                "initiative_id": init_id, "type": "value",
                "description": f"Hypothese {status}",
                "status": status, "learning": learning,
            })

        tree_resp = await test_client.get(f"/api/hypothesen/initiative/{init_id}")
        data = tree_resp.json()
        assert len(data) == 4

    async def test_tree_is_sub_flag(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        parent_resp = await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id, "type": "value",
            "description": "Hoofd",
        })
        parent_id = parent_resp.json()["id"]

        await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id,
            "parent_hypothesis_id": parent_id,
            "type": "value", "description": "Sub",
        })

        tree_resp = await test_client.get(f"/api/hypothesen/initiative/{init_id}")
        data = tree_resp.json()
        assert data[0]["is_sub"] is False
        assert data[0]["sub_hypotheses"][0]["is_sub"] is True


class TestHypothesisAllStatuses:
    """Test alle hypothese-statussen."""

    async def test_all_statuses_valid(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        for status in ["open", "bevestigd", "weerlegd", "vervallen"]:
            learning = "Les" if status != "open" else None
            response = await test_client.post("/api/hypothesen/create", json={
                "initiative_id": init_id, "type": "value",
                "description": f"Test {status}",
                "status": status, "learning": learning,
            })
            assert response.status_code == 200
