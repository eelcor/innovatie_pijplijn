"""Tests voor Horizon 2: MDS als entiteit en Tags."""

import pytest


class TestMDSCrud:
    """Test MDS CRUD operaties."""

    async def test_create_mds(self, test_client):
        response = await test_client.post("/api/mds/create", json={
            "name": "Nieuw Team",
            "description": "Beschrijving van het team",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        assert data["name"] == "Nieuw Team"
        assert data["already_exists"] is False

    async def test_create_mds_duplicate(self, test_client):
        """Dubbele MDS naam retourneert bestaande record."""
        r1 = await test_client.post("/api/mds/create", json={"name": "Uniek team"})
        assert r1.status_code == 200

        r2 = await test_client.post("/api/mds/create", json={"name": "Uniek team"})
        data = r2.json()
        assert data["already_exists"] is True
        assert data["id"] == r1.json()["id"]

    async def test_create_mds_requires_name(self, test_client):
        response = await test_client.post("/api/mds/create", json={})
        # Pydantic schema validatie geeft 422 (Unprocessable Entity)
        assert response.status_code in (400, 422)

    async def test_update_mds(self, test_client):
        create = await test_client.post("/api/mds/create", json={"name": "Originele naam"})
        mds_id = create.json()["id"]

        response = await test_client.put(f"/api/mds/{mds_id}", json={
            "name": "Gewijzigde naam",
            "description": "Nieuwe beschrijving",
        })
        assert response.status_code == 200
        assert response.json()["name"] == "Gewijzigde naam"

    async def test_soft_delete_mds(self, test_client):
        create = await test_client.post("/api/mds/create", json={"name": "Te verwijderen"})
        mds_id = create.json()["id"]

        response = await test_client.delete(f"/api/mds/{mds_id}")
        assert response.status_code == 200

        # Niet meer in lijst (alleen actieve MDS)
        list_resp = await test_client.get("/api/mds/json")
        mds_list = list_resp.json()
        assert not any(m["id"] == mds_id for m in mds_list)


class TestMDSList:
    """Test MDS overzicht."""

    async def test_list_mds(self, test_client):
        # Maak eerst een MDS aan voor de test
        await test_client.post("/api/mds/create", json={"name": "Test team"})

        response = await test_client.get("/api/mds/json")
        assert response.status_code == 200
        data = response.json()
        # Moet minimaal 1 team bevatten
        assert len(data) >= 1

    async def test_mds_with_initiative_count(self, test_client):
        # Maak MDS + initiatief
        mds_resp = await test_client.post("/api/mds/create", json={"name": "Test team"})
        mds_id = mds_resp.json()["id"]

        init_resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Initiatief met MDS",
            "mds_id": mds_id,
        })
        assert init_resp.status_code == 200

        # Check dat teller correct is
        response = await test_client.get("/api/mds/json")
        data = response.json()
        mds = next(m for m in data if m["id"] == mds_id)
        assert mds["initiative_count"] >= 1


class TestMDSInitiativeLink:
    """Test koppeling tussen initiatief en MDS."""

    async def test_create_initiative_with_mds_id(self, test_client):
        # Maak MDS
        mds_resp = await test_client.post("/api/mds/create", json={"name": "Team A"})
        mds_id = mds_resp.json()["id"]

        # Maak initiatief met mds_id
        response = await test_client.post("/api/initiatieven/create", json={
            "title": "Initiatief met MDS ID",
            "mds_id": mds_id,
        })
        assert response.status_code == 200

        # Check via JSON endpoint
        json_resp = await test_client.get("/api/initiatieven/json")
        data = json_resp.json()
        init = next(i for i in data if i["title"] == "Initiatief met MDS ID")
        assert init["mds_id"] == mds_id

    async def test_update_initiative_mds(self, test_client):
        # Maak initiatief zonder MDS
        init_resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Initiatief zonder MDS",
        })
        init_id = init_resp.json()["id"]

        # Maak MDS
        mds_resp = await test_client.post("/api/mds/create", json={"name": "Team B"})
        mds_id = mds_resp.json()["id"]

        # Update initiatief met MDS
        response = await test_client.put(f"/api/initiatieven/{init_id}", json={
            "mds_id": mds_id,
        })
        assert response.status_code == 200

        # Check via JSON endpoint
        json_resp = await test_client.get("/api/initiatieven/json")
        data = json_resp.json()
        init = next(i for i in data if i["id"] == init_id)
        assert init["mds_id"] == mds_id


class TestTags:
    """Test Tags functionaliteit."""

    async def test_tags_exist_in_database(self, test_client):
        """Check of tags bestaan (vanuit seed)."""
        # Dit is een integratie-test die aannemt dat tags zijn ingezaaid
        response = await test_client.get("/api/initiatieven/json")
        assert response.status_code == 200
        # JSON endpoint moet tag_ids veld hebben
        data = response.json()
        if data:
            assert "tag_ids" in data[0]

    async def test_create_initiative_with_tags(self, test_client):
        """Initiatief aanmaken met tags."""
        # Maak eerst een initiatief om tag_ids te testen
        response = await test_client.post("/api/initiatieven/create", json={
            "title": "Initiatief met tags",
            "tag_ids": [],  # Leeg voor nu, tags moeten bestaan
        })
        assert response.status_code == 200

    async def test_update_initiative_tags(self, test_client):
        """Tags updaten via initiatief bewerken."""
        init_resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Initiatief voor tags",
        })
        init_id = init_resp.json()["id"]

        # Update met tag_ids (leeg voor nu)
        response = await test_client.put(f"/api/initiatieven/{init_id}", json={
            "tag_ids": [],
        })
        assert response.status_code == 200


class TestInitiativeJSONResponse:
    """Test JSON response van initiatieven."""

    async def test_json_includes_mds_id(self, test_client):
        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        if data:
            assert "mds_id" in data[0]

    async def test_json_includes_tag_ids(self, test_client):
        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        if data:
            assert "tag_ids" in data[0]

    async def test_json_includes_central_question_ids(self, test_client):
        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        if data:
            assert "central_question_ids" in data[0]
