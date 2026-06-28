"""Tests voor Stap 3: Initiatieven CRUD (F1-F2)."""

import pytest


class TestInitiativeCreate:
    """Test initiatief aanmaken — F1."""

    async def test_create_minimal(self, test_client):
        """Aanmaken met alleen titel moet werken (fase default verkenning)."""
        response = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Minimal initiatief"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        assert data["title"] == "Minimal initiatief"
        assert data["phase"] == "verkenning"

    async def test_create_requires_title(self, test_client):
        """Aanmaken zonder titel moet 422 geven."""
        response = await test_client.post(
            "/api/initiatieven/create",
            json={"phase": "experiment"},
        )
        assert response.status_code == 422

    async def test_create_with_all_fields(self, test_client):
        """Aanmaken met alle velden moet werken."""
        data = {
            "title": "Volledig initiatief",
            "description": "Dit is een uitgebreide beschrijving.",
            "phase": "experiment",
            "horizon": "h2",
            "mds": "AI & Digitalisering",
            "central_question": "Kan AI vergunningen versnellen?",
            "owner": "Team Innovatie",
        }
        response = await test_client.post(
            "/api/initiatieven/create",
            json=data,
        )
        assert response.status_code == 200

        # Check of alle velden correct zijn opgeslagen
        json_resp = await test_client.get("/api/initiatieven/json")
        initiatives = json_resp.json()
        created = [i for i in initiatives if i["id"] == response.json()["id"]]
        assert len(created) == 1
        created = created[0]
        assert created["description"] == data["description"]
        assert created["phase"] == "experiment"
        assert created["horizon"] == "h2"
        assert created["mds"] == "AI & Digitalisering"
        assert created["central_question"] == data["central_question"]
        assert created["owner"] == "Team Innovatie"
        assert created["status"] == "actief"

    async def test_create_returns_uuid(self, test_client):
        """Initiatief ID moet een valide UUID zijn."""
        response = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "UUID test"},
        )
        init_id = response.json()["id"]
        # UUID v4 format check
        assert len(init_id) == 36  # xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        assert init_id.count("-") == 4

    async def test_create_sets_timestamps(self, test_client):
        """Initiatief moet created_at en updated_at hebben."""
        await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Timestamp test"},
        )
        json_resp = await test_client.get("/api/initiatieven/json")
        data = json_resp.json()
        assert len(data) == 1
        assert data[0]["created_at"] is not None
        assert data[0]["updated_at"] is not None


class TestInitiativeUpdate:
    """Test initiatief bewerken — F2."""

    async def test_update_title(self, test_client):
        """Titel wijzigen moet werken."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Originele titel"},
        )
        init_id = resp.json()["id"]

        update_resp = await test_client.put(
            f"/api/initiatieven/{init_id}",
            json={"title": "Nieuwe titel"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["title"] == "Nieuwe titel"

    async def test_update_phase(self, test_client):
        """Fase wijzigen moet werken."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Phase test", "phase": "verkenning"},
        )
        init_id = resp.json()["id"]

        for phase in ["experiment", "pilot", "opschaling"]:
            update_resp = await test_client.put(
                f"/api/initiatieven/{init_id}",
                json={"phase": phase},
            )
            assert update_resp.status_code == 200
            assert update_resp.json()["phase"] == phase

    async def test_update_partial(self, test_client):
        """Partiële update moet andere velden intact laten."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={
                "title": "Originele titel",
                "description": "Originele beschrijving",
                "phase": "verkenning",
                "owner": "Team A",
            },
        )
        init_id = resp.json()["id"]

        # Alleen eigenaar wijzigen
        update_resp = await test_client.put(
            f"/api/initiatieven/{init_id}",
            json={"owner": "Team B"},
        )
        assert update_resp.status_code == 200

        # Check of andere velden intact zijn
        json_resp = await test_client.get("/api/initiatieven/json")
        initiatives = json_resp.json()
        updated = [i for i in initiatives if i["id"] == init_id][0]
        assert updated["title"] == "Originele titel"
        assert updated["description"] == "Originele beschrijving"
        assert updated["phase"] == "verkenning"
        assert updated["owner"] == "Team B"

    async def test_update_nonexistent(self, test_client):
        """Bewerken van niet-bestaand initiatief moet 404 geven."""
        response = await test_client.put(
            "/api/initiatieven/nonexistent-id",
            json={"title": "Test"},
        )
        assert response.status_code == 404

    async def test_update_updates_timestamp(self, test_client):
        """Bijwerken moet updated_at updaten."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Timestamp update test"},
        )
        init_id = resp.json()["id"]

        json_resp = await test_client.get("/api/initiatieven/json")
        before = [i for i in json_resp.json() if i["id"] == init_id][0]

        import time
        time.sleep(0.1)  # Zorg voor tijdverschil

        await test_client.put(
            f"/api/initiatieven/{init_id}",
            json={"title": "Gewijzigd"},
        )

        json_resp = await test_client.get("/api/initiatieven/json")
        after = [i for i in json_resp.json() if i["id"] == init_id][0]
        assert after["updated_at"] >= before["updated_at"]


