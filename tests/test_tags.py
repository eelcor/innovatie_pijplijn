"""Tests voor H2-1: Tags op initiatieven en centrale vragen."""

import pytest


class TestTagCrud:
    """Test Tag CRUD operaties."""

    async def test_create_tag(self, test_client):
        response = await test_client.post("/api/tags/create", json={
            "name": "Nieuwe tag",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        assert data["name"] == "nieuwe tag"  # wordt lowercase
        assert data["already_exists"] is False

    async def test_create_tag_duplicate(self, test_client):
        r1 = await test_client.post("/api/tags/create", json={"name": "Unieke tag"})
        assert r1.status_code == 200

        r2 = await test_client.post("/api/tags/create", json={"name": "Unieke tag"})
        data = r2.json()
        assert data["already_exists"] is True
        assert data["id"] == r1.json()["id"]

    async def test_create_tag_requires_name(self, test_client):
        response = await test_client.post("/api/tags/create", json={})
        # Pydantic schema validatie geeft 422 (Unprocessable Entity)
        assert response.status_code in (400, 422)

    async def test_create_tag_lowercase(self, test_client):
        """Tag naam wordt automatisch lowercase."""
        response = await test_client.post("/api/tags/create", json={"name": "TEST-LABEL-123"})
        data = response.json()
        assert data["name"] == "test-label-123"

    async def test_update_tag(self, test_client):
        create = await test_client.post("/api/tags/create", json={"name": "Originele tag"})
        tag_id = create.json()["id"]

        response = await test_client.put(f"/api/tags/{tag_id}", json={
            "name": "Gewijzigde tag",
        })
        assert response.status_code == 200
        assert response.json()["name"] == "gewijzigde tag"

    async def test_update_tag_duplicate_name(self, test_client):
        """Kan niet hernoemen naar bestaande tag naam."""
        t1 = await test_client.post("/api/tags/create", json={"name": "Unieke tag A"})
        t2 = await test_client.post("/api/tags/create", json={"name": "Unieke tag B"})

        # Probeer Tag B te hernoemen naar Tag A
        response = await test_client.put(f"/api/tags/{t2.json()['id']}", json={
            "name": "Unieke tag A",
        })
        assert response.status_code == 409

    async def test_soft_delete_tag(self, test_client):
        create = await test_client.post("/api/tags/create", json={"name": "Te verwijderen"})
        tag_id = create.json()["id"]

        response = await test_client.delete(f"/api/tags/{tag_id}")
        assert response.status_code == 200

        # Niet meer in lijst (alleen actieve tags)
        list_resp = await test_client.get("/api/tags/json")
        tag_list = list_resp.json()
        assert not any(t["id"] == tag_id for t in tag_list)


class TestTagList:
    """Test Tag overzicht."""

    async def test_list_tags(self, test_client):
        # Maak tag aan voor de lijst-test (geen seed data in test DB)
        await test_client.post("/api/tags/create", json={"name": "Lijst test tag"})

        response = await test_client.get("/api/tags/json")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    async def test_tag_with_counts(self, test_client):
        """Tags tonen correct aantal initiatieven en vragen."""
        # Maak tag + initiatief
        tag_resp = await test_client.post("/api/tags/create", json={"name": "Test tag"})
        tag_id = tag_resp.json()["id"]

        await test_client.post("/api/initiatieven/create", json={
            "title": "Initiatief met tag",
            "tag_ids": [tag_id],
        })

        response = await test_client.get("/api/tags/json")
        data = response.json()
        tag = next(t for t in data if t["id"] == tag_id)
        assert tag["initiative_count"] >= 1
        assert tag["question_count"] >= 0


class TestTagInitiativeLink:
    """Test koppeling tussen initiatief en tags."""

    async def test_create_initiative_with_tags(self, test_client):
        # Maak tag
        tag_resp = await test_client.post("/api/tags/create", json={"name": "Test tag"})
        tag_id = tag_resp.json()["id"]

        # Maak initiatief met tag
        response = await test_client.post("/api/initiatieven/create", json={
            "title": "Initiatief met tag",
            "tag_ids": [tag_id],
        })
        assert response.status_code == 200
        init_id = response.json()["id"]

        # Check via JSON endpoint
        json_resp = await test_client.get(f"/api/initiatieven/{init_id}")
        data = json_resp.json()
        assert tag_id in data["tag_ids"]

    async def test_update_initiative_tags(self, test_client):
        init_resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Initiatief zonder tags",
        })
        init_id = init_resp.json()["id"]

        # Maak tag
        tag_resp = await test_client.post("/api/tags/create", json={"name": "Nieuwe tag"})
        tag_id = tag_resp.json()["id"]

        # Update met tag_ids
        response = await test_client.put(f"/api/initiatieven/{init_id}", json={
            "tag_ids": [tag_id],
        })
        assert response.status_code == 200

        json_resp = await test_client.get(f"/api/initiatieven/{init_id}")
        data = json_resp.json()
        assert tag_id in data["tag_ids"]

    async def test_replace_initiative_tags(self, test_client):
        """Nieuwe tag_ids vervangt bestaande tags."""
        t1 = await test_client.post("/api/tags/create", json={"name": "Unieke Tag 1"})
        t2 = await test_client.post("/api/tags/create", json={"name": "Unieke Tag 2"})

        init_resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Initiatief met tags",
            "tag_ids": [t1.json()["id"]],
        })
        init_id = init_resp.json()["id"]

        # Vervang door Tag 2
        response = await test_client.put(f"/api/initiatieven/{init_id}", json={
            "tag_ids": [t2.json()["id"]],
        })
        assert response.status_code == 200

        json_resp = await test_client.get(f"/api/initiatieven/{init_id}")
        data = json_resp.json()
        assert t1.json()["id"] not in data["tag_ids"]
        assert t2.json()["id"] in data["tag_ids"]

    async def test_remove_all_tags(self, test_client):
        """Lege tag_ids verwijdert alle tags."""
        tag_resp = await test_client.post("/api/tags/create", json={"name": "Tag"})
        tag_id = tag_resp.json()["id"]

        init_resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Initiatief met tag",
            "tag_ids": [tag_id],
        })
        init_id = init_resp.json()["id"]

        # Verwijder alle tags
        response = await test_client.put(f"/api/initiatieven/{init_id}", json={
            "tag_ids": [],
        })
        assert response.status_code == 200

        json_resp = await test_client.get(f"/api/initiatieven/{init_id}")
        data = json_resp.json()
        assert data["tag_ids"] == []


