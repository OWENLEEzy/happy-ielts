"""Shared pytest fixtures for backend tests."""

import pytest

from backend.database import Database


@pytest.fixture()
def db():
    """Provide a fresh Database backed by an in-memory SQLite database.

    Each test gets a clean slate with all tables initialised.
    No external DATABASE_URL required.
    """
    database = Database(":memory:")
    yield database
    database._conn_instance.close()
