#!/usr/bin/env python3
"""Migratie — voeg commentary kolom toe aan hypotheses tabel."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine


def migrate():
    """Voeg commentary kolom toe aan de hypotheses tabel."""
    with engine.connect() as conn:
        # Check of kolom al bestaat
        result = conn.execute(text("PRAGMA table_info(hypotheses)"))
        columns = [row[1] for row in result.fetchall()]

        if "commentary" in columns:
            print("✅ commentary kolom bestaat al — geen migratie nodig.")
            return

        # Voeg nullable kolom toe (bestaande rijen krijgen NULL)
        conn.execute(text("ALTER TABLE hypotheses ADD COLUMN commentary TEXT"))
        conn.commit()
        print("✅ commentary kolom toegevoegd aan hypotheses tabel.")


if __name__ == "__main__":
    migrate()
