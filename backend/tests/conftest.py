"""Shared pytest fixtures for backend tests."""

import os

import psycopg
import pytest

import backend.database as db_module
from backend.database import Database


@pytest.fixture()
def db():
    """Provide a Database instance backed by a real Postgres connection.

    Requires DATABASE_URL in the environment; skips the test if absent.
    Truncates all application tables before yielding so each test starts clean.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set — skipping Postgres integration test")

    # Reset module-level singletons so Database() re-initialises cleanly.
    db_module._pool = None  # type: ignore[attr-defined]
    db_module._instance = None  # type: ignore[attr-defined]

    database = Database()

    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(
            "TRUNCATE user_profile, articles, writing_tasks, "
            "writing_submissions, vocab_items RESTART IDENTITY CASCADE"
        )

    yield database

    # Tear-down: close pool and reset singletons.
    pool = db_module._pool  # type: ignore[attr-defined]
    if pool is not None:
        pool.close()
    db_module._pool = None  # type: ignore[attr-defined]
    db_module._instance = None  # type: ignore[attr-defined]
