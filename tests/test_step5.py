"""Tests voor Stap 5: Dossier — notities + bestanden (F4)."""

import pytest


class TestDossierNotes:
    """Test dossiernotities."""

    async def test_create_note(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        response = await test_client.post("/api/dossier/notes/create", json={
            "initiative_id": init_id,
            "title": "Eerste notitie",
            "body": "Dit is de inhoud van de notitie.",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        assert data["title"] == "Eerste notitie"
        assert data["body"] == "Dit is de inhoud van de notitie."
        assert data["created_at"] is not None

    async def test_create_note_without_title(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        response = await test_client.post("/api/dossier/notes/create", json={
            "initiative_id": init_id,
            "body": "Notitie zonder titel.",
        })
        assert response.status_code == 200

    async def test_create_note_requires_body(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        response = await test_client.post("/api/dossier/notes/create", json={
            "initiative_id": init_id,
            "title": "Lege notitie",
        })
        assert response.status_code == 422

    async def test_update_note(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        note_resp = await test_client.post("/api/dossier/notes/create", json={
            "initiative_id": init_id,
            "title": "Originele titel",
            "body": "Originele inhoud.",
        })
        note_id = note_resp.json()["id"]

        response = await test_client.put(f"/api/dossier/notes/{note_id}", json={
            "title": "Gewijzigde titel",
            "body": "Gewijzigde inhoud.",
        })
        assert response.status_code == 200

    async def test_delete_note(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        note_resp = await test_client.post("/api/dossier/notes/create", json={
            "initiative_id": init_id,
            "body": "Te verwijderen.",
        })
        note_id = note_resp.json()["id"]

        response = await test_client.delete(f"/api/dossier/notes/{note_id}")
        assert response.status_code == 200

    async def test_delete_nonexistent_note(self, test_client):
        response = await test_client.delete("/api/dossier/notes/nonexistent-id")
        assert response.status_code == 404

    async def test_get_notes_per_initiative(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        for i in range(3):
            await test_client.post("/api/dossier/notes/create", json={
                "initiative_id": init_id,
                "body": f"Notitie {i}",
            })

        response = await test_client.get(f"/api/dossier/notes/{init_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    async def test_get_notes_sorted_desc(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        for i in range(3):
            await test_client.post("/api/dossier/notes/create", json={
                "initiative_id": init_id,
                "body": f"Notitie {i}",
            })

        response = await test_client.get(f"/api/dossier/notes/{init_id}")
        data = response.json()
        # Moet aflopend op datum
        timestamps = [n["created_at"] for n in data]
        assert timestamps == sorted(timestamps, reverse=True)

    async def test_get_empty_notes(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        response = await test_client.get(f"/api/dossier/notes/{init_id}")
        assert response.status_code == 200
        assert response.json() == []


class TestDossierFiles:
    """Test dossierbestanden."""

    async def test_upload_file(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        file_content = b"Test bestand inhoud"
        response = await test_client.post(
            f"/api/dossier/files/upload/{init_id}",
            files={"file": ("test.txt", file_content, "text/plain")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        assert data["filename"] == "test.txt"
        assert data["file_size"] == len(file_content)

    async def test_upload_file_preserves_name(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        response = await test_client.post(
            f"/api/dossier/files/upload/{init_id}",
            files={"file": ("rapport.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert response.status_code == 200
        assert response.json()["filename"] == "rapport.pdf"

    async def test_get_files_per_initiative(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        for i in range(2):
            await test_client.post(
                f"/api/dossier/files/upload/{init_id}",
                files={"file": (f"bestand_{i}.txt", b"inhoud", "text/plain")},
            )

        response = await test_client.get(f"/api/dossier/files/{init_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    async def test_get_empty_files(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        response = await test_client.get(f"/api/dossier/files/{init_id}")
        assert response.status_code == 200
        assert response.json() == []

    async def test_delete_file(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        upload_resp = await test_client.post(
            f"/api/dossier/files/upload/{init_id}",
            files={"file": ("te_verwijderen.txt", b"inhoud", "text/plain")},
        )
        file_id = upload_resp.json()["id"]

        response = await test_client.delete(f"/api/dossier/files/{file_id}")
        assert response.status_code == 200

    async def test_delete_nonexistent_file(self, test_client):
        response = await test_client.delete("/api/dossier/files/nonexistent-id")
        assert response.status_code == 404
