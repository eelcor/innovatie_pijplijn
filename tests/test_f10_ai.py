"""Tests voor F10 — AI-curatie-assistent (model-agnostisch).

Testt de AI-client configuratie, alle API endpoints en error handling.
Het daadwerkelijke taalmodel wordt gemockt zodat tests deterministisch zijn.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ====================================================================
# AI Client configuratie-tests
# ====================================================================

class TestAIClientConfig:
    """Test de model-agnostische configuratie."""

    def test_model_url_configurable(self, monkeypatch):
        from app import ai_client
        monkeypatch.setenv("MODEL_URL", "http://custom-server:9000")
        import importlib
        importlib.reload(ai_client)
        assert ai_client.MODEL_URL == "http://custom-server:9000"

    def test_model_name_configurable(self, monkeypatch):
        from app import ai_client
        monkeypatch.setenv("MODEL_NAME", "llama3")
        import importlib
        importlib.reload(ai_client)
        assert ai_client.MODEL_NAME == "llama3"

    def test_ai_enabled_true(self, monkeypatch):
        from app import ai_client
        monkeypatch.setenv("AI_ENABLED", "true")
        monkeypatch.setenv("MODEL_URL", "http://test.local")
        import importlib
        importlib.reload(ai_client)
        assert ai_client.AI_ENABLED is True

    def test_ai_enabled_false(self, monkeypatch):
        from app import ai_client
        monkeypatch.setenv("AI_ENABLED", "false")
        monkeypatch.setenv("MODEL_URL", "http://test.local")
        import importlib
        importlib.reload(ai_client)
        assert ai_client.AI_ENABLED is False

    def test_completion_url_with_v1_suffix(self, monkeypatch):
        from app import ai_client
        monkeypatch.setenv("MODEL_URL", "http://test.local/v1")
        import importlib
        importlib.reload(ai_client)
        url = ai_client._get_completion_url()
        assert url == "http://test.local/v1/chat/completions"

    def test_completion_url_without_v1_suffix(self, monkeypatch):
        from app import ai_client
        monkeypatch.setenv("MODEL_URL", "http://test.local:8080")
        import importlib
        importlib.reload(ai_client)
        url = ai_client._get_completion_url()
        assert url == "http://test.local:8080/v1/chat/completions"


# ====================================================================
# Mock helper — patch call_model en call_model_structured direct
# ====================================================================

def _patch_call_model(return_text):
    """Patch ai_client.call_model om een vaste tekst terug te geven."""
    mock_fn = AsyncMock(return_value=return_text)
    return patch("app.ai_client.call_model", mock_fn)


def _patch_call_model_structured(return_dict):
    """Patch ai_client.call_model_structured om een vast dict terug te geven."""
    mock_fn = AsyncMock(return_value=return_dict)
    return patch("app.ai_client.call_model_structured", mock_fn)


# ====================================================================
# AI API endpoint-tests (met gemockt model)
# ====================================================================

class TestHypothesisSuggestions:
    """Test hypothese-suggesties endpoint."""

    async def test_suggest_hypotheses_returns_json(self, test_client):
        """Endpoint retourneert suggesties als JSON-array."""
        resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Test initiatief", "description": "Een test"
        })
        initiative_id = resp.json()["id"]

        suggestions = [
            {"type": "value", "description": "Gebruikers vinden de tool snel", "rationale": "Drempel is laag"},
        ]

        with _patch_call_model_structured({"success": True, "suggestions": suggestions}):
            response = await test_client.post(
                f"/api/ai/initiatieven/{initiative_id}/suggest-hypotheses"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    async def test_suggest_hypotheses_404_nonexistent(self, test_client):
        """Retourneert 404 voor niet-bestaand initiatief."""
        with _patch_call_model_structured({"suggestions": []}):
            response = await test_client.post(
                "/api/ai/initiatieven/nonexistent-id/suggest-hypotheses"
            )
            assert response.status_code == 404

    async def test_suggest_hypotheses_disabled_ai(self, test_client):
        """Retourneert foutmelding bij uitgeschakeld AI."""
        resp = await test_client.post("/api/initiatieven/create", json={"title": "Test"})
        initiative_id = resp.json()["id"]

        from app import ai_client
        original = ai_client.AI_ENABLED
        try:
            ai_client.AI_ENABLED = False
            response = await test_client.post(
                f"/api/ai/initiatieven/{initiative_id}/suggest-hypotheses"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
        finally:
            ai_client.AI_ENABLED = original

    async def test_suggest_hypotheses_no_model_url(self, test_client):
        """Retourneert foutmelding bij ontbrekende MODEL_URL."""
        resp = await test_client.post("/api/initiatieven/create", json={"title": "Test"})
        initiative_id = resp.json()["id"]

        from app import ai_client
        original_url = ai_client.MODEL_URL
        try:
            ai_client.MODEL_URL = ""
            response = await test_client.post(
                f"/api/ai/initiatieven/{initiative_id}/suggest-hypotheses"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
        finally:
            ai_client.MODEL_URL = original_url


class TestAcceptHypothesis:
    """Test hypothese accepteren endpoint."""

    async def test_accept_hypothesis(self, test_client):
        """Accepteer een AI-suggestie en voeg toe als hypothese."""
        resp = await test_client.post("/api/initiatieven/create", json={"title": "Test"})
        initiative_id = resp.json()["id"]

        response = await test_client.post(
            f"/api/ai/initiatieven/{initiative_id}/accept-hypothesis",
            json={"type": "value", "description": "AI-gesuggereerde hypothese"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "hypothesis_id" in data

    async def test_accept_hypothesis_invalid_type(self, test_client):
        """Afwijzen bij ongeldig type."""
        resp = await test_client.post("/api/initiatieven/create", json={"title": "Test"})
        initiative_id = resp.json()["id"]

        response = await test_client.post(
            f"/api/ai/initiatieven/{initiative_id}/accept-hypothesis",
            json={"type": "invalid", "description": "test"},
        )
        assert response.status_code == 400

    async def test_accept_hypothesis_no_description(self, test_client):
        """Afwijzen bij ontbrekende beschrijving."""
        resp = await test_client.post("/api/initiatieven/create", json={"title": "Test"})
        initiative_id = resp.json()["id"]

        response = await test_client.post(
            f"/api/ai/initiatieven/{initiative_id}/accept-hypothesis",
            json={"type": "value", "description": ""},
        )
        assert response.status_code == 400

    async def test_accept_hypothesis_duplicate(self, test_client):
        """Retourneert 409 bij dubbele hypothese."""
        resp = await test_client.post("/api/initiatieven/create", json={"title": "Test"})
        initiative_id = resp.json()["id"]
        desc = "Unieke test-hypothese"

        await test_client.post(
            f"/api/ai/initiatieven/{initiative_id}/accept-hypothesis",
            json={"type": "value", "description": desc},
        )
        response = await test_client.post(
            f"/api/ai/initiatieven/{initiative_id}/accept-hypothesis",
            json={"type": "value", "description": desc},
        )
        assert response.status_code == 409

    async def test_accept_hypothesis_404(self, test_client):
        """Retourneert 404 voor niet-bestaand initiatief."""
        response = await test_client.post(
            "/api/ai/initiatieven/nonexistent-id/accept-hypothesis",
            json={"type": "value", "description": "test"},
        )
        assert response.status_code == 404


class TestNarratief:
    """Test narratief-generatie endpoint."""

    async def test_narratief_returns_text(self, test_client):
        """Endpoint retourneert gegenereerd narratief."""
        init_resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Curatie-test initiatief"
        })
        initiative_id = init_resp.json()["id"]

        cur_resp = await test_client.post("/api/curaties/create", json={
            "name": "Test Curatie", "purpose": "Show & tell"
        })
        curation_id = cur_resp.json()["id"]

        await test_client.post(
            f"/api/curaties/{curation_id}/items/add",
            json={"initiative_id": initiative_id, "position": 1},
        )

        with _patch_call_model("Dit is een gegenereerd narratief over de curatie."):
            response = await test_client.post(f"/api/ai/curaties/{curation_id}/narratief")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "narrative" in data

    async def test_narratief_404_nonexistent(self, test_client):
        """Retourneert 404 voor niet-bestaande curatie."""
        with _patch_call_model("test"):
            response = await test_client.post("/api/ai/curaties/nonexistent-id/narratief")
            assert response.status_code == 404


class TestOnePager:
    """Test one-pager generatie endpoint."""

    async def test_onepager_returns_text(self, test_client):
        """Endpoint retourneert gegenereerde one-pager."""
        resp = await test_client.post("/api/initiatieven/create", json={
            "title": "One-pager test", "description": "Test beschrijving"
        })
        initiative_id = resp.json()["id"]

        with _patch_call_model("# One-Pager\nDit is de samenvatting."):
            response = await test_client.post(f"/api/ai/initiatieven/{initiative_id}/one-pager")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "one_pager" in data

    async def test_onepager_404_nonexistent(self, test_client):
        """Retourneert 404 voor niet-bestaand initiatief."""
        with _patch_call_model("test"):
            response = await test_client.post("/api/ai/initiatieven/nonexistent-id/one-pager")
            assert response.status_code == 404


class TestAIPrompts:
    """Test dat prompt templates bestaan en correct zijn."""

    def test_system_prompt_narratief_exists(self):
        from app.routes import ai
        assert "programmamanager" in ai.SYSTEM_PROMPT_NARRATIEF.lower()
        assert "directievoordracht" in ai.SYSTEM_PROMPT_NARRATIEF.lower()

    def test_system_prompt_hypothesen_exists(self):
        from app.routes import ai
        assert "value" in ai.SYSTEM_PROMPT_HYPOTHESEN.lower()
        assert "growth" in ai.SYSTEM_PROMPT_HYPOTHESEN.lower()
        assert "compliance" in ai.SYSTEM_PROMPT_HYPOTHESEN.lower()

    def test_system_prompt_onepager_exists(self):
        from app.routes import ai
        prompt_lower = ai.SYSTEM_PROMPT_ONEPAGER.lower()
        assert "one-pager" in prompt_lower or "onepager" in prompt_lower

    def test_data_helper_initiative_with_details(self):
        from app.routes.ai import _get_initiative_with_details
        assert callable(_get_initiative_with_details)

    def test_data_helper_curation_with_details(self):
        from app.routes.ai import _get_curation_with_details
        assert callable(_get_curation_with_details)


class TestAIErrorHandling:
    """Test error handling bij model-communicatie."""

    async def test_connect_error_returns_user_friendly_message(self, test_client):
        """Verbindingsfout geeft duidelijke melding."""
        resp = await test_client.post("/api/initiatieven/create", json={"title": "Test"})
        initiative_id = resp.json()["id"]

        error_mock = AsyncMock(
            return_value="[Verbindingsfout — kan niet verbinden met http://test/v1/chat/completions]"
        )
        with patch("app.ai_client.call_model", error_mock):
            response = await test_client.post(
                f"/api/ai/initiatieven/{initiative_id}/one-pager"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False

    async def test_empty_response_returns_error(self, test_client):
        """Leeg model-antwoord geeft foutmelding."""
        resp = await test_client.post("/api/initiatieven/create", json={"title": "Test"})
        initiative_id = resp.json()["id"]

        with _patch_call_model(""):
            response = await test_client.post(
                f"/api/ai/initiatieven/{initiative_id}/one-pager"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False

    async def test_structured_json_parse_error(self, test_client):
        """Ongeldig JSON-antwoord bij suggesties geeft error."""
        resp = await test_client.post("/api/initiatieven/create", json={"title": "Test"})
        initiative_id = resp.json()["id"]

        with _patch_call_model_structured({"error": "Kon antwoord niet parsen"}):
            response = await test_client.post(
                f"/api/ai/initiatieven/{initiative_id}/suggest-hypotheses"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False


class TestPreFiltering:
    """Test keyword pre-filtering logica."""

    def test_extract_keywords_basic(self):
        from app.routes.ai import _extract_keywords
        keywords = _extract_keywords("Digitaal platform voor vrijwilligers en ouderen")
        assert "digitaal" in keywords
        assert "platform" in keywords
        assert "vrijwilligers" in keywords
        assert "ouderen" in keywords

    def test_extract_keywords_removes_stop_words(self):
        from app.routes.ai import _extract_keywords
        keywords = _extract_keywords("de initiatieven van de gemeente Leiden")
        assert "de" not in keywords
        assert "van" not in keywords
        assert "initiatieven" in keywords
        assert "gemeente" in keywords
        assert "leiden" in keywords

    def test_extract_keywords_short_words_ignored(self):
        from app.routes.ai import _extract_keywords
        keywords = _extract_keywords("AI en IoT")
        # Woorden korter dan 3 karakters worden genegeerd
        assert "ai" not in keywords
        # 'iot' is precies 3 karakters → wordt wel meegeteld
        assert "iot" in keywords

    def test_score_initiative_title_match_counts_double(self):
        from app.routes.ai import _score_initiative, _extract_keywords
        from unittest.mock import MagicMock

        init = MagicMock()
        init.title = "Digitaal platform"
        init.description = "Een webapp voor vrijwilligers"

        keywords = ["digitaal", "platform", "webapp"]
        score = _score_initiative(init, keywords)
        # 'digitaal' en 'platform' in titel = 2*2 = 4, 'webapp' in desc = 1
        assert score == 5.0

    def test_score_initiative_no_match(self):
        from app.routes.ai import _score_initiative
        from unittest.mock import MagicMock

        init = MagicMock()
        init.title = "Test initiatief"
        init.description = "Geen match hier"

        keywords = ["vrijwilligers", "ouderen", "participatie"]
        score = _score_initiative(init, keywords)
        assert score == 0.0

    def test_score_initiative_description_only(self):
        from app.routes.ai import _score_initiative
        from unittest.mock import MagicMock

        init = MagicMock()
        init.title = "Korte titel"
        init.description = "Over vrijwilligers en participatie"

        keywords = ["vrijwilligers", "participatie"]
        score = _score_initiative(init, keywords)
        # Beide in beschrijving = 1+1 = 2
        assert score == 2.0

    def test_max_candidates_constant(self):
        from app.routes.ai import MAX_CANDIDATES
        assert MAX_CANDIDATES == 30


class TestCurationInitiativeSuggestions:
    """Test initiatief-suggesties voor curaties."""

    async def test_suggest_initiatives_returns_json(self, test_client):
        """Endpoint retourneert suggesties als JSON-array."""
        # Maak een initiatief aan dat NIET in de curatie zit
        init_resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Beschikbaar initiatief",
            "description": "Dit initiatief is beschikbaar voor suggestie"
        })
        available_id = init_resp.json()["id"]

        # Maak een curatie aan
        cur_resp = await test_client.post("/api/curaties/create", json={
            "name": "Test Curatie",
            "purpose": "Show & tell"
        })
        curation_id = cur_resp.json()["id"]

        suggestions = [
            {"initiative_id": available_id, "title": "Beschikbaar initiatief", "rationale": "Past bij doel"},
        ]

        with _patch_call_model_structured(suggestions):
            response = await test_client.post(
                f"/api/ai/curaties/{curation_id}/suggest-initiatives"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["suggestions"]) == 1

    async def test_suggest_initiatives_excludes_existing(self, test_client):
        """Initiatieven die al in de curatie zitten worden uitgesloten."""
        init_resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Al toegevoegd",
            "description": "Dit initiatief zit al in de curatie"
        })
        initiative_id = init_resp.json()["id"]

        cur_resp = await test_client.post("/api/curaties/create", json={
            "name": "Test Curatie",
            "purpose": "Show & tell"
        })
        curation_id = cur_resp.json()["id"]

        # Voeg initiatief toe aan curatie
        await test_client.post(
            f"/api/curaties/{curation_id}/items/add",
            json={"initiative_id": initiative_id, "position": 1},
        )

        with _patch_call_model_structured([]):
            response = await test_client.post(
                f"/api/ai/curaties/{curation_id}/suggest-initiatives"
            )
            assert response.status_code == 200
            data = response.json()
            # Moet lege lijst zijn omdat het enige initiatief al toegevoegd is
            assert data["suggestions"] == []

    async def test_suggest_initiatives_404_nonexistent(self, test_client):
        """Retourneert 404 voor niet-bestaande curatie."""
        with _patch_call_model_structured([]):
            response = await test_client.post(
                "/api/ai/curaties/nonexistent-id/suggest-initiatives"
            )
            assert response.status_code == 404

    async def test_suggest_initiatives_excludes_stopped(self, test_client):
        """Gestopte initiatieven worden uitgesloten van suggesties."""
        # Maak gestopt initiatief
        init_resp = await test_client.post("/api/initiatieven/create", json={
            "title": "Gestopt initiatief",
            "description": "Dit initiatief is gestopt"
        })
        initiative_id = init_resp.json()["id"]

        # Stop het initiatief
        await test_client.post(
            f"/api/initiatieven/{initiative_id}/stop",
            json={"stop_reason": "Test reden"},
        )

        cur_resp = await test_client.post("/api/curaties/create", json={
            "name": "Test Curatie",
            "purpose": "Show & tell"
        })
        curation_id = cur_resp.json()["id"]

        with _patch_call_model_structured([]):
            response = await test_client.post(
                f"/api/ai/curaties/{curation_id}/suggest-initiatives"
            )
            assert response.status_code == 200
            data = response.json()
            # Gestopte initiatieven mogen niet worden gesuggereerd
            assert data["suggestions"] == []
