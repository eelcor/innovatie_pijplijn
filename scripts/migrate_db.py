"""Database migratie — voeg ontbrekende kolommen toe aan bestaande tabellen."""

import sqlite3
import os

DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "innovatiepijplijn.db"))


def get_missing_columns(cursor, table_name, expected_columns):
    """Check welke kolommen ontbreken in een tabel."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing = {row[1] for row in cursor.fetchall()}
    return [col for col in expected_columns if col not in existing]


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    migrations = []

    # --- initiatives: mds_id ---
    missing = get_missing_columns(cursor, "initiatives", ["mds_id"])
    if "mds_id" in missing:
        cursor.execute(
            "ALTER TABLE initiatives ADD COLUMN mds_id VARCHAR(36) DEFAULT NULL"
        )
        migrations.append("✅ Added 'mds_id' to initiatives")

    # --- initiatives: trekker, type_ai_gebruik ---
    missing = get_missing_columns(cursor, "initiatives", ["trekker", "type_ai_gebruik"])
    if "trekker" in missing:
        cursor.execute(
            "ALTER TABLE initiatives ADD COLUMN trekker TEXT DEFAULT NULL"
        )
        migrations.append("✅ Added 'trekker' to initiatives")
    if "type_ai_gebruik" in missing:
        # SQLite doesn't support adding enum columns easily, use VARCHAR
        cursor.execute(
            "ALTER TABLE initiatives ADD COLUMN type_ai_gebruik VARCHAR(30) DEFAULT NULL"
        )
        migrations.append("✅ Added 'type_ai_gebruik' to initiatives")

    # --- hypotheses: commentary ---
    missing = get_missing_columns(cursor, "hypotheses", ["commentary"])
    if "commentary" in missing:
        cursor.execute(
            "ALTER TABLE hypotheses ADD COLUMN commentary TEXT DEFAULT NULL"
        )
        migrations.append("✅ Added 'commentary' to hypotheses")

    # --- one_pagers table (nieuwe tabel + kolom toevoegingen) ---
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='one_pagers'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE one_pagers (
                id VARCHAR(36) PRIMARY KEY,
                initiative_id VARCHAR(36) NOT NULL,
                content TEXT NOT NULL,
                purpose TEXT DEFAULT NULL,
                audience TEXT DEFAULT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY (initiative_id) REFERENCES initiatives(id) ON DELETE CASCADE
            )
        """)
        migrations.append("✅ Created 'one_pagers' table")
    else:
        # Voeg ontbrekende kolommen toe aan bestaande tabel
        missing = get_missing_columns(cursor, "one_pagers", ["purpose", "audience", "updated_at"])
        if "purpose" in missing:
            cursor.execute("ALTER TABLE one_pagers ADD COLUMN purpose TEXT DEFAULT NULL")
            migrations.append("✅ Added 'purpose' to one_pagers")
        if "audience" in missing:
            cursor.execute("ALTER TABLE one_pagers ADD COLUMN audience TEXT DEFAULT NULL")
            migrations.append("✅ Added 'audience' to one_pagers")
        if "updated_at" in missing:
            cursor.execute("ALTER TABLE one_pagers ADD COLUMN updated_at DATETIME DEFAULT NULL")
            migrations.append("✅ Added 'updated_at' to one_pagers")

    conn.commit()

    if migrations:
        print("Migraties uitgevoerd:")
        for m in migrations:
            print(f"  {m}")
    else:
        print("Geen migraties nodig — schema is up-to-date.")

    conn.close()


if __name__ == "__main__":
    migrate()
