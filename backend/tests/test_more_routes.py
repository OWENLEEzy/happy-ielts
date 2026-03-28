"""Additional route tests covering run_planner, SSE endpoints, and update_profile
in backend/main.py (previously at 60% coverage).
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import Article, UserProfile
from backend.orchestrator import planner_state as _planner_state

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

LONG_TEXT = (
    "Para one is a long paragraph with enough text to pass validation requirements. "
    "\n\nPara two contains more content for the article body text. "
    "\n\nPara three concludes the article with additional prose to exceed minimum."
)

LONG_INSTRUCTION = (
    "Write a professional email addressing the key points of the article above, "
    "demonstrating clear argumentation and structured reasoning in your response."
)

SAMPLE_PROFILE = UserProfile(
    goal="Read tech articles",
    interests=["AI", "TypeScript"],
    level=6,
    bandwidth_minutes=25,
    writing_mode="professional",
)

SAMPLE_ARTICLE = Article(
    id=1,
    date=date.today().isoformat(),
    source_url="https://example.com",
    original_title="Sample Article",
    full_text=LONG_TEXT,
    highlight_indices=[0, 1, 2],
    article_logic="compare",
    topic_tags=["tech"],
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    mock_cp = MagicMock()
    mock_cp.aget_tuple = AsyncMock(return_value=None)
    app.state.checkpointer = mock_cp
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _mock_db(**method_returns) -> MagicMock:
    db = MagicMock()
    for method, value in method_returns.items():
        getattr(db, method).return_value = value
    return db


# ---------------------------------------------------------------------------
# POST /api/planner/jobs
# ---------------------------------------------------------------------------


def test_run_planner_already_ready(client: TestClient):
    """Returns already_ready status when today's article already exists."""
    mock_db = _mock_db(get_today_article=SAMPLE_ARTICLE)
    with patch("backend.database.get_db", return_value=mock_db):
        r = client.post("/api/planner/jobs")
    assert r.status_code == 200
    assert r.json()["status"] == "already_ready"


def test_run_planner_already_running(client: TestClient):
    """Returns running status when a planner is already in progress for today."""
    today = date.today().isoformat()
    _planner_state[today] = {"status": "running", "error": None}
    mock_db = _mock_db(get_today_article=None)
    with patch("backend.database.get_db", return_value=mock_db):
        r = client.post("/api/planner/jobs")
    assert r.status_code == 200
    assert r.json()["status"] == "running"
    _planner_state.pop(today, None)


def test_run_planner_starts_new_thread(client: TestClient):
    """Starts a daemon thread and returns started status for a fresh run."""
    today = date.today().isoformat()
    _planner_state.pop(today, None)
    mock_db = _mock_db(get_today_article=None)
    mock_thread_instance = MagicMock()
    with (
        patch("backend.database.get_db", return_value=mock_db),
        patch("threading.Thread", return_value=mock_thread_instance),
    ):
        r = client.post("/api/planner/jobs")
    assert r.status_code == 200
    assert r.json()["status"] == "started"
    mock_thread_instance.start.assert_called_once()
    _planner_state.pop(today, None)


# ---------------------------------------------------------------------------
# POST /api/onboarding/message (token yield branch — lines 138-141)
# ---------------------------------------------------------------------------


def test_onboarding_message_streams_token_when_agent_yields_content(client: TestClient):
    """SSE response includes a 'token' event when the agent yields a message."""
    token = MagicMock()
    token.content = "Hello learner, let's start!"

    async def _fake_astream(*_a, **_kw):
        yield (token, {})

    mock_agent = MagicMock()
    mock_agent.astream = _fake_astream
    with patch("backend.onboarding.agent.create_onboarding_agent", return_value=mock_agent):
        r = client.post("/api/onboarding/messages", json={"message": "Hello"})
    assert r.status_code == 200
    assert '"type": "token"' in r.text
    assert "[DONE]" in r.text


def test_onboarding_message_skips_empty_content(client: TestClient):
    """No 'token' event is emitted when the message content is empty."""
    token = MagicMock()
    token.content = ""  # empty → should be skipped

    async def _fake_astream(*_a, **_kw):
        yield (token, {})

    mock_agent = MagicMock()
    mock_agent.astream = _fake_astream
    with patch("backend.onboarding.agent.create_onboarding_agent", return_value=mock_agent):
        r = client.post("/api/onboarding/messages", json={"message": "Hello"})
    assert r.status_code == 200
    assert '"type": "token"' not in r.text
    assert "[DONE]" in r.text


# ---------------------------------------------------------------------------
# POST /api/lesson/action (SSE streaming — lines 191-207)
# ---------------------------------------------------------------------------


def test_lesson_action_streams_graph_chunks(client: TestClient):
    """SSE response contains chunks yielded by the graph."""

    async def fake_astream(*_a, **_kw):
        yield {"type": "review_question", "word": "leverage"}

    mock_graph = MagicMock()
    mock_graph.astream = fake_astream
    with patch("backend.tutor.graph.get_tutor_graph", return_value=mock_graph):
        r = client.post("/api/lessons/today/actions", json={"type": "done_reading"})
    assert r.status_code == 200
    assert "review_question" in r.text
    assert "[DONE]" in r.text


def test_lesson_action_streams_done_when_graph_is_empty(client: TestClient):
    """SSE response ends with [DONE] even when graph yields nothing."""

    async def fake_astream(*_a, **_kw):
        return
        yield  # make it an async generator

    mock_graph = MagicMock()
    mock_graph.astream = fake_astream
    with patch("backend.tutor.graph.get_tutor_graph", return_value=mock_graph):
        r = client.post("/api/lessons/today/actions", json={"type": "done_reading"})
    assert r.status_code == 200
    assert "[DONE]" in r.text


