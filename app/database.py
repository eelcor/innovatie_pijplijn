"""Database setup en configuratie.

Gebruikt Alembic voor schema-migraties. Bij startup wordt automatisch
opgegraded naar de nieuwste migratie als deze beschikbaar is.
"""

import os
from sqlalchemy import create_engine, event, text as sa_text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.logging_config import logger

# Database path — configureerbaar via DATABASE_PATH env var
# Standaard: data/innovatiepijplijn.db (relatief ten opzichte van projectroot)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "data", "innovatiepijplijn.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# Enable WAL mode for better concurrent reads
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    dbapi_connection.execute("PRAGMA journal_mode=WAL")
    dbapi_connection.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency voor DB sessies."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _check_schema_compatibility() -> None:
    """Fail-fast schema compatibiliteitscheck bij startup.

    Controleert of alle verwachte tabellen en kritieke kolommen aanwezig zijn.
    Geeft een duidelijke melding als het schema niet matcht met de modellen.
    """
    import sqlite3 as sqlite_mod

    # Gebruik verse connectie na migraties (engine pool kan stale zijn)
    engine.dispose()

    # Directe SQLite check voor betrouwbaarheid (omzeil SQLAlchemy cache)
    conn = sqlite_mod.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        # Verwachte tabellen (uit models.py)
        expected_tables = {
            "initiatives", "hypotheses", "curations", "curation_items",
            "central_questions", "initiative_questions", "dossier_notes",
            "dossier_files", "tags", "initiative_tags", "question_tags",
            "mds", "users", "one_pagers",
        }

        missing_tables = expected_tables - existing_tables
        if missing_tables:
            raise RuntimeError(
                f"Schema incompatibiliteit: ontbrekende tabellen: {', '.join(sorted(missing_tables))}. "
                f"Run 'alembic upgrade head' of herstel vanuit een recente backup."
            )

        # Check kritieke v0.2 kolommen op initiatives tabel
        cursor.execute("PRAGMA table_info(initiatives)")
        col_names = {row[1] for row in cursor.fetchall()}
        required_cols = {'cluster', 'afdeling', 'potentie'}
        missing_cols = required_cols - col_names
        if missing_cols:
            raise RuntimeError(
                f"Schema incompatibiliteit: initiatives tabel mist v0.2 kolommen: "
                f"{', '.join(sorted(missing_cols))}. Run 'alembic upgrade head'."
            )
    finally:
        conn.close()


def init_db():
    """Initialiseer de database met Alembic migraties.

    Voert automatisch `alembic upgrade head` uit om te zorgen dat het
    schema up-to-date is. Ondersteupt adopteren van bestaande DB's die
    via SQLAlchemy create_all() zijn aangemaakt (zonder alembic_version).

    Fail-fast: controleert schema compatibiliteit na migratie.
    """
    import app.models  # noqa: F401

    try:
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_command

        # Vind alembic.ini (twee niveau's boven database.py)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alembic_ini = os.path.join(project_root, "alembic.ini")

        if os.path.exists(alembic_ini):
            config = AlembicConfig(alembic_ini)
            # Override database URL
            config.set_main_option("sqlalchemy.url", DATABASE_URL)

            # Adopt-existing-DB: als alembic_version tabel ontbreekt maar
            # de tabellen wel bestaan (gecreëerd via create_all), dan stampen
            # op baseline en daarna upgraden. Op een volledig lege DB
            # NIET stampen — laat Alembic alle migraties uitvoeren.
            has_alembic_version = False
            has_existing_tables = False
            try:
                with engine.connect() as conn:
                    has_alembic_version = conn.execute(
                        sa_text("SELECT 1 FROM alembic_version LIMIT 1")
                    ).fetchone() is not None
                    has_existing_tables = conn.execute(
                        sa_text("SELECT 1 FROM initiatives LIMIT 1")
                    ).fetchone() is not None
            except Exception:
                pass  # Tabellen bestaan nog niet — verse DB

            if not has_alembic_version and has_existing_tables:
                # Bestaande DB zonder Alembic history — stamp op eerste migratie
                try:
                    alembic_command.stamp(config, "79ec42ad9b26")
                    logger.info("Bestaande DB geadopteerd: gestampt op baseline migratie")
                except Exception as e:
                    logger.warning(f"Kon bestaande DB niet stampen: {e}")

            alembic_command.upgrade(config, "head")
        else:
            # Fallback: create_all zonder Alembic
            Base.metadata.create_all(bind=engine)
    except ImportError:
        # Alembic niet geïnstalleerd — fallback naar create_all
        Base.metadata.create_all(bind=engine)

    # Fail-fast schema compatibiliteitscheck
    try:
        _check_schema_compatibility()
    except RuntimeError as e:
        logger.critical(str(e))
        raise