class TestTagQuestionLink:
    """Test koppeling tussen centrale vraag en tags."""

    async def test_create_question_with_tags(self, test_client):
        tag_resp = await test_client.post("/api/tags/create", json={"name": "Vraag tag"})
        tag_id = tag_resp.json()["id"]

        response = await test_client.post("/api/vragen/create", json={
            "question": "Test vraag met tags?",
            "tag_ids": [tag_id],
        })
        assert response.status_code == 200

    async def test_update_question_tags(self, test_client):
        question_resp = await test_client.post("/api/vragen/create", json={
            "question": "Test vraag zonder tags?",
        })
        question_id = question_resp.json()["id"]

        tag_resp = await test_client.post("/api/tags/create", json={"name": "Vraag tag"})
        tag_id = tag_resp.json()["id"]

        response = await test_client.put(f"/api/vragen/{question_id}", json={
            "tag_ids": [tag_id],
        })
        assert response.status_code == 200


class TestTagFilter:
    """Test filteren op tags."""

    async def test_filter_initiatives_by_tag(self, test_client):
        tag_resp = await test_client.post("/api/tags/create", json={"name": "Filter tag"})
        tag_id = tag_resp.json()["id"]

        # Maak initiatief met tag
        await test_client.post("/api/initiatieven/create", json={
            "title": "Initiatief met filter tag",
            "tag_ids": [tag_id],
        })

        # Maak initiatief zonder tag
        await test_client.post("/api/initiatieven/create", json={
            "title": "Initiatief zonder filter tag",
        })

        # Filter op tag
        response = await test_client.get(f"/api/initiatieven/filter?tag_id={tag_id}")
        data = response.json()
        assert len(data["initiatives"]) >= 1
        titles = [i["title"] for i in data["initiatives"]]
        assert "Initiatief met filter tag" in titles
        assert "Initiatief zonder filter tag" not in titles


class TestTagDetailPage:
    """Test tag detail API."""

    async def test_tag_not_found(self, test_client):
        response = await test_client.get("/api/tags/nonexistent-id")
        assert response.status_code == 404
