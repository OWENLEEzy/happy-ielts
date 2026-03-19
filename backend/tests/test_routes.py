"""FastAPI route smoke tests using TestClient with Database mocked at the source."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import (
    Article,
    UserProfile,
    VocabItem,
    WritingTask,
)

# ---------------------------------------------------------------------------
# Shared sample data
# ---------------------------------------------------------------------------

LONG_TEXT = (
    "Para one is a long paragraph with enough text to pass validation requirements. "
    "\n\nPara two contains more content for the article body text. "
    "\n\nPara three concludes the article with additional prose."
)

LONG_INSTRUCTION = (
    "Write a professional email addressing the key points of the article above, "
    "demonstrating clear argumentation and structured reasoning in your response."
)

SAMPLE_ARTICLE = Article(
    id=1,
    date=date.today().isoformat(),
    source_url="https://example.com",
    original_title="Sample Article",
    full_text=LONG_TEXT,
    highlight_indices=[0, 1],
    article_logic="compare",
    topic_tags=["tech"],
)

SAMPLE_TASK = WritingTask(
    id=1,
    article_id=1,
    mode="professional",
    instruction=LONG_INSTRUCTION,
    min_words=100,
)

SAMPLE_PROFILE = UserProfile(
    goal="Read tech articles",
    interests=["AI", "TypeScript"],
    level=6,
    bandwidth_minutes=25,
    writing_mode="professional",
)

SAMPLE_VOCAB = VocabItem(
    id=1,
    word="leverage",
    context_sentence="We can leverage this approach.",
    source="reading_click",
    next_review=date.today().isoformat(),
    fsrs_state={"due": date.today().isoformat(), "stability": 1.0},
    article_id=1,
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """TestClient that pre-populates app.state.checkpointer to avoid lifespan errors."""
    mock_cp = MagicMock()
    app.state.checkpointer = mock_cp
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _mock_db(**method_returns) -> MagicMock:
    """Create a mock Database instance with the given method return values."""
    db = MagicMock()
    for method, value in method_returns.items():
        getattr(db, method).return_value = value
    return db


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# GET /api/vocab — patches backend.database.Database (lazy import in route)
# ---------------------------------------------------------------------------


def test_get_vocab_empty(client: TestClient):
    """Returns 200 with empty list when no vocab items exist."""
    with patch("backend.database.Database") as MockDb:
        MockDb.return_value.get_all_vocab_items.return_value = []
        r = client.get("/api/vocab")
    assert r.status_code == 200
    assert r.json() == []


def test_get_vocab_with_items(client: TestClient):
    """Returns 200 with serialised vocab items."""
    with patch("backend.database.Database") as MockDb:
        MockDb.return_value.get_all_vocab_items.return_value = [SAMPLE_VOCAB]
        r = client.get("/api/vocab")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["word"] == "leverage"


# ---------------------------------------------------------------------------
# GET /api/profile
# ---------------------------------------------------------------------------


def test_get_profile_not_found(client: TestClient):
    """Returns 404 when no profile exists."""
    with patch("backend.database.Database") as MockDb:
        MockDb.return_value.get_user_profile.return_value = None
        r = client.get("/api/profile")
    assert r.status_code == 404


def test_get_profile_exists(client: TestClient):
    """Returns 200 with profile when one exists."""
    with patch("backend.database.Database") as MockDb:
        MockDb.return_value.get_user_profile.return_value = SAMPLE_PROFILE
        r = client.get("/api/profile")
    assert r.status_code == 200
    data = r.json()
    assert data["goal"] == "Read tech articles"
    assert data["writing_mode"] == "professional"


# ---------------------------------------------------------------------------
# GET /api/lesson/today
# ---------------------------------------------------------------------------


def test_get_lesson_today_not_ready(client: TestClient):
    """Returns 404 when planner hasn't run yet."""
    with patch("backend.database.Database") as MockDb:
        MockDb.return_value.get_today_article.return_value = None
        MockDb.return_value.get_today_writing_task.return_value = None
        r = client.get("/api/lesson/today")
    assert r.status_code == 404


