"""Shared pytest fixtures for backend tests."""

import os

import psycopg2
import psycopg2.extensions
import pytest
from psycopg2 import sql

from backend.database import Database, reset_db

if not os.environ.get("DATABASE_URL"):
    raise RuntimeError(
        "DATABASE_URL not set. PostgreSQL is required to run these tests.\n"
        "Example: DATABASE_URL=postgresql://owenlee@localhost:5432/dynamiclingo_dev "
        "pytest backend/tests/"
    )

# Tables in dependency order (leaf tables first) for TRUNCATE CASCADE
_ALL_TABLES = (
    "writing_submissions",
    "vocab_items",
    "project_sessions",
    "project_lessons",
    "general_student_models",
    "learning_projects",
    "writing_tasks",
    "articles",
    "user_profile",
)


@pytest.fixture()
def db():
    """Provide a Database connected to the local PostgreSQL dev instance.

    Each test gets a clean slate: all tables are truncated before yielding.
    Requires DATABASE_URL to point at a local PostgreSQL database
    (e.g. postgresql://owenlee@localhost:5432/dynamiclingo_dev).
    """
    database = Database()

    # Use a standalone connection for the TRUNCATE so we don't access Database internals.
    # psycopg2.sql.Identifier ensures table names are safely quoted.
    conn: psycopg2.extensions.connection = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn:
            cur = conn.cursor()
            stmt = sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
                sql.SQL(", ").join(sql.Identifier(t) for t in _ALL_TABLES)
            )
            cur.execute(stmt)
    finally:
        conn.close()

    yield database

    database._pool.closeall()
    reset_db()
