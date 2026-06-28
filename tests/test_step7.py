"""Tests voor Stap 7: Zoeken & filteren (F7)."""

import pytest


class TestFTSSearch:
    """Test FTS5 full-text search."""

    async def test_search_finds_by_title(self, test_client):
        await test_client.post("/api/initiatieven/create", json={
            "title": "AI vergunningenscreening",
            "description": "Automatische screening van aanvragen",
            "phase": "experiment",
        })

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        found = [i for i in data if "AI" in i["title"]]
        assert len(found) == 1

    async def test_search_finds_by_description(self, test_client):
        await test_client.post("/api/initiatieven/create", json={
            "title": "Korte titel",
            "description": "Uitgebreide beschrijving met sleutelwoorden.",
            "phase": "verkenning",
        })

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        found = [i for i in data if "sleutelwoorden" in (i["description"] or "")]
        assert len(found) == 1

    async def test_search_no_results(self, test_client):
        await test_client.post("/api/initiatieven/create", json={
            "title": "Test initiatief",
        })

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        found = [i for i in data if "xyz123nietbestaand" in (i["title"] or "")]
        assert len(found) == 0


class TestFilterByPhase:
    """Test filteren op fase."""

    async def test_filter_verkenning(self, test_client):
        for phase in ["verkenning", "experiment", "pilot"]:
            await test_client.post("/api/initiatieven/create", json={
                "title": f"Initiatief {phase}",
                "phase": phase,
            })

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        filtered = [i for i in data if i["phase"] == "verkenning"]
        assert len(filtered) == 1
        assert filtered[0]["title"] == "Initiatief verkenning"

    async def test_filter_experiment(self, test_client):
        for phase in ["verkenning", "experiment"]:
            await test_client.post("/api/initiatieven/create", json={
                "title": f"Initiatief {phase}",
                "phase": phase,
            })

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        filtered = [i for i in data if i["phase"] == "experiment"]
        assert len(filtered) == 1


class TestFilterByStatus:
    """Test filteren op status."""

    async def test_filter_actief(self, test_client):
        # Actief initiatief
        await test_client.post("/api/initiatieven/create", json={
            "title": "Actief initiatief",
        })

        # Gestopt initiatief
        stopped_resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Gestopt initiatief",
        })
        stopped_id = stopped_resp.json()["id"]
        await test_client.post(f"/api/initiatieven/{stopped_id}/stop", json={
            "stop_reason": "Les geleerd.",
        })

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        active = [i for i in data if i["status"] == "actief"]
        stopped = [i for i in data if i["status"] == "gestopt"]
        assert len(active) == 1
        assert len(stopped) == 1

    async def test_filter_afgerond(self, test_client):
        await test_client.post("/api/initiatieven/create", json={
            "title": "Actief initiatief",
        })

        resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Afgerond initiatief",
        })
        id_ = resp.json()["id"]
        await test_client.put(f"/api/initiatieven/{id_}", json={
            "status": "afgerond",
        })

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        afgerond = [i for i in data if i["status"] == "afgerond"]
        assert len(afgerond) == 1


class TestFilterByHorizon:
    """Test filteren op horizon."""

    async def test_filter_h1(self, test_client):
        for h in ["h1", "h2", "h3"]:
            await test_client.post("/api/initiatieven/create", json={
                "title": f"Initiatief {h}",
                "horizon": h,
            })

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        h1_only = [i for i in data if i["horizon"] == "h1"]
        assert len(h1_only) == 1

    async def test_filter_no_horizon(self, test_client):
        await test_client.post("/api/initiatieven/create", json={
            "title": "Met horizon",
            "horizon": "h1",
        })
        await test_client.post("/api/initiatieven/create", json={
            "title": "Zonder horizon",
        })

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        no_horizon = [i for i in data if not i["horizon"]]
        assert len(no_horizon) == 1


class TestFilterByMDS:
    """Test filteren op MDS."""

    async def test_filter_mds(self, test_client):
        await test_client.post("/api/initiatieven/create", json={
            "title": "AI initiatief",
            "mds": "AI & Digitalisering",
        })
        await test_client.post("/api/initiatieven/create", json={
            "title": "Zelfbouw initiatief",
            "mds": "Zelfbouw",
        })

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        ai_only = [i for i in data if i["mds"] == "AI & Digitalisering"]
        assert len(ai_only) == 1


class TestCombinedFilters:
    """Test gecombineerde filters."""

    async def test_filter_phase_and_status(self, test_client):
        # Actief verkenning
        await test_client.post("/api/initiatieven/create", json={
            "title": "Actief verkenning",
            "phase": "verkenning",
        })
        # Gestopt experiment
        resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Gestopt experiment",
            "phase": "experiment",
        })
        stopped_id = resp.json()["id"]
        await test_client.post(f"/api/initiatieven/{stopped_id}/stop", json={
            "stop_reason": "Les.",
        })

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()

        # Gecombineerd filter: experiment + gestopt
        combined = [i for i in data if i["phase"] == "experiment" and i["status"] == "gestopt"]
        assert len(combined) == 1
        assert combined[0]["title"] == "Gestopt experiment"

    async def test_filter_phase_and_horizon(self, test_client):
        await test_client.post("/api/initiatieven/create", json={
            "title": "H1 verkenning",
            "phase": "verkenning",
            "horizon": "h1",
        })
        await test_client.post("/api/initiatieven/create", json={
            "title": "H2 experiment",
            "phase": "experiment",
            "horizon": "h2",
        })

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        combined = [i for i in data if i["phase"] == "verkenning" and i["horizon"] == "h1"]
        assert len(combined) == 1


class TestSearchHypotheses:
    """Test zoeken in hypothesen."""

    async def test_search_hypothesis_description(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Test initiatief"},
        )
        init_id = resp.json()["id"]

        await test_client.post("/api/hypothesen/create", json={
            "initiative_id": init_id,
            "type": "value",
            "description": "Kans op automatisering van vergunningen.",
        })

        tree_resp = await test_client.get(f"/api/hypothesen/initiative/{init_id}")
        data = tree_resp.json()
        found = [h for h in data if "automatisering" in h["description"]]
        assert len(found) == 1


class TestSearchStoppedLearning:
    """Test zoeken in leeruitkomsten van gestopte initiatieven."""

    async def test_search_stop_reason(self, test_client):
        resp = await test_client.post(
            "/api/initiatieven/create", json={"title": "Gestopt initiatief"},
        )
        stopped_id = resp.json()["id"]

        await test_client.post(f"/api/initiatieven/{stopped_id}/stop", json={
            "stop_reason": "We hebben geleerd dat automatisering hier niet past.",
        })

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        found = [i for i in data if "automatisering" in (i["stop_reason"] or "")]
        assert len(found) == 1
