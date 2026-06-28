"""Tests voor F5: Stoppen met leeruitkomst.

PRD-requirements:
- Status "gestopt" kan alleen worden gezet via een modale dialoog die om de leeruitkomst vraagt.
- Een gestopt initiatief blijft volledig zichtbaar en doorzoekbaar.
- Neutrale UI-taal (geen rood/afval-gevoel).
"""

import pytest


class TestStoppenZonderLeeruitkomst:
    """Stoppen zonder leeruitkomst moet worden tegengehouden."""

    async def test_stop_endpoint_verplichte_leeruitkomst(self, test_client):
        """POST /stop zonder stop_reason geeft 422."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Initiatief A"},
        )
        init_id = resp.json()["id"]

        response = await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={},
        )
        assert response.status_code == 422

    async def test_stop_endpoint_lege_leeruitkomst(self, test_client):
        """POST /stop met lege string geeft 422."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Initiatief B"},
        )
        init_id = resp.json()["id"]

        response = await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={"stop_reason": ""},
        )
        assert response.status_code == 422

    async def test_stop_endpoint_alleen_witruimte(self, test_client):
        """POST /stop met alleen spaties geeft 422."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Initiatief C"},
        )
        init_id = resp.json()["id"]

        response = await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={"stop_reason": "   "},
        )
        assert response.status_code == 422

    async def test_put_gestopt_verplichte_leeruitkomst(self, test_client):
        """PUT met status=gestopt zonder stop_reason geeft 400."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Initiatief D"},
        )
        init_id = resp.json()["id"]

        response = await test_client.put(
            f"/api/initiatieven/{init_id}",
            json={"status": "gestopt"},
        )
        assert response.status_code == 400

    async def test_put_gestopt_met_leeruitkomst_werkt(self, test_client):
        """PUT met status=gestopt én stop_reason werkt."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Initiatief E"},
        )
        init_id = resp.json()["id"]

        response = await test_client.put(
            f"/api/initiatieven/{init_id}",
            json={"status": "gestopt", "stop_reason": "Les geleerd."},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "gestopt"


class TestStoppenMetLeeruitkomst:
    """Stoppen mét leeruitkomst moet correct werken."""

    async def test_stop_met_leeruitkomst(self, test_client):
        """Stoppen met leeruitkomst zet status op gestopt en bewaart reden."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Initiatief F", "phase": "experiment"},
        )
        init_id = resp.json()["id"]

        response = await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={"stop_reason": "We hebben geleerd dat X niet werkt in deze context."},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "gestopt"
        assert data["stop_reason"] == "We hebben geleerd dat X niet werkt in deze context."

    async def test_stop_bewaart_andere_velden(self, test_client):
        """Stoppen mag andere velden van het initiatief niet aanpassen."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={
                "title": "Initiatief G",
                "phase": "pilot",
                "horizon": "h2",
                "mds": "Team AI",
                "owner": "Jan de Vries",
            },
        )
        init_id = resp.json()["id"]

        await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={"stop_reason": "Les geleerd."},
        )

        # Check via JSON endpoint dat alle velden intact zijn
        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        init = next(i for i in data if i["id"] == init_id)

        assert init["title"] == "Initiatief G"
        assert init["phase"] == "pilot"
        assert init["horizon"] == "h2"
        assert init["mds"] == "Team AI"
        assert init["owner"] == "Jan de Vries"
        assert init["status"] == "gestopt"

    async def test_stop_logt_wijziging(self, test_client):
        """Stoppen moet een wijziging loggen in het changes-logboek."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Initiatief H"},
        )
        init_id = resp.json()["id"]

        await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={"stop_reason": "Les geleerd."},
        )

        response = await test_client.get(f"/api/initiatieven/{init_id}/changes")
        assert response.status_code == 200
        changes = response.json()
        status_changes = [c for c in changes if c["field"] == "status"]
        assert any(c["new_value"] == "gestopt" for c in status_changes)

    async def test_stop_niet_bestaand_initiatief(self, test_client):
        """Stoppen van niet-bestaand initiatief geeft 404."""
        response = await test_client.post(
            "/api/initiatieven/nonexistent-id/stop",
            json={"stop_reason": "Les geleerd."},
        )
        assert response.status_code == 404

    async def test_stop_twemaal(self, test_client):
        """Stoppen van een al gestopt initiatief moet nog werken (idempotent)."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Initiatief I"},
        )
        init_id = resp.json()["id"]

        # Eerste keer stoppen
        resp1 = await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={"stop_reason": "Eerste les."},
        )
        assert resp1.status_code == 200

        # Tweede keer stoppen (update leeruitkomst)
        resp2 = await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={"stop_reason": "Geüpdateerde les."},
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["stop_reason"] == "Geüpdateerde les."


class TestGestoptBlijftZichtbaar:
    """Een gestopt initiatief blijft volledig zichtbaar en doorzoekbaar."""

    async def test_gestopt_in_lijst(self, test_client):
        """Gestopt initiatief staat in de JSON-lijst van alle initiatieven."""
        # Maak actief en gestopt initiatief
        await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Actief initiatief"},
        )
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Gestopt initiatief"},
        )
        stopped_id = resp.json()["id"]
        await test_client.post(
            f"/api/initiatieven/{stopped_id}/stop",
            json={"stop_reason": "Les geleerd."},
        )

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        assert len(data) == 2
        stopped = [i for i in data if i["status"] == "gestopt"]
        assert len(stopped) == 1
        assert stopped[0]["title"] == "Gestopt initiatief"

    async def test_gestopt_in_dashboard(self, test_client):
        """Gestopt initiatief telt mee in dashboard statistieken."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Gestopt voor dashboard"},
        )
        stopped_id = resp.json()["id"]
        await test_client.post(
            f"/api/initiatieven/{stopped_id}/stop",
            json={"stop_reason": "Les geleerd."},
        )

        response = await test_client.get("/")
        assert response.status_code == 200
        body = response.text
        # Dashboard toont gestopt initiatief in stats
        assert "Gestopt (met leeruitkomst)" in body

    async def test_gestopt_in_recent_stopped(self, test_client):
        """Gestopt initiatief met leeruitkomst verschijnt in 'recent gestopt' sectie."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Net gestopt"},
        )
        stopped_id = resp.json()["id"]
        await test_client.post(
            f"/api/initiatieven/{stopped_id}/stop",
            json={"stop_reason": "Belangrijke les over gebruikersbehoeften."},
        )

        response = await test_client.get("/")
        body = response.text
        assert "Net gestopt" in body
        assert "Belangrijke les over gebruikersbehoeften" in body

    async def test_gestopt_blijft_doorzoekbaar(self, test_client):
        """Gestopt initiatief is terug te vinden via zoeken op titel."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Uniek gestopt initiatief", "description": "Speciale beschrijving"},
        )
        stopped_id = resp.json()["id"]
        await test_client.post(
            f"/api/initiatieven/{stopped_id}/stop",
            json={"stop_reason": "Les geleerd."},
        )

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        found = [i for i in data if "Uniek gestopt" in i["title"]]
        assert len(found) == 1
        assert found[0]["status"] == "gestopt"

    async def test_gestopt_met_leeruitkomst_in_json(self, test_client):
        """stop_reason is terug te vinden in JSON response van gestopt initiatief."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Met leeruitkomst"},
        )
        stopped_id = resp.json()["id"]
        await test_client.post(
            f"/api/initiatieven/{stopped_id}/stop",
            json={"stop_reason": "Specifieke leeruitkomst voor test."},
        )

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        stopped = next(i for i in data if i["id"] == stopped_id)
        assert stopped["stop_reason"] == "Specifieke leeruitkomst voor test."

    async def test_gestopt_initiatief_detail_toont_leeruitkomst(self, test_client):
        """Detailpagina van gestopt initiatief toont de leeruitkomst."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Gestopt met les"},
        )
        stopped_id = resp.json()["id"]
        await test_client.post(
            f"/api/initiatieven/{stopped_id}/stop",
            json={"stop_reason": "We hebben geleerd dat de markt niet klaar is."},
        )

        response = await test_client.get(f"/api/initiatieven/detail/{stopped_id}")
        assert response.status_code == 200
        body = response.text
        assert "We hebben geleerd dat de markt niet klaar is" in body
        assert "Leeruitkomst" in body

    async def test_gestopt_initiatief_geen_stop_knop(self, test_client):
        """Detailpagina van gestopt initiatief toont geen 'Stoppen' knop."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Al gestopt"},
        )
        stopped_id = resp.json()["id"]
        await test_client.post(
            f"/api/initiatieven/{stopped_id}/stop",
            json={"stop_reason": "Les."},
        )

        response = await test_client.get(f"/api/initiatieven/detail/{stopped_id}")
        body = response.text
        # De 'Stoppen' button moet afwezig zijn (onclick met stop-knop)
        assert 'onclick="openStopModal' not in body
        assert '>Stoppen</button>' not in body

    async def test_gestopt_initiatief_wel_bewerken_knop(self, test_client):
        """Gestopt initiatief kan nog wel bewerkt worden (Bewerken knop zichtbaar)."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Gestopt maar bewerkbaar"},
        )
        stopped_id = resp.json()["id"]
        await test_client.post(
            f"/api/initiatieven/{stopped_id}/stop",
            json={"stop_reason": "Les."},
        )

        response = await test_client.get(f"/api/initiatieven/detail/{stopped_id}")
        body = response.text
        assert "openEditModal" in body


