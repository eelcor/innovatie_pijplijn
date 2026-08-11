#!/usr/bin/env python3
"""Migratie script voor v0.2 — nieuwe velden toevoegen aan Initiative model.

Nieuwe kolommen:
  - cluster: tekst (Beheer, Dienstverlening, etc.)
  - afdeling: tekst
  - team: tekst
  - potentie: enum (hoog, midden, onbekend)
  - capaciteitsvraag: enum (hoog, midden, laag, onbekend)
  - risico: enum (hoog, midden, laag)
  - bron_initiatief: tekst
  - externe_partners: tekst
  - betrokkenheid_iv: enum (actief_begeleidend, passief_volgend, nog_niet_betrokken)
  - gerelateerde_initiatieven: tekst
  - volgende_stap: tekst
  - opmerkingen: tekst

Ook extendeert bestaande enums:
  - status: + "onduidelijk", "pauze", "idee"
  - fase: blijft zoals is (nieuwe waarden worden gemapped)
"""

import sys
from pathlib import Path

# Voeg project root toe aan path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect
from app.database import engine, SessionLocal
from app.logging_config import logger


def run_migration():
    """Voer database migraties uit voor de nieuwe velden."""
    db = SessionLocal()

    try:
        # Check welke kolommen al bestaan
        inspector = inspect(engine)
        existing_cols = {col["name"] for col in inspector.get_columns("initiatives")}
        new_cols = [
            "cluster", "afdeling", "team", "potentie", "capaciteitsvraag",
            "risico", "bron_initiatief", "externe_partners", "betrokkenheid_iv",
            "gerelateerde_initiatieven", "volgende_stap", "opmerkingen"
        ]

        # --- Stap 1: Extendeer status enum met nieuwe waarden ---
        print("Stap 1: Status enum extenderen...")
        try:
            db.execute(text("""
                ALTER TABLE initiatives
                ADD CONSTRAINT check_status_extended
                CHECK (status IN ('actief', 'gestopt', 'afgerond', 'onduidelijk', 'pauze', 'idee'))
            """))
        except Exception as e:
            # Constraint bestaat mogelijk al of enum is anders geimplementeerd
            if "already exists" not in str(e).lower():
                print(f"  Info: status check constraint: {e}")

        # Voor SQLite: we kunnen de enum waarden direct toevoegen door
        # de kolom te droppen en opnieuw aan te maken. Maar dat is riskant.
        # In plaats daarvan gebruiken we Text kolommen voor flexibiliteit.
        print("  Status waarden worden flexibel geaccepteerd (Text-based)")

        # --- Stap 2: Voeg nieuwe tekstkolommen toe ---
        print("Stap 2: Nieuwe tekstkolommen toevoegen...")
        text_columns = [
            ("cluster", "TEXT"),
            ("afdeling", "TEXT"),
            ("team", "TEXT"),
            ("bron_initiatief", "TEXT"),
            ("externe_partners", "TEXT"),
            ("gerelateerde_initiatieven", "TEXT"),
            ("volgende_stap", "TEXT"),
            ("opmerkingen", "TEXT"),
        ]

        for col_name, col_type in text_columns:
            if col_name not in existing_cols:
                try:
                    db.execute(text(f"ALTER TABLE initiatives ADD COLUMN {col_name} {col_type} DEFAULT NULL"))
                    print(f"  ✓ {col_name} toegevoegd")
                except Exception as e:
                    print(f"  ⚠ {col_name}: {e}")
            else:
                print(f"  ∟ {col_name} bestaat al")

        # --- Stap 3: Voeg enum-achtige kolommen toe als TEXT (flexibel) ---
        print("Stap 3: Enum-achtige kolommen toevoegen (als TEXT voor flexibiliteit)...")
        enum_columns = [
            ("potentie", "TEXT"),           # hoog, midden, onbekend
            ("capaciteitsvraag", "TEXT"),   # hoog, midden, laag, onbekend
            ("risico", "TEXT"),             # hoog, midden, laag
            ("betrokkenheid_iv", "TEXT"),   # actief_begeleidend, passief_volgend, nog_niet_betrokken
        ]

        for col_name, col_type in enum_columns:
            if col_name not in existing_cols:
                try:
                    db.execute(text(f"ALTER TABLE initiatives ADD COLUMN {col_name} {col_type} DEFAULT NULL"))
                    print(f"  ✓ {col_name} toegevoegd")
                except Exception as e:
                    print(f"  ⚠ {col_name}: {e}")
            else:
                print(f"  ∟ {col_name} bestaat al")

        db.commit()
        print("\nMigratie voltooid!")

        # Toon nieuwe schema
        inspector = inspect(engine)
        all_cols = [col["name"] for col in inspector.get_columns("initiatives")]
        print(f"\nInitiatieven tabel heeft nu {len(all_cols)} kolommen")

    except Exception as e:
        db.rollback()
        print(f"FOUT bij migratie: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
