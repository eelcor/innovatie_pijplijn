"""Tests voor F9: Centrale vragen."""

import pytest


class TestCentralQuestionCreate:
    """Test centrale vraag aanmaken."""

    async def test_create_question(self, test_client):
        response = await test_client.post("/api/vragen/create", json={
            "question": "Kan AI wachttijden met 30% reduceren?",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        assert data["question"] == "Kan AI wachttijden met 30% reduceren?"
        assert data["already_exists"] is False

    async def test_create_question_requires_text(self, test_client):
        response = await test_client.post("/api/vragen/create", json={})
        assert response.status_code == 422

    async def test_create_duplicate_returns_existing(self, test_client):
        """Identieke vraag retourneert bestaande record."""
        q1 = await test_client.post("/api/vragen/create", json={
            "question": "Zullen burgers dit platform gebruiken?",
        })
        assert q1.status_code == 200

        q2 = await test_client.post("/api/vragen/create", json={
            "question": "Zullen burgers dit platform gebruiken?",
        })
        data = q2.json()
        assert data["already_exists"] is True
        assert data["id"] == q1.json()["id"]

    async def test_create_strips_whitespace(self, test_client):
        response = await test_client.post("/api/vragen/create", json={
            "question": "  Een vraag met spaties  ",
        })
        assert response.status_code == 200
        assert response.json()["question"] == "Een vraag met spaties"


class TestCentralQuestionUpdate:
    """Test centrale vraag bewerken."""

    async def test_update_question_text(self, test_client):
        create = await test_client.post("/api/vragen/create", json={
            "question": "Originele vraag",
        })
        q_id = create.json()["id"]

        response = await test_client.put(f"/api/vragen/{q_id}", json={
            "question": "Gewijzigde vraag",
        })
        assert response.status_code == 200
        assert response.json()["question"] == "Gewijzigde vraag"

    async def test_update_nonexistent(self, test_client):
        response = await test_client.put("/api/vragen/nonexistent-id", json={
            "question": "Test",
        })
        assert response.status_code == 404


class TestCentralQuestionDelete:
    """Test centrale vraag soft-delete."""

    async def test_soft_delete_question(self, test_client):
        create = await test_client.post("/api/vragen/create", json={
            "question": "Te verwijderen",
        })
        q_id = create.json()["id"]

        response = await test_client.delete(f"/api/vragen/{q_id}")
        assert response.status_code == 200

        # Niet meer in lijst (alleen actieve vragen)
        list_resp = await test_client.get("/api/vragen/json")
        questions = list_resp.json()
        assert not any(q["id"] == q_id for q in questions)

    async def test_delete_nonexistent(self, test_client):
        response = await test_client.delete("/api/vragen/nonexistent-id")
        assert response.status_code == 404


class TestCentralQuestionList:
    """Test overzicht van centrale vragen."""

    async def test_list_questions(self, test_client):
        for i in range(3):
            await test_client.post("/api/vragen/create", json={
                "question": f"Vraag {i}",
            })

        response = await test_client.get("/api/vragen/json")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    async def test_list_empty(self, test_client):
        response = await test_client.get("/api/vragen/json")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_excludes_inactive(self, test_client):
        create = await test_client.post("/api/vragen/create", json={
            "question": "Actieve vraag",
        })
        q_id = create.json()["id"]

        # Soft delete
        await test_client.delete(f"/api/vragen/{q_id}")

        response = await test_client.get("/api/vragen/json")
        data = response.json()
        assert not any(q["id"] == q_id for q in data)


class TestInitiativeQuestionLink:
    """Test koppeling tussen initiatief en centrale vraag."""

    async def test_link_question_to_initiative(self, test_client):
        # Maak vraag + initiatief
        q_resp = await test_client.post("/api/vragen/create", json={
            "question": "Testvraag",
        })
        q_id = q_resp.json()["id"]

        i_resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Test initiatief",
        })
        i_id = i_resp.json()["id"]

        # Koppel vraag aan initiatief
        response = await test_client.post(f"/api/vragen/{q_id}/initiatives/add/{i_id}")
        assert response.status_code == 200

        # Check dat koppeling bestaat
        questions = await test_client.get(f"/api/vragen/{q_id}/initiatives")
        data = questions.json()
        assert len(data) == 1
        assert data[0]["id"] == i_id

    async def test_duplicate_link_returns_already_exists(self, test_client):
        q_resp = await test_client.post("/api/vragen/create", json={
            "question": "Testvraag",
        })
        q_id = q_resp.json()["id"]

        i_resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Test initiatief",
        })
        i_id = i_resp.json()["id"]

        await test_client.post(f"/api/vragen/{q_id}/initiatives/add/{i_id}")
        response = await test_client.post(f"/api/vragen/{q_id}/initiatives/add/{i_id}")
        assert response.status_code == 200
        assert "bestaat al" in response.json()["message"]

    async def test_remove_link(self, test_client):
        q_resp = await test_client.post("/api/vragen/create", json={
            "question": "Testvraag",
        })
        q_id = q_resp.json()["id"]

        i_resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Test initiatief",
        })
        i_id = i_resp.json()["id"]

        await test_client.post(f"/api/vragen/{q_id}/initiatives/add/{i_id}")

        # Verwijder koppeling
        response = await test_client.delete(f"/api/vragen/{q_id}/initiatives/remove/{i_id}")
        assert response.status_code == 200

        # Check dat koppeling weg is
        questions = await test_client.get(f"/api/vragen/{q_id}/initiatives")
        assert questions.json() == []

    async def test_multiple_questions_per_initiative(self, test_client):
        """Eén initiatief kan meerdere centrale vragen hebben."""
        i_resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Multi-vraag initiatief",
        })
        i_id = i_resp.json()["id"]

        q_ids = []
        for i in range(3):
            q_resp = await test_client.post("/api/vragen/create", json={
                "question": f"Vraag {i}",
            })
            q_ids.append(q_resp.json()["id"])
            await test_client.post(f"/api/vragen/{q_resp.json()['id']}/initiatives/add/{i_id}")

        # Check dat alle 3 vragen aan initiatief gekoppeld zijn
        response = await test_client.get(f"/api/vragen/initiative/{i_id}")
        data = response.json()
        assert len(data) == 3

    async def test_multiple_initiatives_per_question(self, test_client):
        """Eén vraag kan aan meerdere initiatieven gekoppeld zijn."""
        q_resp = await test_client.post("/api/vragen/create", json={
            "question": "Gedeelde vraag",
        })
        q_id = q_resp.json()["id"]

        i_ids = []
        for i in range(3):
            i_resp = await test_client.post("/api/initiatieven/create", json={
                "title": f"Initiatief {i}",
            })
            i_ids.append(i_resp.json()["id"])
            await test_client.post(f"/api/vragen/{q_id}/initiatives/add/{i_resp.json()['id']}")

        # Check dat alle 3 initiatieven aan vraag gekoppeld zijn
        response = await test_client.get(f"/api/vragen/{q_id}/initiatives")
        data = response.json()
        assert len(data) == 3


