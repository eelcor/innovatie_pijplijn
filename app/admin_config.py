"""Beheerconfiguratie voor de Innovatiepijplijn.

Opslag van aanpasbare instellingen in een JSON-bestand zodat admin
instellingen kan wijzigen zonder environment variabelen te herstarten.

Bestand: data/admin_config.json

Configuratie-voorrang (van hoog naar laag):
  1. admin_config.json  — wordt bij startup geladen, overschrijft .env waarden
  2. .env / env vars    — APP_BASE_URL, AI_ENABLED, MODEL_URL, etc.
  3. hardcoded defaults — fallback als niets anders is ingesteld

Dit betekent dat een admin die via het beheerpaneel de AI-config wijzigt,
dit direct effect heeft én het overleeft bij herstart — tenzij de .env
terug wordt gezet EN admin_config.json wordt gewist.
"""

import json
import os
from pathlib import Path
from typing import Optional

from app.logging_config import logger

# Pad naar configuratiebestand
ADMIN_CONFIG_PATH = os.environ.get(
    "ADMIN_CONFIG_PATH",
    str(Path(__file__).parent.parent / "data" / "admin_config.json"),
)

DEFAULT_CONFIG = {
    "ai_model_url": "",
    "ai_model_name": "qwen3.6",
    "ai_api_key": "",
    "ai_enabled": True,
    "ai_request_timeout": 120,
    "ai_temperature": 0.7,
    "ai_max_tokens": 8192,
}


def _load() -> dict:
    """Laad configuratiebestand (of default)."""
    path = Path(ADMIN_CONFIG_PATH)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Merge met defaults voor nieuwe velden
            config = {**DEFAULT_CONFIG, **data}
            return config
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Kon admin_config.json niet laden: {e}, gebruik default")
    return dict(DEFAULT_CONFIG)


def _save(config: dict) -> None:
    """Sla configuratie op."""
    path = Path(ADMIN_CONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_config() -> dict:
    """Haal huidige effectieve configuratie op.

    Combineert admin_config.json met environment variabelen zodat de
    admin UI altijd de daadwerkelijk actieve waarden toont.
    """
    config = _load()
    ai_cfg = get_ai_config_for_client()

    # Vervang lege/missing waarden door effectieve waarden (van env of defaults)
    result = dict(config)
    if not result.get("ai_model_url"):
        result["ai_model_url"] = ai_cfg["MODEL_URL"] or ""
    if not result.get("ai_model_name"):
        result["ai_model_name"] = ai_cfg["MODEL_NAME"]
    if not result.get("ai_api_key"):
        result["ai_api_key"] = "(via environment)" if ai_cfg["MODEL_API_KEY"] else ""
    if "ai_enabled" not in result:
        result["ai_enabled"] = ai_cfg["AI_ENABLED"]
    if "ai_request_timeout" not in result:
        result["ai_request_timeout"] = ai_cfg["REQUEST_TIMEOUT"]

    return result


def update_config(updates: dict) -> dict:
    """Update configuratie met nieuwe waarden.

    Retourneert de volledige bijgewerkte configuratie (zonder API key).
    Lege string waarden worden verwijderd zodat environment variabelen
    als fallback gebruikt worden.
    """
    config = _load()
    allowed_keys = set(DEFAULT_CONFIG.keys())
    for key, value in updates.items():
        if key in allowed_keys:
            # Strip trailing slashes from model URL
            if key == "ai_model_url" and isinstance(value, str):
                value = value.rstrip("/")
            # Remove empty string values so env vars act as fallback
            if value == "" or value is None:
                config.pop(key, None)
            else:
                config[key] = value
    _save(config)

    # Retourneer zonder API key
    result = dict(config)
    api_key_masked = "(ingesteld)" if result.get("ai_api_key") else ""
    result["ai_api_key"] = api_key_masked
    return result


def get_ai_config_for_client() -> dict:
    """Haal AI configuratie op voor de ai_client module.

    Prioriteit: admin_config.json > environment variabelen > defaults.
    Alleen niet-lege waarden uit admin_config.json overschrijven env vars.
    """
    config = _load()

    # Environment variabelen als fallback
    env_url = os.environ.get("MODEL_URL", "").rstrip("/")
    env_name = os.environ.get("MODEL_NAME", "qwen3.6")
    env_key = os.environ.get("MODEL_API_KEY", "")
    env_enabled = os.environ.get("AI_ENABLED", "true").lower() in ("true", "1", "yes")
    env_timeout = float(os.environ.get("AI_REQUEST_TIMEOUT", "120"))

    # Admin config overschrijft env var ALLEEN als de waarde niet-lege is.
    # Dit zorgt dat .env variabelen correct werken als defaults.
    cfg_url = (config.get("ai_model_url") or "").rstrip("/")
    cfg_name = config.get("ai_model_name") or ""
    cfg_key = config.get("ai_api_key") or ""

    model_url = cfg_url or env_url
    model_name = cfg_name or env_name
    api_key = cfg_key or env_key

    # Voor boolean en numeriek: admin config overschrijft alleen als expliciet ingesteld
    ai_enabled = config.get("ai_enabled", None)
    if ai_enabled is None:
        ai_enabled = env_enabled

    timeout = config.get("ai_request_timeout", None)
    if timeout is None:
        timeout = env_timeout

    temperature = config.get("ai_temperature", 0.7)
    max_tokens = config.get("ai_max_tokens", 8192)

    return {
        "MODEL_URL": model_url,
        "MODEL_NAME": model_name,
        "MODEL_API_KEY": api_key,
        "AI_ENABLED": ai_enabled,
        "REQUEST_TIMEOUT": timeout,
        "TEMPERATURE": temperature,
        "MAX_TOKENS": max_tokens,
    }
