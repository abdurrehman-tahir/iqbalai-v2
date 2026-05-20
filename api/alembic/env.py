"""Alembic env.py — dual-head configuration for school and independent schemas."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so Alembic can detect schema changes
# (models will be added as features are implemented)
try:
    from app.db.base import Base
    target_metadata = Base.metadata
except ImportError:
    target_metadata = None

# DB URL from environment (overrides alembic.ini)
DB_URL = os.environ.get("DB_URL", config.get_main_option("sqlalchemy.url", ""))


def get_schema_for_branch(branch_label: str) -> str:
    """Map branch label to Postgres schema name."""
    return branch_label  # "school" -> "school", "independent" -> "independent"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL only)."""
    url = DB_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema="public",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (against a live DB)."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = DB_URL

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema="public",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
