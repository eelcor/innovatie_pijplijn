"""Tests voor Stap 1: Projectopzet & database."""

import pytest


class TestDatabaseSetup:
    """Test of de database correct wordt opgezet."""

    def test_tables_exist(self, test_db_engine):
        """Alle tabellen uit het datamodel moeten bestaan."""
        engine, Session, _ = test_db_engine
        from app.models import (
            Initiative, Hypothesis, DossierNote, DossierFile,
            Curation, CurationItem,
        )

        session = Session()

        # Test dat we kunnen schrijven en lezen in elke tabel
        init = Initiative(title="Test", phase="verkenning")
        session.add(init)
        session.commit()
        assert init.id is not None
        assert init.phase == "verkenning"
        assert init.status == "actief"
        assert init.created_at is not None

        # Hypothesis
        hyp = Hypothesis(
            initiative_id=init.id, type="value", description="Test hypothese"
        )
        session.add(hyp)
        session.commit()
        assert hyp.id is not None
        assert hyp.status == "open"

        # Sub-hypothesis (self-referencing)
        sub = Hypothesis(
            initiative_id=init.id,
            parent_hypothesis_id=hyp.id,
            type="value",
            description="Sub hypothese",
        )
        session.add(sub)
        session.commit()
        assert sub.id is not None
        assert sub.parent_hypothesis_id == hyp.id

        # DossierNote
        note = DossierNote(initiative_id=init.id, title="Notitie", body="Body")
        session.add(note)
        session.commit()
        assert note.id is not None

        # Curation
        cur = Curation(name="Test Curatie")
        session.add(cur)
        session.commit()
        assert cur.id is not None

        # CurationItem
        item = CurationItem(
            curation_id=cur.id, initiative_id=init.id, position=1
        )
        session.add(item)
        session.commit()
        assert item.id is not None
        assert item.position == 1

        session.close()

    def test_enum_values(self, test_db_engine):
        """Enum waarden moeten overeenkomen met de PRD."""
        engine, Session, _ = test_db_engine
        from app.models import Initiative, Hypothesis

        session = Session()

        # Test phase enum
        for phase in ["verkenning", "experiment", "pilot", "opschaling"]:
            init = Initiative(title=f"Test {phase}", phase=phase)
            session.add(init)
        session.commit()
        assert True

        # Test hypothesis type enum
        for htype in ["value", "growth", "compliance"]:
            init = session.query(Initiative).first()
            hyp = Hypothesis(
                initiative_id=init.id, type=htype, description=f"Test {htype}"
            )
            session.add(hyp)
        session.commit()
        assert True

        # Test hypothesis status enum
        for status in ["open", "bevestigd", "weerlegd", "vervallen"]:
            hyp = session.query(Hypothesis).first()
            hyp.status = status
        session.commit()
        assert True

        # Test initiative status enum
        for status in ["actief", "gestopt", "afgerond"]:
            init = session.query(Initiative).first()
            init.status = status
        session.commit()
        assert True

        # Test horizon enum
        for h in ["h1", "h2", "h3"]:
            init = session.query(Initiative).first()
            init.horizon = h
        session.commit()
        assert True

        session.close()


class TestFTS5:
    """Test FTS5 full-text search functionaliteit."""

    def test_fts_table_created(self, test_db_engine):
        """FTS5 tabel moet bestaan na initialisatie."""
        engine, Session, _ = test_db_engine
        from app.search import create_fts_table
        from sqlalchemy import text

        session = Session()
        create_fts_table(session)

        result = session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='search_index'")
        ).fetchone()
        assert result is not None, "FTS5 tabel 'search_index' niet gevonden"
        session.close()

    def test_fts_search(self, test_db_engine):
        """Zoeken moet resultaten opleveren."""
        engine, Session, _ = test_db_engine
        from app.models import Initiative
        from app.search import create_fts_table, update_fts_initiative, search

        session = Session()
        create_fts_table(session)

        # Maak initiatief aan en voeg toe aan FTS index
        init = Initiative(title="AI vergunningen", description="Automatische screening")
        session.add(init)
        session.commit()

        update_fts_initiative(session, init.id, init.title, init.description)

        # Zoeken moet resultaat geven
        results = search(session, "vergunningen")
        assert len(results) > 0, "Zoekopdracht 'vergunningen' gaf geen resultaten"
        assert results[0][0] == init.id

        # Niet-matchende zoekopdracht
        results = search(session, "xyz123nietbestaand")
        assert len(results) == 0

        session.close()


class TestAPIEndpoints:
    """Test API endpoints (JSON only, geen templates)."""

    async def test_create_initiative(self, test_client):
        """Initiatief aanmaken moet werken."""
        response = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Test Initiatief", "phase": "verkenning"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        assert data["title"] == "Test Initiatief"

    async def test_create_initiative_requires_title(self, test_client):
        """Initiatief zonder titel moet falen."""
        response = await test_client.post(
            "/api/initiatieven/create",
            json={"phase": "verkenning"},
        )
        assert response.status_code == 422

    async def test_initiatieven_json(self, test_client):
        """JSON endpoint moet lijst teruggeven."""
        # Maak eerst een initiatief
        await test_client.post(
            "/api/initiatieven/create",
            json={"title": "JSON Test", "phase": "experiment"},
        )
        response = await test_client.get("/api/initiatieven/json")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    async def test_update_initiative(self, test_client):
        """Initiatief bijwerken moet werken."""
        # Maak initiatief
        create_resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Originele titel", "phase": "verkenning"},
        )
        initiative_id = create_resp.json()["id"]

        # Werk bij
        update_resp = await test_client.put(
            f"/api/initiatieven/{initiative_id}",
            json={"title": "Gewijzigde titel", "phase": "experiment"},
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["title"] == "Gewijzigde titel"
        assert data["phase"] == "experiment"

    async def test_stop_requires_reason(self, test_client):
        """Stoppen zonder leeruitkomst moet falen."""
        create_resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Te stoppen", "phase": "verkenning"},
        )
        initiative_id = create_resp.json()["id"]

        # Probeer te stoppen zonder reden via PUT
        stop_resp = await test_client.put(
            f"/api/initiatieven/{initiative_id}",
            json={"status": "gestopt"},
        )
        assert stop_resp.status_code == 400

    async def test_stop_with_reason(self, test_client):
        """Stoppen met leeruitkomst moet werken."""
        create_resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Te stoppen", "phase": "verkenning"},
        )
        initiative_id = create_resp.json()["id"]

        stop_resp = await test_client.post(
            f"/api/initiatieven/{initiative_id}/stop",
            json={"stop_reason": "We hebben geleerd dat X niet werkt."},
        )
        assert stop_resp.status_code == 200
        data = stop_resp.json()