# ---------------------------------------------------------------------------
# POST /api/lesson/start (SSE streaming — lines 213-240)
# ---------------------------------------------------------------------------


def test_start_lesson_returns_409_when_checkpoint_has_pending_nodes(client: TestClient):
    """Returns 409 with next nodes when a checkpoint with pending nodes already exists."""
    checkpoint_tuple = MagicMock()
    checkpoint_tuple.metadata = {"next": ["reading"]}
    app.state.checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)
    mock_graph = MagicMock()
    mock_state = MagicMock()
    mock_state.tasks = []
    mock_graph.aget_state = AsyncMock(return_value=mock_state)
    with patch("backend.tutor.graph.get_tutor_graph", return_value=mock_graph):
        r = client.post("/api/lessons/today/session")
    assert r.status_code == 409
    data = r.json()
    assert data["status"] == "already_started"
    assert data["next"] == ["reading"]


def test_start_lesson_409_includes_spaced_review_node(client: TestClient):
    """Returns correct node name when paused at spaced_review."""
    checkpoint_tuple = MagicMock()
    checkpoint_tuple.metadata = {"next": ["spaced_review"]}
    app.state.checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)
    mock_graph = MagicMock()
    mock_state = MagicMock()
    mock_state.tasks = []
    mock_graph.aget_state = AsyncMock(return_value=mock_state)
    with patch("backend.tutor.graph.get_tutor_graph", return_value=mock_graph):
        r = client.post("/api/lessons/today/session")
    assert r.status_code == 409
    assert r.json()["next"] == ["spaced_review"]


def test_start_lesson_streams_initial_chunks(client: TestClient):
    """Streams initial graph chunks when no prior checkpoint exists."""
    app.state.checkpointer.aget_tuple = AsyncMock(return_value=None)

    async def fake_astream(*_a, **_kw):
        yield {"type": "loading"}

    mock_graph = MagicMock()
    mock_graph.astream = fake_astream
    with patch("backend.tutor.graph.get_tutor_graph", return_value=mock_graph):
        r = client.post("/api/lessons/today/session")
    assert r.status_code == 200
    assert "[DONE]" in r.text
    assert "loading" in r.text


def test_start_lesson_returns_409_when_checkpoint_metadata_has_next_empty(client: TestClient):
    """Returns 200 (not 409) when checkpoint exists but next is an empty list."""
    checkpoint_tuple = MagicMock()
    checkpoint_tuple.metadata = {"next": []}  # falsy list → not "already started"
    app.state.checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)

    async def fake_astream(*_a, **_kw):
        yield {"type": "start"}

    mock_graph = MagicMock()
    mock_graph.astream = fake_astream
    with patch("backend.tutor.graph.get_tutor_graph", return_value=mock_graph):
        r = client.post("/api/lessons/today/session")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# PATCH /api/profile (lines 259-284)
# ---------------------------------------------------------------------------


def test_update_profile_returns_404_when_profile_missing(client: TestClient):
    """Returns 404 when no profile exists to update."""
    mock_db = _mock_db(get_user_profile=None)
    with patch("backend.database.get_db", return_value=mock_db):
        r = client.patch("/api/profile", json={"interests_update": "more AI content"})
    assert r.status_code == 404


def test_update_profile_calls_llm_and_returns_updated_interests(client: TestClient):
    """Calls LLM with_structured_output to merge interests, then persists and returns profile."""
    from pydantic import BaseModel

    class _FakeInterestList(BaseModel):
        interests: list[str]

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.invoke.return_value = _FakeInterestList(
        interests=["AI", "Machine Learning", "NLP"]
    )
    mock_db = _mock_db(get_user_profile=SAMPLE_PROFILE)
    with (
        patch("backend.database.get_db", return_value=mock_db),
        patch("backend.llm.get_llm", return_value=mock_llm),
    ):
        r = client.patch("/api/profile", json={"interests_update": "add NLP topics"})
    assert r.status_code == 200
    data = r.json()
    assert data["interests"] == ["AI", "Machine Learning", "NLP"]
    mock_db.upsert_user_profile.assert_called_once()


# ---------------------------------------------------------------------------
# POST /api/planner/prepare-next
# ---------------------------------------------------------------------------


def test_prepare_next_endpoint_triggers_planner(client: TestClient):
    """prepare-next should start the planner background task."""
    mock_db = _mock_db(get_article_for_date=None)
    with (
        patch("backend.database.get_db", return_value=mock_db),
        patch("backend.orchestrator._start_planner_thread"),
    ):
        r = client.post("/api/planner/jobs/next")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("started", "already_ready")
    assert "date" in data


def test_prepare_next_skips_if_already_ready(client: TestClient):
    """If tomorrow's lesson exists, endpoint returns already_ready."""
    from datetime import timedelta

    from backend.models import Article

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    mock_article = Article(
        id=1,
        date=tomorrow,
        source_url="http://x.com",
        original_title="Tomorrow",
        full_text="x" * 200,
        highlight_indices=[0, 1, 2],
        article_logic="compare",
        topic_tags=["tech"],
    )
    mock_db = _mock_db(get_article_for_date=mock_article)
    with patch("backend.database.get_db", return_value=mock_db):
        r = client.post("/api/planner/jobs/next")
    assert r.json()["status"] == "already_ready"