class TestInitiativeDelete:
    """Test initiatief verwijderen."""

    async def test_delete_initiative(self, test_client):
        """Verwijderen moet werken."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Te verwijderen"},
        )
        init_id = resp.json()["id"]

        delete_resp = await test_client.delete(f"/api/initiatieven/{init_id}")
        assert delete_resp.status_code == 200

        # Check of het weg is
        json_resp = await test_client.get("/api/initiatieven/json")
        remaining = [i for i in json_resp.json() if i["id"] == init_id]
        assert len(remaining) == 0

    async def test_delete_nonexistent(self, test_client):
        """Verwijderen van niet-bestaand initiatief moet 404 geven."""
        response = await test_client.delete("/api/initiatieven/nonexistent-id")
        assert response.status_code == 404


class TestInitiativeValidation:
    """Test validatie-regels."""

    async def test_status_gestopt_requires_reason(self, test_client):
        """Status 'gestopt' via PUT vereist stop_reason."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Test"},
        )
        init_id = resp.json()["id"]

        response = await test_client.put(
            f"/api/initiatieven/{init_id}",
            json={"status": "gestopt"},
        )
        assert response.status_code == 400

    async def test_status_gestopt_with_reason_via_put(self, test_client):
        """Status 'gestopt' via PUT met stop_reason moet werken."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Test"},
        )
        init_id = resp.json()["id"]

        response = await test_client.put(
            f"/api/initiatieven/{init_id}",
            json={"status": "gestopt", "stop_reason": "Les geleerd."},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "gestopt"

    async def test_stop_endpoint_requires_reason(self, test_client):
        """Stop endpoint vereist stop_reason."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Test"},
        )
        init_id = resp.json()["id"]

        response = await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={},
        )
        assert response.status_code == 422

    async def test_stop_endpoint_sets_reason(self, test_client):
        """Stop endpoint moet stop_reason opslaan."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Test"},
        )
        init_id = resp.json()["id"]

        response = await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={"stop_reason": "We hebben geleerd dat X niet werkt."},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "gestopt"
        assert data["stop_reason"] == "We hebben geleerd dat X niet werkt."

    async def test_phase_enum_validation(self, test_client):
        """Ongeldige fase moet 422 geven."""
        response = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Test", "phase": "ongeldige_fase"},
        )
        assert response.status_code == 422

    async def test_horizon_enum_validation(self, test_client):
        """Ongeldige horizon moet 422 geven."""
        response = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Test", "horizon": "h99"},
        )
        assert response.status_code == 422


class TestInitiativeDetail:
    """Test initiatief detail endpoint."""

    async def test_detail_page_returns_200(self, test_client):
        """Detailpagina moet 200 geven voor bestaand initiatief."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Detail test"},
        )
        init_id = resp.json()["id"]

        response = await test_client.get(f"/api/initiatieven/detail/{init_id}")
        assert response.status_code == 200
        assert b"Detail test" in response.content

    async def test_detail_page_404(self, test_client):
        """Detailpagina voor niet-bestaand initiatief moet 404 geven."""
        response = await test_client.get("/api/initiatieven/detail/nonexistent-id")
        assert response.status_code == 404

    async def test_detail_shows_all_fields(self, test_client):
        """Detailpagina moet alle velden tonen."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={
                "title": "Volledig detail",
                "description": "Beschrijving hier",
                "phase": "experiment",
                "horizon": "h2",
                "mds": "AI MDS",
                "owner": "Team X",
                "central_question": "Kan het?",
            },
        )
        init_id = resp.json()["id"]

        response = await test_client.get(f"/api/initiatieven/detail/{init_id}")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Volledig detail" in content
        assert "Beschrijving hier" in content
        assert "AI MDS" in content
        assert "Team X" in content

    async def test_detail_shows_hypotheses(self, test_client):
        """Detailpagina moet hypothesen tonen."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Met hypothesen"},
        )
        init_id = resp.json()["id"]

        # Voeg hypothese toe
        await test_client.post(
            "/api/hypothesen/create",
            json={
                "initiative_id": init_id,
                "type": "value",
                "description": "Test hypothese",
            },
        )

        response = await test_client.get(f"/api/initiatieven/detail/{init_id}")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Test hypothese" in content


