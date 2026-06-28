#!/usr/bin/env python3
"""Migratie — voeg is_active kolom toe aan tags tabel (default=True)."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine


def migrate():
    """Voeg is_active kolom toe aan de tags tabel."""
    with engine.connect() as conn:
        # Check of kolom al bestaat
        result = conn.execute(text("PRAGMA table_info(tags)"))
        columns = [row[1] for row in result.fetchall()]

        if "is_active" in columns:
            print("✅ is_active kolom bestaat al — geen migratie nodig.")
            return

        # Voeg kolom toe met default=True
        conn.execute(text("ALTER TABLE tags ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))
        conn.commit()
        print("✅ is_active kolom toegevoegd aan tags tabel (default=True).")


if __name__ == "__main__":
    migrate()
