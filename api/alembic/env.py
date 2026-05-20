"""Alembic environment — dual-head configuration for school and independent branches.

Stub — fully implemented in T-003 (database schema migrations).
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic Config object — provides access to values in alembic.ini
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Target metadata — populated in T-003 when models are created
# ---------------------------------------------------------------------------
target_metadata = None

# ---------------------------------------------------------------------------
# Database URL resolution
# ---------------------------------------------------------------------------
DB_URL = os.environ.get("DB_URL", config.get_main_option("sqlalchemy.url", ""))
config.set_main_option("sqlalchemy.url", DB_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection required)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with an active DB connection.

    Supports dual-head (school / independent) via schema_translate_map.
    The active schema is selected by the ALEMBIC_SCHEMA env var set by the
    migration runner script (see T-003).
    """
    schema = os.environ.get("ALEMBIC_SCHEMA", "public")
    schema_translate_map = {None: schema}

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        execution_options={"schema_translate_map": schema_translate_map},
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema=schema,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
