"""Model-agnostische AI-client voor de Innovatiepijplijn.

Ondersteunt elk taalmodel met een OpenAI-compatible chat completions endpoint:
  Ollama, vLLM, LM Studio, SambaNova, etc.

Configuratie via omgevingsvariabelen:
  MODEL_URL    — base URL van het model (bijv. http://beestjeai2.local:8033)
  MODEL_NAME   — naam van het model (bijv. qwen3.6)
  MODEL_API_KEY — optionele API key
  AI_ENABLED   — "true"/"false" om AI in/uit te schakelen
"""

import json
import os
from typing import Optional

import httpx

# --- Configuratie (model-agnostisch, uit environment) ---

MODEL_URL = os.environ.get("MODEL_URL", "").rstrip("/")
MODEL_NAME = os.environ.get("MODEL_NAME", "qwen3.6")
MODEL_API_KEY = os.environ.get("MODEL_API_KEY", "")
# AI standaard uitgeschakeld — expliciet inschakelen via AI_ENABLED=true
AI_ENABLED = os.environ.get("AI_ENABLED", "false").lower() in ("true", "1", "yes")

# Standaard timeout per request (seconden)
# 120s is enough for most prompts; prevents runaway costs on slow models
REQUEST_TIMEOUT = float(os.environ.get("AI_REQUEST_TIMEOUT", "120"))


def _get_completion_url() -> str:
    """Bouw het volledige chat completions URL."""
    if MODEL_URL.endswith("/v1"):
        return f"{MODEL_URL}/chat/completions"
    else:
        return f"{MODEL_URL}/v1/chat/completions"


async def call_model(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.7,
    max_tokens: int = 8192,
) -> str:
    """Roep het taalmodel aan via OpenAI-compatible API.

    Retourneert de tekst van het model-antwoord.
    Geeft een beschrijvende error string terug bij falen.

    Ondersteunt 'thinking' modellen die reasoning_content gebruiken:
    als content leeg is maar reasoning_content aanwezig, wordt de
    redenering meegenomen zodat het model niet halfweg afbreekt.
    """
    if not AI_ENABLED:
        return "[AI is uitgeschakeld — stel MODEL_URL en AI_ENABLED=true in]"

    if not MODEL_URL:
        return "[AI niet geconfigureerd — stel MODEL_URL in]"

    url = _get_completion_url()

    headers = {"Content-Type": "application/json"}
    if MODEL_API_KEY:
        headers["Authorization"] = f"Bearer {MODEL_API_KEY}"

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            message = data.get("choices", [{}])[0].get("message", {})
            content = message.get("content", "")

            # Sommige modellen (thinking/reasoning) geven eerst reasoning_content
            # Als content leeg is maar het model wel tokens heeft verbruikt,
            # betekent dit dat de redenering halverwege afliep.
            reasoning = message.get("reasoning_content", "")
            usage = data.get("usage", {})
            completion_tokens = usage.get("completion_tokens", 0)

            if not content and reasoning and completion_tokens > 0:
                # Thinking-model: content is leeg omdat max_tokens op was
                return f"[Model had meer tokens nodig — verhoog max_tokens (huidig gebruik: {completion_tokens})]"

            if not content:
                return "[Model gaf een leeg antwoord]"
            return content.strip()
        except httpx.ConnectError:
            return f"[Verbindingsfout — kan niet verbinden met {url}]"
        except httpx.TimeoutException:
            return f"[Timeout — model reageerde niet binnen {REQUEST_TIMEOUT}s]"
        except httpx.HTTPStatusError as e:
            body = ""
            try:
                body = e.response.text[:200]
            except Exception:
                pass
            return f"[HTTP-fout {e.response.status_code} van model: {body}]"
        except json.JSONDecodeError:
            return "[Model antwoord is geen geldig JSON]"
        except Exception as e:
            return f"[Onverwachte fout bij AI-aanroep: {type(e).__name__}: {e}]"


async def call_model_structured(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.7,
    max_tokens: int = 8192,
) -> dict:
    """Roep het model aan en parseer JSON-antwoord.

    Voegt instructie toe om JSON terug te geven en probeert
    het antwoord te parsen met meerdere strategieën. Retourneert
    een error dict bij falen.
    """
    # Vraag expliciet om JSON in de system prompt
    json_system = f"{system_prompt}\n\nGeef je antwoord uitsluitend als geldig JSON."

    raw = await call_model(
        system_prompt=json_system,
        user_prompt=user_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # Error-strings beginnen met [ gevolgd door een letter (bijv. "[Timeout", "[Verbindingsfout")
    # JSON arrays beginnen met [{ of [" — die mogen we proberen te parsen
    if raw.startswith("[") and len(raw) > 1 and raw[1].isalpha():
        return {"error": raw}

    def try_parse(text: str):
        """Probeer JSON te parsen uit tekst."""
        text = text.strip()
        # Direct proberen
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Haal markdown code blocks eruit
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                try:
                    return json.loads(part)
                except json.JSONDecodeError:
                    continue

        # Zoek naar eerste [ of { en probeer van daar te parsen
        for start_char in ("[", "{"):
            idx = text.find(start_char)
            if idx >= 0:
                end_char = "]" if start_char == "[" else "}"
                # Zoek de bijpassende closing bracket met balanced counting
                depth = 0
                for i in range(idx, len(text)):
                    if text[i] == start_char:
                        depth += 1
                    elif text[i] == end_char:
                        depth -= 1
                        if depth == 0:
                            candidate = text[idx:i+1]
                            try:
                                return json.loads(candidate)
                            except json.JSONDecodeError:
                                break
        return None

    parsed = try_parse(raw)
    if parsed is not None:
        return parsed

    return {"error": f"Kon antwoord niet parsen als JSON", "raw": raw[:500]}
