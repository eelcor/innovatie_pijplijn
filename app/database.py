"""Database setup en configuratie.

Gebruikt Alembic voor schema-migraties. Bij startup wordt automatisch
opgegraded naar de nieuwste migratie als deze beschikbaar is.
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

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


def init_db():
    """Initialiseer de database met Alembic migraties.

    Voert automatisch `alembic upgrade head` uit om te zorgen dat het
    schema up-to-date is. Als er geen migraties zijn, valt terug op
    create_all voor backward compatibility.
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
            alembic_command.upgrade(config, "head")
        else:
            # Fallback: create_all zonder Alembic
            Base.metadata.create_all(bind=engine)
    except ImportError:
        # Alembic niet geïnstalleerd — fallback naar create_all
        Base.metadata.create_all(bind=engine)