def test_get_lesson_today_ready(client: TestClient):
    """Returns 200 with article and task when lesson is ready."""
    with patch("backend.database.Database") as MockDb:
        MockDb.return_value.get_today_article.return_value = SAMPLE_ARTICLE
        MockDb.return_value.get_today_writing_task.return_value = SAMPLE_TASK
        r = client.get("/api/lesson/today")
    assert r.status_code == 200
    data = r.json()
    assert "article" in data
    assert "task" in data
    assert data["article"]["original_title"] == "Sample Article"


def test_get_lesson_today_article_without_task_returns_404(client: TestClient):
    """Returns 404 when article exists but task is missing."""
    with patch("backend.database.Database") as MockDb:
        MockDb.return_value.get_today_article.return_value = SAMPLE_ARTICLE
        MockDb.return_value.get_today_writing_task.return_value = None
        r = client.get("/api/lesson/today")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/onboarding/message
# ---------------------------------------------------------------------------


def test_onboarding_message_missing_message_field_returns_422(client: TestClient):
    """POST with body missing required 'message' field must return 422."""
    r = client.post("/api/onboarding/message", json={})
    assert r.status_code == 422


def test_onboarding_message_valid_body_accepted(client: TestClient):
    """POST with a valid 'message' field is accepted (not 422)."""

    # Stub out the onboarding agent so no LLM call is made
    async def _fake_astream(*_a, **_kw):
        return
        yield  # make it an async generator

    mock_agent = MagicMock()
    mock_agent.astream = _fake_astream

    with patch("backend.onboarding.agent.create_onboarding_agent", return_value=mock_agent):
        r = client.post("/api/onboarding/message", json={"message": "Hello"})
    assert r.status_code != 422


# ---------------------------------------------------------------------------
# GET /api/onboarding/status
# ---------------------------------------------------------------------------


def test_onboarding_status_not_ready(client: TestClient):
    with patch("backend.database.Database") as MockDb:
        MockDb.return_value.get_user_profile.return_value = None
        r = client.get("/api/onboarding/status")
    assert r.status_code == 200
    assert r.json() == {"ready": False}


def test_onboarding_status_ready(client: TestClient):
    with patch("backend.database.Database") as MockDb:
        MockDb.return_value.get_user_profile.return_value = SAMPLE_PROFILE
        r = client.get("/api/onboarding/status")
    assert r.status_code == 200
    assert r.json() == {"ready": True}


# ---------------------------------------------------------------------------
# GET /api/planner/status
# ---------------------------------------------------------------------------


def test_planner_status_not_ready(client: TestClient):
    with patch("backend.database.Database") as MockDb:
        MockDb.return_value.get_today_article.return_value = None
        MockDb.return_value.get_today_writing_task.return_value = None
        r = client.get("/api/planner/status")
    assert r.status_code == 200
    assert r.json() == {"ready": False}


def test_planner_status_ready(client: TestClient):
    with patch("backend.database.Database") as MockDb:
        MockDb.return_value.get_today_article.return_value = SAMPLE_ARTICLE
        MockDb.return_value.get_today_writing_task.return_value = SAMPLE_TASK
        r = client.get("/api/planner/status")
    assert r.status_code == 200
    assert r.json() == {"ready": True}


# ---------------------------------------------------------------------------
# POST /api/onboarding/preferences
# ---------------------------------------------------------------------------


def test_save_preferences_not_found(client: TestClient):
    """Returns 404 when no profile exists yet."""
    with patch("backend.database.Database") as MockDb:
        MockDb.return_value.get_user_profile.return_value = None
        r = client.post(
            "/api/onboarding/preferences",
            json={"bandwidth_minutes": 30, "writing_mode": "professional"},
        )
    assert r.status_code == 404


def test_save_preferences_updates_profile(client: TestClient):
    """Returns 200 and calls upsert when profile exists."""
    with patch("backend.database.Database") as MockDb:
        MockDb.return_value.get_user_profile.return_value = SAMPLE_PROFILE
        r = client.post(
            "/api/onboarding/preferences",
            json={"bandwidth_minutes": 45, "writing_mode": "ielts_task2"},
        )
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    MockDb.return_value.upsert_user_profile.assert_called_once()
