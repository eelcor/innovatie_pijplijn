"""Database setup en configuratie."""

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
    """Maak alle tabellen aan als ze nog niet bestaan."""
    # Importeer modellen zodat ze geregistreerd worden bij Base.metadata
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
