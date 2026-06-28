"""Import initiatieven uit het markdown document in de database."""

import os
import re
import sys

# Ensure app module is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db
from app.models import Initiative

MD_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "Inventarisatie_AI_initiatieven_v0.1.md",
)

# Map fase-namen naar enum waarden
FASE_MAP = {
    "verkenning": "verkenning",
    "experiment": "experiment",
    "pilot": "pilot",
    "opschaling": "opschaling",
    "idee": "verkenning",  # idee -> verkenning (dichtstbijzijnde)
    "gestopt": "verkenning",
    "onbekend": "verkenning",
    "mix": "experiment",
}

# Map status-namen naar enum waarden
STATUS_MAP = {
    "actief": "actief",
    "gestopt": "gestopt",
    "afgerond": "afgerond",
    "onduidelijk": "actief",
    "idee": "actief",
}


def extract_initiatives(md_text: str) -> list[dict]:
    """Parse het markdown document en extraheer initiatieven."""
    initiatives = []
    current_cluster = ""

    # Split in secties per initiatief (#### CODE — Titel)
    pattern = re.compile(
        r'^####\s+([A-Z]+-\d+)\s*—\s*(.+)$', re.MULTILINE
    )
    matches = list(pattern.finditer(md_text))

    for i, match in enumerate(matches):
        code = match.group(1)
        title = match.group(2).strip()

        # Bepaal tekstblok voor dit initiatief (tot volgende #### of einde)
        start = match.end()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(md_text)

        block = md_text[start:end]

        # Parse velden uit het blok
        description = extract_field(block, "Omschrijving") or ""
        fase_raw = extract_field(block, "Fase") or "verkenning"
        type_ai = extract_field(block, "Type AI-gebruik") or ""
        trekker = extract_field(block, "Trekker") or ""
        afdeling = extract_field(block, "Afdeling") or ""
        team = extract_field(block, "Team") or ""
        bron_initiatief = extract_field(block, "Bron initiatief") or ""
        externe_partners = extract_field(block, "Externe partners") or ""
        betrokkenheid_iv = extract_field(block, "Betrokkenheid IV") or ""
        gerelateerde = extract_field(block, "Gerelateerde initiatieven") or ""
        aandachtspunten = extract_field(block, "Aandachtspunten") or ""
        volgende_stap = extract_field(block, "Volgende stap") or ""
        centrale_vraag = extract_field(block, "Centrale vraag") or ""
        leeruitkomst = extract_field(block, "Leeruitkomst") or ""
        status_raw = extract_field(block, "Status") or ""
        programma = extract_field(block, "Programma") or ""

        # Bepaal fase en status
        phase = FASE_MAP.get(_normalize(fase_raw), "verkenning")
        status = STATUS_MAP.get(_normalize(status_raw), "actief")

        # Speciale gevallen
        if "gestopt" in _normalize(fase_raw):
            status = "gestopt"
            phase = "verkenning"

        # Bouw uitgebreide description
        desc_parts = []
        if description:
            desc_parts.append(description)

        meta_lines = []
        if current_cluster:
            meta_lines.append(f"**Cluster:** {current_cluster}")
        if afdeling:
            meta_lines.append(f"**Afdeling:** {afdeling}")
        if team:
            meta_lines.append(f"**Team:** {team}")
        if trekker:
            meta_lines.append(f"**Trekker:** {trekker}")
        if type_ai and type_ai not in ("n.v.t.", "onbekend"):
            meta_lines.append(f"**Type AI-gebruik:** {type_ai}")
        if bron_initiatief:
            meta_lines.append(f"**Bron initiatief:** {bron_initiatief}")
        if externe_partners:
            meta_lines.append(f"**Externe partners:** {externe_partners}")
        if betrokkenheid_iv:
            meta_lines.append(f"**Betrokkenheid IV:** {betrokkenheid_iv}")

        if meta_lines:
            desc_parts.append("\n" + "\n".join(meta_lines))

        if volgende_stap:
            desc_parts.append(f"\n**Volgende stap:** {volgende_stap}")
        if aandachtspunten:
            desc_parts.append(f"\n**Aandachtspunten:** {aandachtspunten}")
        if gerelateerde:
            desc_parts.append(f"\n**Gerelateerd aan:** {gerelateerde}")
        if centrale_vraag:
            desc_parts.append(f"\n**Centrale vraag:** {centrale_vraag}")
        if leeruitkomst:
            desc_parts.append(f"\n**Leeruitkomst:** {leeruitkomst}")

        full_description = "\n".join(desc_parts) if desc_parts else description

        # Owner = trekker of afdeling
        owner = trekker or afdeling or ""

        initiatives.append({
            "code": code,
            "title": title,
            "description": full_description.strip(),
            "phase": phase,
            "status": status,
            "owner": owner.strip(),
            "stop_reason": leeruitkomst if status == "gestopt" else None,
        })

    return initiatives


def extract_field(block: str, field_name: str) -> str | None:
    """Haal een veld op uit het markdown blok."""
    pattern = re.compile(
        rf'^-?\s*\*?\*?{field_name}\*?\*?\s*[:—]\s*(.+)$',
        re.MULTILINE | re.IGNORECASE,
    )
    m = pattern.search(block)
    if m:
        return m.group(1).strip()
    return None


def _normalize(text: str) -> str:
    """Verwijder opmerkingen tussen haakjes en normalize."""
    # Haal "(gok: ...)" en "(niet vermeld)" opmerkingen voor matching
    base = re.sub(r'\([^)]*\)', '', text).strip().lower()
    if not base:
        base = text.lower().split()[0] if text.split() else ""
    return base


def import_initiatives():
    """Importeer initiatieven in de database."""
    init_db()

    with open(MD_PATH, "r", encoding="utf-8") as f:
        md_text = f.read()

    initiatives_data = extract_initiatives(md_text)

    print(f"Geïdentificeerd: {len(initiatives_data)} initiatieven\n")

    db = SessionLocal()
    try:
        added = 0
        skipped = 0

        for data in initiatives_data:
            # Check of er al een initiatief met deze titel bestaat (fuzzy match)
            existing = db.query(Initiative).filter(
                Initiative.title.ilike(f"%{data['title'][:30]}%")
            ).first()

            if existing:
                print(f"  ⏭️  Bestaat al: {data['code']} — {data['title']} (id={existing.id})")
                skipped += 1
                continue

            init = Initiative(
                title=data["title"],
                description=data["description"],
                phase=data["phase"],
                status=data["status"],
                owner=data["owner"] or None,
                stop_reason=data["stop_reason"],
            )
            db.add(init)
            added += 1
            print(f"  ✅ Toegevoegd: {data['code']} — {data['title']}")

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"\n❌ Fout bij importeren: {e}")
        raise
    finally:
        db.close()

    print(f"\n{'='*50}")
    print(f"Import voltooid: {added} toegevoegd, {skipped} overgeslagen")


if __name__ == "__main__":
    import_initiatives()