class TestNeutraleUITaal:
    """UI gebruikt neutrale taal voor gestopte initiatieven."""

    async def test_dashboard_neutrale_label(self, test_client):
        """Dashboard gebruikt 'Gestopt (met leeruitkomst)' niet 'Mislukt' of 'Verwijderd'."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Test"},
        )
        stopped_id = resp.json()["id"]
        await test_client.post(
            f"/api/initiatieven/{stopped_id}/stop",
            json={"stop_reason": "Les."},
        )

        response = await test_client.get("/")
        body = response.text
        assert "Gestopt (met leeruitkomst)" in body
        # Geen negatieve taal
        assert "Mislukt" not in body
        assert "Verwijderd" not in body
        assert "Afgevoerd" not in body

    async def test_recent_stopped_neutrale_taal(self, test_client):
        """'Recent gestopt met leeruitkomst' sectie gebruikt positieve/ neutrale taal."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Gestopt initiatief"},
        )
        stopped_id = resp.json()["id"]
        await test_client.post(
            f"/api/initiatieven/{stopped_id}/stop",
            json={"stop_reason": "Les."},
        )

        response = await test_client.get("/")
        body = response.text
        assert "Recent gestopt met leeruitkomst" in body

    async def test_detail_leeruitkomst_label(self, test_client):
        """Detailpagina toont 'Leeruitkomst' label (niet 'Reden voor stoppen')."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Test"},
        )
        stopped_id = resp.json()["id"]
        await test_client.post(
            f"/api/initiatieven/{stopped_id}/stop",
            json={"stop_reason": "Les."},
        )

        response = await test_client.get(f"/api/initiatieven/detail/{stopped_id}")
        body = response.text
        assert "Leeruitkomst" in body


class TestStoppenMetHypothesen:
    """Stoppen van initiatief met hypothesen."""

    async def test_stop_met_hypothesen(self, test_client):
        """Hypothesen blijven behouden na stoppen van initiatief."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Initiatief met hypothesen"},
        )
        init_id = resp.json()["id"]

        # Voeg hypothese toe
        await test_client.post(
            "/api/hypothesen/create",
            json={
                "initiative_id": init_id,
                "type": "value",
                "description": "Test hypothese",
                "status": "open",
            },
        )

        # Stop het initiatief
        await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={"stop_reason": "Les geleerd."},
        )

        # Check dat hypothese nog bestaat (boomstructuur response)
        response = await test_client.get(f"/api/hypothesen/initiative/{init_id}")
        data = response.json()
        assert len(data) == 1
        assert data[0]["description"] == "Test hypothese"
        assert data[0]["status"] == "open"

    async def test_stop_met_bevestigde_hypothese(self, test_client):
        """Initiatief met bevestigde hypothese kan gestopt worden."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Met bevestigde hypothese"},
        )
        init_id = resp.json()["id"]

        await test_client.post(
            "/api/hypothesen/create",
            json={
                "initiative_id": init_id,
                "type": "value",
                "description": "Bevestigde hypothese",
                "status": "bevestigd",
                "learning": "Dit werkt!",
            },
        )

        response = await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={"stop_reason": "Ondanks bevestigde hypothese: context veranderd."},
        )
        assert response.status_code == 200


class TestStoppenPerFase:
    """Stoppen is mogelijk in elke fase."""

    async def test_stop_in_verkenning(self, test_client):
        """Initiatief in verkenningsfase kan gestopt worden."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Verkenning stoppen", "phase": "verkenning"},
        )
        init_id = resp.json()["id"]

        response = await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={"stop_reason": "Ideaal niet haalbaar."},
        )
        assert response.status_code == 200

    async def test_stop_in_experiment(self, test_client):
        """Initiatief in experimentfase kan gestopt worden."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Experiment stoppen", "phase": "experiment"},
        )
        init_id = resp.json()["id"]

        response = await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={"stop_reason": "PoC faalde."},
        )
        assert response.status_code == 200

    async def test_stop_in_pilot(self, test_client):
        """Initiatief in pilotfase kan gestopt worden."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Pilot stoppen", "phase": "pilot"},
        )
        init_id = resp.json()["id"]

        response = await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={"stop_reason": "Schaalbaarheid niet bewezen."},
        )
        assert response.status_code == 200

    async def test_stop_in_opschaling(self, test_client):
        """Initiatief in opschalingsfase kan gestopt worden."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Opschaling stoppen", "phase": "opschaling"},
        )
        init_id = resp.json()["id"]

        response = await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={"stop_reason": "Budget gesneefd."},
        )
        assert response.status_code == 200

    async def test_stop_bewaart_originele_fase(self, test_client):
        """Na stoppen blijft de oorspronkelijke fase behouden."""
        resp = await test_client.post(
            "/api/initiatieven/create",
            json={"title": "Fase bewaren", "phase": "pilot"},
        )
        init_id = resp.json()["id"]

        await test_client.post(
            f"/api/initiatieven/{init_id}/stop",
            json={"stop_reason": "Les."},
        )

        response = await test_client.get("/api/initiatieven/json")
        data = response.json()
        init = next(i for i in data if i["id"] == init_id)
        assert init["phase"] == "pilot"
        assert init["status"] == "gestopt"
