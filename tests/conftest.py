"""Test configuratie en fixtures."""

import tempfile
import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine as sa_create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session


# --- Test database setup ---

@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory):
    """Sessie-breed pad voor test databases."""
    base = tmp_path_factory.mktemp("dbs")
    return str(base)


@pytest.fixture(scope="function")
def test_db_engine(test_db_path):
    """Maak een frisse test-database engine per test."""
    from app.database import Base

    # Uniek bestand per test
    temp_db = os.path.join(test_db_path, f"test_{id(object())}.db")
    test_url = f"sqlite:///{temp_db}"

    engine = sa_create_engine(test_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
                content,
                content_rowid
            )
        """)
        cursor.close()

    # Importeer modellen en maak tabellen aan
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    yield engine, TestSession, temp_db

    # Cleanup
    Base.metadata.drop_all(bind=engine)
    try:
        os.remove(temp_db)
        os.remove(temp_db + "-shm")
        os.remove(temp_db + "-wal")
    except FileNotFoundError:
        pass


@pytest.fixture(scope="function")
async def test_client(test_db_engine):
    """Maak een async test client met override van get_db."""
    engine, TestSession, _ = test_db_engine

    from app import main, database

    def override_get_db():
        """Sync generator om te matchen met de originele get_db()."""
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    main.app.dependency_overrides[database.get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
    ) as ac:
        yield ac

    main.app.dependency_overrides.clear()
