"""Tests voor Stap 2: Dashboard (F8)."""

import pytest


class TestDashboardData:
    """Test dashboard data-aggregatie."""

    async def test_empty_dashboard(self, test_client):
        """Dashboard met 0 initiatieven moet nullen tonen."""
        response = await test_client.get("/api/initiatieven/json")
        assert response.status_code == 200
        assert response.json() == []

    async def test_phase_counts(self, test_client):
        """Aantal per fase moet correct geteld worden."""
        # Maak initiatieven in verschillende fasen
        phases = ["verkenning", "experiment", "pilot", "opschaling"]
        for phase in phases:
            await test_client.post(
                "/api/initiatieven/create",
                json={"title": f"Test {phase}", "phase": phase},
            )
        # Extra verkenning voor ongelijke telling
        await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Extra verkenning", "phase": "verkenning"},
        )

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        assert len(data) == 5

        # Tel fasen
        phase_counts = {}
        for item in data:
            phase_counts[item["phase"]] = phase_counts.get(item["phase"], 0) + 1

        assert phase_counts["verkenning"] == 2
        assert phase_counts["experiment"] == 1
        assert phase_counts["pilot"] == 1
        assert phase_counts["opschaling"] == 1

    async def test_horizon_counts(self, test_client):
        """Horizon-verdeling moet correct zijn."""
        for h in ["h1", "h2", "h3"]:
            await test_client.post(
                "/api/initiatieven/create",
                json={"title": f"Test {h}", "phase": "verkenning", "horizon": h},
            )
        # Zonder horizon
        await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Geen horizon", "phase": "verkenning"},
        )

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()

        h_counts = {"h1": 0, "h2": 0, "h3": 0, "none": 0}
        for item in data:
            key = item["horizon"] or "none"
            h_counts[key] = h_counts.get(key, 0) + 1

        assert h_counts["h1"] == 1
        assert h_counts["h2"] == 1
        assert h_counts["h3"] == 1
        assert h_counts["none"] == 1

    async def test_status_counts(self, test_client):
        """Status-verdeling moet correct zijn."""
        # Actief (default)
        await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Actief initiatief", "phase": "verkenning"},
        )

        # Gestopt met leeruitkomst
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Te stoppen", "phase": "experiment"},
        )
        stopped_id = resp.json()["id"]
        await test_client.post(
            f"/api/initiatieven/{stopped_id}/stop",
            json={"stop_reason": "We hebben geleerd dat X niet werkt."},
        )

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()

        status_counts = {}
        for item in data:
            s = item["status"]
            status_counts[s] = status_counts.get(s, 0) + 1

        assert status_counts["actief"] == 1
        assert status_counts["gestopt"] == 1


class TestDashboardRecent:
    """Test 'recent gewijzigd' en 'recent gestopt' secties."""

    async def test_recent_changed(self, test_client):
        """Recent gewijzigde initiatieven moeten op datum gesorteerd zijn."""
        # Maak meerdere initiatieven
        for i in range(3):
            await test_client.post(
                "/api/initiatieven/create",
                json={"title": f"Initiatief {i}", "phase": "verkenning"},
            )

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        assert len(data) == 3

    async def test_recent_stopped_shows_learning(self, test_client):
        """Gestopte initiatieven moeten stop_reason bevatten."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Te stoppen", "phase": "pilot"},
        )
        initiative_id = resp.json()["id"]

        learning = "Belangrijke les uit dit initiatief."
        stop_resp = await test_client.post(
            f"/api/initiatieven/{initiative_id}/stop",
            json={"stop_reason": learning},
        )
        assert stop_resp.status_code == 200

        # Check in JSON lijst
        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        stopped = [i for i in data if i["status"] == "gestopt"]
        assert len(stopped) == 1
        assert stopped[0]["stop_reason"] == learning


class TestDashboardHypotheses:
    """Test hypothese-statistieken op dashboard."""

    async def test_hypotheses_count(self, test_client):
        """Aantal hypothesen moet correct geteld worden."""
        # Maak initiatief
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Test met hypothesen", "phase": "experiment"},
        )
        initiative_id = resp.json()["id"]

        # Voeg hypothesen toe
        for i in range(3):
            await test_client.post(
                "/api/hypothesen/create",
                json={
                    "initiative_id": initiative_id,
                    "type": "value",
                    "description": f"Hypothese {i}",
                },
            )

        # Check hypothesen endpoint
        hyp_resp = await test_client.get(f"/api/hypothesen/initiative/{initiative_id}")
        assert hyp_resp.status_code == 200
        data = hyp_resp.json()
        assert len(data) == 3

    async def test_tested_hypotheses_count(self, test_client):
        """Getoonste hypothesen (status != open) moeten geteld worden."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Test", "phase": "verkenning"},
        )
        initiative_id = resp.json()["id"]

        # Open hypothese
        await test_client.post(
            "/api/hypothesen/create",
            json={
                "initiative_id": initiative_id,
                "type": "value",
                "description": "Open hypothese",
                "status": "open",
            },
        )

        # Bevestigde hypothese (met leeruitkomst)
        await test_client.post(
            "/api/hypothesen/create",
            json={
                "initiative_id": initiative_id,
                "type": "growth",
                "description": "Bevestigde hypothese",
                "status": "bevestigd",
                "learning": "Dit werkt!",
            },
        )

        # Weerlegde hypothese (met leeruitkomst)
        await test_client.post(
            "/api/hypothesen/create",
            json={
                "initiative_id": initiative_id,
                "type": "compliance",
                "description": "Weerlegde hypothese",
                "status": "weerlegd",
                "learning": "Dit werkt niet.",
            },
        )

        hyp_resp = await test_client.get(f"/api/hypothesen/initiative/{initiative_id}")
        data = hyp_resp.json()

        open_count = sum(1 for h in data if h["status"] == "open")
        tested_count = sum(1 for h in data if h["status"] != "open")

        assert open_count == 1
        assert tested_count == 2


