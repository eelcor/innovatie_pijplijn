#!/usr/bin/env python3
"""Importeer initiatieven uit Inventarisatie_AI_initiatieven_v0.1.md.

Gebruik:
    uv run python scripts/import_inventarisatie.py

Importeert alle initiatieven uit het markdown bestand naar de database.
Bestaande initiatieven met dezelfde code (bijv. B-01) worden overschreven.
"""

import os
import re
import sys
from pathlib import Path

# Zorg dat app in path staat
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.models import Initiative

# --- Config ---

MD_FILE = Path(__file__).parent.parent / "Inventarisatie_AI_initiatieven_v0.1.md"

# Fase mapping: transcript termen → database enums
FASE_MAP = {
    "verkenning": "verkenning",
    "experiment": "experiment",
    "pilot": "pilot",
    "opschaling": "opschaling",
    "mix": "verkenning",  # fallback
    "idee": "verkenning",  # idee → verkenning (minimale fase)
}

# Status mapping
STATUS_MAP = {
    "actief": "actief",
    "gestopt": "gestopt",
    "afgerond": "afgerond",
    "onduidelijk": "actief",  # onduidelijk → actief (we blijven volgen)
}

# Type AI-gebruik mapping
AI_TYPE_MAP = {
    "bouwen_met_ai": "bouwen_met_ai",
    "ai_in_bouwsels": "ai_in_bouwsels",
    "ai_in_bestaande_tools": "ai_in_bestaande_tools",
    "persoonlijke_productiviteit": "persoonlijke_productiviteit",
    "mix": "mix",
    "n.v.t.": None,  # geen AI initiatief
}


def parse_initiatives(markdown_text: str) -> list[dict]:
    """Parse initiatieven uit het markdown bestand."""
    initiatives = []

    # Splits op initiative headers (#### CODE — TITEL)
    pattern = r'^####\s+([A-Z]+-\d+)\s*—\s*(.+?)$'
    lines = markdown_text.split('\n')

    current = None
    for line in lines:
        match = re.match(pattern, line.strip())
        if match:
            if current:
                initiatives.append(current)
            code = match.group(1)
            title = match.group(2).strip()
            current = {
                "code": code,
                "title": title,
                "description": "",
                "phase": "verkenning",
                "status": "actief",
                "type_ai_gebruik": None,
                "trekker": None,
                "bron_initiatief": None,
                "betrokkenheid_iv": None,
                "aandachtspunten": None,
                "volgende_stap": None,
                "externe_partners": None,
                "horizon": None,
            }
        elif current and line.strip().startswith("- **"):
            # Parse veld: "- **Veld:** waarde"
            # Format: - **Field:** Value (colon is INSIDE the bold markers)
            field_match = re.match(r'^-\s+\*\*(.+?):\*\*\s+(.+)$', line.strip())
            if field_match:
                field_name = field_match.group(1).strip().lower()
                value = field_match.group(2).strip()

                # Map veldnamen naar database velden
                field_map = {
                    "omschrijving": "description",
                    "fase": "phase",
                    "type ai-gebruik": "type_ai_gebruik",
                    "trekker": "trekker",
                    "bron initiatief": "bron_initiatief",
                    "betrokkenheid iv": "betrokkenheid_iv",
                    "aandachtspunten": "aandachtspunten",
                    "volgende stap": "volgende_stap",
                    "status": "status",
                    "externe partners": "externe_partners",
                }

                if field_name in field_map:
                    db_field = field_map[field_name]
                    current[db_field] = value

    # Voeg laatste initiatief toe
    if current:
        initiatives.append(current)

    return initiatives


def normalize_initiative(data: dict) -> dict:
    """Normalizeer waarden naar database enums."""
    # Fase
    phase_raw = (data.get("phase") or "verkenning").lower()
    data["phase"] = FASE_MAP.get(phase_raw, "verkenning")

    # Status
    status_raw = (data.get("status") or "actief").lower()
    data["status"] = STATUS_MAP.get(status_raw, "actief")

    # Type AI-gebruik
    ai_raw = (data.get("type_ai_gebruik") or "").lower()
    data["type_ai_gebruik"] = AI_TYPE_MAP.get(ai_raw)

    # Clean up "(niet vermeld)" en "(gok: ...)" notaties
    for field in ["trekker", "aandachtspunten", "volgende_stap"]:
        val = data.get(field) or ""
        if "(niet vermeld)" in val.lower():
            data[field] = None

    return data


def import_initiatives(db: Session, initiatives: list[dict]) -> tuple[int, int]:
    """Importeer initiatieven naar de database.

    Retourneert (aantal nieuw, aantal bijgewerkt).
    """
    new_count = 0
    updated_count = 0

    for data in initiatives:
        code = data["code"]
        title = f"[{code}] {data['title']}"

        # Zoek bestaand initiatief op code (in titel)
        existing = db.query(Initiative).filter(
            Initiative.title.like(f"%[{code}]%")
        ).first()

        if existing:
            # Update bestaande
            existing.description = data["description"] or existing.description
            existing.phase = data["phase"]
            existing.status = data["status"]
            existing.type_ai_gebruik = data["type_ai_gebruik"]
            existing.trekker = data["trekker"]
            updated_count += 1
        else:
            # Nieuw initiatief
            initiative = Initiative(
                title=title,
                description=data["description"],
                phase=data["phase"],
                status=data["status"],
                horizon=data["horizon"],
                type_ai_gebruik=data["type_ai_gebruik"],
                trekker=data["trekker"],
            )
            db.add(initiative)
            new_count += 1

    db.commit()
    return new_count, updated_count


def main():
    """Hoofdfunctie."""
    if not MD_FILE.exists():
        print(f"Fout: bestand niet gevonden: {MD_FILE}")
        sys.exit(1)

    # Lees markdown
    markdown_text = MD_FILE.read_text(encoding="utf-8")
    print(f"Lezen: {MD_FILE} ({len(markdown_text)} bytes)")

    # Parse initiatieven
    initiatives = parse_initiatives(markdown_text)
    print(f"Gevonden: {len(initiatives)} initiatieven")

    if not initiatives:
        print("Geen initiatieven gevonden — controleer het markdown formaat.")
        sys.exit(1)

    # Print overzicht
    for i, data in enumerate(initiatives, 1):
        code = data["code"]
        title = data["title"][:60]
        phase = data.get("phase", "?")
        ai_type = data.get("type_ai_gebruik", "?")
        print(f"  {i:2d}. [{code}] {title}... | fase={phase} | AI={ai_type}")

    # Normalizeer
    initiatives = [normalize_initiative(d) for d in initiatives]

    # Importeer
    init_db()
    db = SessionLocal()
    try:
        new, updated = import_initiatives(db, initiatives)
        print(f"\nResultaat:")
        print(f"  Nieuw aangemaakt: {new}")
        print(f"  Bijgewerkt: {updated}")
        print(f"  Totaal: {new + updated}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