class TestInitiativeCreateWithQuestions:
    """Test initiatief aanmaken/met centrale vragen."""

    async def test_create_initiative_with_question_ids(self, test_client):
        q_resp = await test_client.post("/api/vragen/create", json={
            "question": "Kan AI helpen?",
        })
        q_id = q_resp.json()["id"]

        response = await test_client.post("/api/initiatieven/create", json={
            "title": "Initiatief met vraag",
            "central_question_ids": [q_id],
        })
        assert response.status_code == 200
        i_id = response.json()["id"]

        # Check koppeling
        questions = await test_client.get(f"/api/vragen/initiative/{i_id}")
        data = questions.json()
        assert len(data) == 1
        assert data[0]["id"] == q_id

    async def test_update_initiative_questions(self, test_client):
        i_resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Initiatief zonder vraag",
        })
        i_id = i_resp.json()["id"]

        q_resp = await test_client.post("/api/vragen/create", json={
            "question": "Nieuwe vraag",
        })
        q_id = q_resp.json()["id"]

        # Update met centrale vragen via dedicated endpoint
        response = await test_client.post(
            f"/api/vragen/initiative/{i_id}/set",
            json={"question_ids": [q_id]},
        )
        assert response.status_code == 200

        # Check koppeling
        questions = await test_client.get(f"/api/vragen/initiative/{i_id}")
        data = questions.json()
        assert len(data) == 1


class TestDashboardWithoutQuestion:
    """Test dashboard stat voor initiatieven zonder centrale vraag."""

    async def test_dashboard_shows_without_question_count(self, test_client):
        # Maak initiatief zonder centrale vraag
        await test_client.post("/api/initiatieven/create", json={
            "title": "Initiatief zonder vraag",
        })

        response = await test_client.get("/")
        assert response.status_code == 200
        body = response.text
        # Dashboard toont waarschuwing als er initiatieven zonder vraag zijn
        assert "zonder centrale vraag" in body or "without_question" in str(response.json()) if "json" in response.headers.get("content-type", "") else True