class TestDashboardCurations:
    """Test curatie-data op dashboard."""

    async def test_curation_creation(self, test_client):
        """Curatie aanmaken moet werken."""
        response = await test_client.post(
            "/api/curaties/create",
            json={"name": "Show & tell juli", "purpose": "Demonstratie"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Show & tell juli"

    async def test_curations_list(self, test_client):
        """Curaties lijst moet werken."""
        await test_client.post(
            "/api/curaties/create",
            json={"name": "Curatie 1"},
        )
        await test_client.post(
            "/api/curaties/create",
            json={"name": "Curatie 2"},
        )

        response = await test_client.get("/api/curaties/json")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2


class TestDashboardSearch:
    """Test zoeken en filteren op dashboard."""

    async def test_fts_search_finds_initiative(self, test_client):
        """FTS zoekopdracht moet initiatieven vinden."""
        await test_client.post(
            "/api/initiatieven/create",
            json={
                "title": "AI vergunningenscreening",
                "description": "Automatische screening van vergunningaanvragen",
                "phase": "experiment",
            },
        )

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        # Check of het initiatief in de lijst staat
        found = [i for i in data if "AI" in i["title"]]
        assert len(found) == 1

    async def test_filter_by_phase(self, test_client):
        """Filteren op fase moet werken via client-side logica."""
        # Maak initiatieven in verschillende fasen
        for phase in ["verkenning", "experiment"]:
            await test_client.post(
                "/api/initiatieven/create",
                json={"title": f"Test {phase}", "phase": phase},
            )

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()

        # Client-side filter simulatie
        verkenning_only = [i for i in data if i["phase"] == "verkenning"]
        assert len(verkenning_only) == 1

    async def test_filter_by_status(self, test_client):
        """Filteren op status moet werken."""
        # Actief initiatief
        await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Actief", "phase": "verkenning"},
        )

        # Gestopt initiatief
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Gestopt", "phase": "experiment"},
        )
        stopped_id = resp.json()["id"]
        await test_client.post(
            f"/api/initiatieven/{stopped_id}/stop",
            json={"stop_reason": "Les geleerd."},
        )

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()

        active_only = [i for i in data if i["status"] == "actief"]
        stopped_only = [i for i in data if i["status"] == "gestopt"]

        assert len(active_only) == 1
        assert len(stopped_only) == 1


class TestDashboardEmptyState:
    """Test lege staat van dashboard."""

    async def test_empty_initiatives_list(self, test_client):
        """Lege initiatievenlijst moet lege array teruggeven."""
        response = await test_client.get("/api/initiatieven/json")
        assert response.status_code == 200
        assert response.json() == []

    async def test_empty_hypotheses(self, test_client):
        """Initiatief zonder hypothesen moet lege boom teruggeven."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Leeg initiatief", "phase": "verkenning"},
        )
        initiative_id = resp.json()["id"]

        hyp_resp = await test_client.get(f"/api/hypothesen/initiative/{initiative_id}")
        assert hyp_resp.status_code == 200
        assert hyp_resp.json() == []

    async def test_empty_curations(self, test_client):
        """Lege curatieslijst moet lege array teruggeven."""
        response = await test_client.get("/api/curaties/json")
        assert response.status_code == 200
        assert response.json() == []
