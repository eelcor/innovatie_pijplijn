"""Alembic configuratie voor Innovatiepijplijn.

Gebruikt SQLite met synchronouse engine (sqlite ondersteunt geen async migraties).
"""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text

from alembic import context

# Alembic configuratie
config = context.config

# Interpret the config's for python.sqlalchemy target
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importeer alle modellen zodat ze bij Base.metadata geregistreerd zijn
import app.models  # noqa: F401
from app.database import Base

# Database path — zelfde als in database.py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "data", "innovatiepijplijn.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Override sqlalchemy.url in alembic.ini
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Model Base voor autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Does not use a real database connection — generates SQL scripts instead.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite requires batch mode
    )

    with context.begin_transaction():
        context.run_migrations()


def include_object(object, name, type_, reflected, compare_to):
    """Exclude FTS5 virtual tables from Alembic migrations.

    FTS5 tables are created separately in database.py via raw SQL.
    """
    if name and name.startswith("search_index"):
        return False
    return True


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with real database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite requires batch mode
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
