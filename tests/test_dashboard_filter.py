"""Tests voor dashboard filter API en dynamische rendering."""

import pytest


class TestFilterAPI:
    """Test server-side filtering van initiatieven."""

    async def test_filter_returns_all_by_default(self, test_client):
        await test_client.post("/api/initiatieven/create", json={"title": "Test A"})
        await test_client.post("/api/initiatieven/create", json={"title": "Test B"})

        response = await test_client.get("/api/initiatieven/filter")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert len(data["initiatives"]) >= 2

    async def test_filter_by_phase(self, test_client):
        await test_client.post("/api/initiatieven/create", json={
            "title": "Verkenning initiatief", "phase": "verkenning"
        })
        await test_client.post("/api/initiatieven/create", json={
            "title": "Pilot initiatief", "phase": "pilot"
        })

        response = await test_client.get("/api/initiatieven/filter?phase=verkenning")
        data = response.json()
        for init in data["initiatives"]:
            assert init["phase"] == "verkenning"

    async def test_filter_by_status(self, test_client):
        await test_client.post("/api/initiatieven/create", json={"title": "Actief"})
        # Default status is 'actief'

        response = await test_client.get("/api/initiatieven/filter?status=actief")
        data = response.json()
        for init in data["initiatives"]:
            assert init["status"] == "actief"

    async def test_filter_gestopt_phase(self, test_client):
        # Maak een gestopt initiatief
        resp = await test_client.post("/api/initiatieven/create", json={"title": "Zal stoppen"})
        init_id = resp.json()["id"]
        await test_client.post(f"/api/initiatieven/{init_id}/stop", json={"stop_reason": "Test"})

        response = await test_client.get("/api/initiatieven/filter?phase=gestopt")
        data = response.json()
        for init in data["initiatives"]:
            assert init["status"] == "gestopt"

    async def test_filter_by_horizon(self, test_client):
        await test_client.post("/api/initiatieven/create", json={
            "title": "H1 initiatief", "horizon": "h1"
        })
        await test_client.post("/api/initiatieven/create", json={
            "title": "H2 initiatief", "horizon": "h2"
        })

        response = await test_client.get("/api/initiatieven/filter?horizon=h1")
        data = response.json()
        for init in data["initiatives"]:
            if init["title"] in ("H1 initiatief",):
                assert init["horizon"] == "h1"

    async def test_filter_by_horizon_none(self, test_client):
        await test_client.post("/api/initiatieven/create", json={
            "title": "Geen horizon"
        })

        response = await test_client.get("/api/initiatieven/filter?horizon=none")
        data = response.json()
        for init in data["initiatives"]:
            assert not init["horizon"]

    async def test_filter_search(self, test_client):
        await test_client.post("/api/initiatieven/create", json={
            "title": "Uniek zoektest initiatief",
            "description": "Dit is een beschrijving voor zoeken"
        })

        response = await test_client.get("/api/initiatieven/filter?search=zoektest")
        data = response.json()
        titles = [i["title"] for i in data["initiatives"]]
        assert "Uniek zoektest initiatief" in titles

    async def test_filter_search_in_description(self, test_client):
        await test_client.post("/api/initiatieven/create", json={
            "title": "Korte titel",
            "description": "Specifieke beschrijvings tekst voor zoeken"
        })

        response = await test_client.get("/api/initiatieven/filter?search=beschrijvings")
        data = response.json()
        titles = [i["title"] for i in data["initiatives"]]
        assert "Korte titel" in titles

    async def test_filter_combined(self, test_client):
        await test_client.post("/api/initiatieven/create", json={
            "title": "Combo test", "phase": "pilot", "horizon": "h2"
        })

        response = await test_client.get("/api/initiatieven/filter?phase=pilot&horizon=h2")
        data = response.json()
        for init in data["initiatives"]:
            assert init["phase"] == "pilot"
            assert init["horizon"] == "h2"

    async def test_filter_limit(self, test_client):
        response = await test_client.get("/api/initiatieven/filter?limit=5")
        data = response.json()
        assert len(data["initiatives"]) <= 5

    async def test_filter_total_includes_all_matches(self, test_client):
        # Maak meerdere initiatieven met dezelfde fase
        for i in range(3):
            await test_client.post("/api/initiatieven/create", json={
                "title": f"Filter totaal {i}", "phase": "experiment"
            })

        response = await test_client.get("/api/initiatieven/filter?phase=experiment")
        data = response.json()
        assert data["total"] >= 3

    async def test_filter_empty_result(self, test_client):
        response = await test_client.get("/api/initiatieven/filter?search=uniekezoekterm12345")
        data = response.json()
        # Zou leeg kunnen zijn als geen match
        assert "initiatives" in data
        assert "total" in data

    async def test_filter_sort_by_title(self, test_client):
        await test_client.post("/api/initiatieven/create", json={"title": "Zaardvark"})
        await test_client.post("/api/initiatieven/create", json={"title": "Apple"})

        response = await test_client.get("/api/initiatieven/filter?sort=title&order=asc")
        data = response.json()
        titles = [i["title"] for i in data["initiatives"]]
        if "Apple" in titles and "Zaardvark" in titles:
            assert titles.index("Apple") < titles.index("Zaardvark")


class TestDashboardPage:
    """Test dashboard pagina rendering."""

    async def test_dashboard_renders(self, test_client):
        response = await test_client.get("/")
        assert response.status_code == 200
        html = response.text
        assert "Dashboard" in html
        assert "stats-grid" in html

    async def test_dashboard_shows_recent_initiatives(self, test_client):
        """Dashboard shows last 10 initiatives statically."""
        await test_client.post("/api/initiatieven/create", json={"title": "Recent initiatief"})
        response = await test_client.get("/")
        html = response.text
        assert "Laatste ingevoerde initiatieven" in html
        assert "Recent initiatief" in html

    async def test_initiatives_list_has_filters(self, test_client):
        """Initiatieven list page has filter chips."""
        response = await test_client.get("/api/initiatieven/lijst")
        html = response.text
        assert 'data-filter="phase"' in html
        assert 'data-filter="status"' in html
        assert 'data-filter="horizon"' in html

    async def test_initiatives_list_has_container(self, test_client):
        """Initiatieven list page has dynamic container."""
        response = await test_client.get("/api/initiatieven/lijst")
        html = response.text
        assert 'id="initiatives-container"' in html
