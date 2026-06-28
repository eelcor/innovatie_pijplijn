"""Beheerconfiguratie voor de Innovatiepijplijn.

Opslag van aanpasbare instellingen in een JSON-bestand zodat admin
instellingen kan wijzigen zonder environment variabelen te herstarten.

Bestand: data/admin_config.json
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
    """Haal huidige configuratie op."""
    return _load()


def update_config(updates: dict) -> dict:
    """Update configuratie met nieuwe waarden.

    Retourneert de volledige bijgewerkte configuratie (zonder API key).
    """
    config = _load()
    allowed_keys = set(DEFAULT_CONFIG.keys())
    for key, value in updates.items():
        if key in allowed_keys:
            config[key] = value
    _save(config)

    # Retourneer zonder API key
    result = dict(config)
    api_key_masked = "(ingesteld)" if result.get("ai_api_key") else ""
    result["ai_api_key"] = api_key_masked
    return result


def get_ai_config_for_client() -> dict:
    """Haal AI configuratie op voor de ai_client module.

    Combineert environment variabelen met admin config (admin config heeft prioriteit).
    """
    config = _load()

    # Environment variabelen als fallback
    env_url = os.environ.get("MODEL_URL", "").rstrip("/")
    env_name = os.environ.get("MODEL_NAME", "qwen3.6")
    env_key = os.environ.get("MODEL_API_KEY", "")
    env_enabled = os.environ.get("AI_ENABLED", "true").lower() in ("true", "1", "yes")
    env_timeout = float(os.environ.get("AI_REQUEST_TIMEOUT", "120"))

    # Admin config heeft prioriteit boven environment
    model_url = config.get("ai_model_url") or env_url
    model_name = config.get("ai_model_name") or env_name
    api_key = config.get("ai_api_key") or env_key
    ai_enabled = config.get("ai_enabled", env_enabled)
    timeout = config.get("ai_request_timeout", env_timeout)

    return {
        "MODEL_URL": model_url,
        "MODEL_NAME": model_name,
        "MODEL_API_KEY": api_key,
        "AI_ENABLED": ai_enabled,
        "REQUEST_TIMEOUT": timeout,
        "TEMPERATURE": config.get("ai_temperature", 0.7),
        "MAX_TOKENS": config.get("ai_max_tokens", 8192),
    }
