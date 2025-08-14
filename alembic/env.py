"""
Alembic environment configuration for WMS Chatbot database migrations.
Supports both online and offline migration modes.
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine

# Import your models and configuration
from src.core.config import get_database_settings
from src.database.models import Base

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata

# Set SQLAlchemy URL from environment
settings = get_database_settings()
config.set_main_option("sqlalchemy.url", settings.postgres_sync_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def include_object(object, name, type_, reflected, compare_to):
    """
    Should we include this object in the migration?
    Exclude certain tables or objects if needed.
    """
    # Skip temporary tables or system tables
    if type_ == "table" and name.startswith("temp_"):
        return False
    
    return True


def do_run_migrations(connection):
    """Run migrations with the provided connection"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
        # PostgreSQL specific options
        render_as_batch=False,
        # Include indexes in autogenerate
        include_indexes=True,
        # Include constraints in autogenerate
        include_constraints=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    """Run migrations in online mode with async support"""
    from sqlalchemy.ext.asyncio import create_async_engine
    
    connectable = create_async_engine(
        settings.postgres_url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Check if we're running in async mode
    if hasattr(config, "cmd_opts") and getattr(config.cmd_opts, "x", None):
        if "async" in config.cmd_opts.x:
            # Run async migrations
            asyncio.run(run_async_migrations())
            return

    # Run sync migrations
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()