class TestInitiativeList:
    """Test initiatieven lijst."""

    async def test_list_page_returns_200(self, test_client):
        """Lijstpagina moet 200 geven."""
        response = await test_client.get("/api/initiatieven/lijst")
        assert response.status_code == 200

    async def test_list_json_sorted_by_updated(self, test_client):
        """JSON lijst moet gesorteerd zijn op updated_at (nieuwste eerst)."""
        # Maak meerdere initiatieven
        for i in range(3):
            await test_client.post(
                "/api/initiatieven/create",
                json={"title": f"Initiatief {i}"},
            )

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        assert len(data) == 3

        # Check dat alle initiatieven er zijn
        titles = [d["title"] for d in data]
        assert "Initiatief 0" in titles
        assert "Initiatief 1" in titles
        assert "Initiatief 2" in titles

        # Check sortering: updated_at moet aflopend zijn
        timestamps = [d["updated_at"] for d in data]
        assert timestamps == sorted(timestamps, reverse=True)

    async def test_list_empty(self, test_client):
        """Lege lijst moet lege array teruggeven."""
        response = await test_client.get("/api/initiatieven/json")
        assert response.status_code == 200
        assert response.json() == []


class TestInitiativeChangeLog:
    """Test wijzigingen-logboek."""

    async def test_change_log_endpoint_exists(self, test_client):
        """Wijzigingen-log endpoint moet bestaan."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Log test"},
        )
        init_id = resp.json()["id"]

        response = await test_client.get(f"/api/initiatieven/{init_id}/changes")
        assert response.status_code == 200

    async def change_log_tracks_phase_change(self, test_client):
        """Fase-wijziging moet in logboek staan."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Log test", "phase": "verkenning"},
        )
        init_id = resp.json()["id"]

        # Wijzig fase
        await test_client.put(
            f"/api/initiatieven/{init_id}",
            json={"phase": "experiment"},
        )

        response = await test_client.get(f"/api/initiatieven/{init_id}/changes")
        data = response.json()
        assert len(data) > 0
        # Check of er een fase-wijziging in staat
        phase_changes = [c for c in data if c["field"] == "phase"]
        assert len(phase_changes) >= 1
        assert phase_changes[-1]["new_value"] == "experiment"

    async def test_change_log_tracks_status_change(self, test_client):
        """Status-wijziging moet in logboek staan."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Log test"},
        )
        init_id = resp.json()["id"]

        # Stop met leeruitkomst
        await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={"stop_reason": "Les geleerd."},
        )

        response = await test_client.get(f"/api/initiatieven/{init_id}/changes")
        data = response.json()
        status_changes = [c for c in data if c["field"] == "status"]
        assert len(status_changes) >= 1
        assert status_changes[-1]["new_value"] == "gestopt"
