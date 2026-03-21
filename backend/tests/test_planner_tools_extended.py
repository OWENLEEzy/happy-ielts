"""Unit tests for highlight_key_paragraphs and generate_writing_task planner tools.

backend.planner.tools calls get_db() at module level.  We stub that during
collection so no real DB connection is attempted.  The LLM (_get_llm) is now
a lazy lru_cache function, so no API key is needed at import time.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

# Stub the database singleton so get_db() doesn't connect to a real DB.
_mock_db = MagicMock()
with patch("backend.database.get_db", return_value=_mock_db):
    import backend.planner.tools as _tools_mod  # noqa: E402

    # Expose the @tool objects for use in tests.
    highlight_key_paragraphs = _tools_mod.highlight_key_paragraphs
    generate_writing_task = _tools_mod.generate_writing_task
    load_user_profile = _tools_mod.load_user_profile
    save_daily_lesson = _tools_mod.save_daily_lesson
    scrape_article = _tools_mod.scrape_article
    _trafilatura_scrape = _tools_mod._trafilatura_scrape


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _llm_response(content: str) -> MagicMock:
    """Return a mock LLM response object with a .content attribute."""
    return MagicMock(content=content)


VALID_HIGHLIGHT_JSON = json.dumps({"highlight_indices": [0, 1, 2], "article_logic": "cause_effect"})

VALID_WRITING_TASK_JSON = json.dumps(
    {
        "article_id": 0,
        "mode": "professional",
        "instruction": (
            "Write a professional email summarising the key points of the article for a colleague."
        ),
        "min_words": 100,
    }
)

# A text with exactly 3 paragraphs (split by \n\n)
THREE_PARA_TEXT = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."


# ---------------------------------------------------------------------------
# highlight_key_paragraphs tests
# ---------------------------------------------------------------------------


def test_highlight_returns_valid_indices_and_logic():
    """Happy-path: LLM returns valid JSON; result has correct types."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _llm_response(VALID_HIGHLIGHT_JSON)
    with patch("backend.planner.tools._get_llm", return_value=mock_llm):
        result = highlight_key_paragraphs.invoke(
            {
                "full_text": THREE_PARA_TEXT,
                "user_goal": "improve professional writing",
                "interests": ["technology", "business"],
            }
        )

    assert isinstance(result["highlight_indices"], list)
    assert all(isinstance(i, int) for i in result["highlight_indices"])
    assert result["article_logic"] in ("compare", "cause_effect", "argumentation")


def test_highlight_filters_out_of_range_indices():
    """LLM returns [0, 1, 99] for a 3-paragraph text; 99 must be filtered out."""
    llm_json = json.dumps({"highlight_indices": [0, 1, 99], "article_logic": "argumentation"})
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _llm_response(llm_json)
    with patch("backend.planner.tools._get_llm", return_value=mock_llm):
        result = highlight_key_paragraphs.invoke(
            {
                "full_text": THREE_PARA_TEXT,
                "user_goal": "improve professional writing",
                "interests": ["technology"],
            }
        )

    indices = result["highlight_indices"]
    assert 99 not in indices
    assert 0 in indices
    assert 1 in indices


def test_highlight_retries_on_parse_failure_then_succeeds():
    """First LLM call returns garbage; second returns valid JSON. Result must be returned."""
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        _llm_response("not json at all %%%"),
        _llm_response(VALID_HIGHLIGHT_JSON),
        _llm_response(VALID_HIGHLIGHT_JSON),  # never reached
    ]
    with patch("backend.planner.tools._get_llm", return_value=mock_llm):
        result = highlight_key_paragraphs.invoke(
            {
                "full_text": THREE_PARA_TEXT,
                "user_goal": "improve professional writing",
                "interests": ["technology"],
            }
        )

    assert "highlight_indices" in result
    assert "article_logic" in result
    assert mock_llm.invoke.call_count == 2


def test_highlight_raises_after_3_failures():
    """All 3 LLM calls return unparseable garbage; tool must raise ValueError."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _llm_response("garbage %%% not json")
    with patch("backend.planner.tools._get_llm", return_value=mock_llm):
        with pytest.raises(ValueError, match="3 attempts"):
            highlight_key_paragraphs.invoke(
                {
                    "full_text": THREE_PARA_TEXT,
                    "user_goal": "improve professional writing",
                    "interests": ["technology"],
                }
            )

    assert mock_llm.invoke.call_count == 3


# ---------------------------------------------------------------------------
# generate_writing_task tests
# ---------------------------------------------------------------------------


def test_generate_writing_task_returns_valid_task():
    """Happy-path: LLM returns valid WritingTaskCreate JSON; dict has required keys."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _llm_response(VALID_WRITING_TASK_JSON)
    with patch("backend.planner.tools._get_llm", return_value=mock_llm):
        result = generate_writing_task.invoke(
            {
                "article": {
                    "original_title": "How AI is changing software development",
                    "article_logic": "cause_effect",
                },
                "profile": {
                    "goal": "advance career in tech",
                    "level": 7,
                    "writing_mode": "professional",
                },
            }
        )

    assert "mode" in result
    assert "instruction" in result
    assert "min_words" in result
    assert "article_id" in result


def test_generate_writing_task_retries_on_failure():
    """First call returns garbage; second returns valid JSON. Result must be returned."""
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        _llm_response("bad response ###"),
        _llm_response(VALID_WRITING_TASK_JSON),
        _llm_response(VALID_WRITING_TASK_JSON),  # never reached
    ]
    with patch("backend.planner.tools._get_llm", return_value=mock_llm):
        result = generate_writing_task.invoke(
            {
                "article": {
                    "original_title": "How AI is changing software development",
                    "article_logic": "compare",
                },
                "profile": {
                    "goal": "advance career in tech",
                    "level": 5,
                    "writing_mode": "professional",
                },
            }
        )

    assert "mode" in result
    assert mock_llm.invoke.call_count == 2


def test_generate_writing_task_raises_after_3_failures():
    """All 3 LLM calls return garbage; tool must raise ValueError."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _llm_response("not json @@@ garbage")
    with patch("backend.planner.tools._get_llm", return_value=mock_llm):
        with pytest.raises(ValueError, match="3 attempts"):
            generate_writing_task.invoke(
                {
                    "article": {
                        "original_title": "How AI is changing software development",
                        "article_logic": "argumentation",
                    },
                    "profile": {
                        "goal": "advance career in tech",
                        "level": 6,
                        "writing_mode": "professional",
                    },
                }
            )

    assert mock_llm.invoke.call_count == 3


# ---------------------------------------------------------------------------
# load_user_profile
# ---------------------------------------------------------------------------


def test_load_user_profile_returns_profile_dict():
    """load_user_profile returns profile dict when profile exists."""
    from unittest.mock import MagicMock, patch

    from backend.models import UserProfile

    profile = UserProfile(
        goal="Improve career",
        interests=["tech"],
        level=6,
        bandwidth_minutes=30,
        writing_mode="professional",
    )
    db_mock = MagicMock()
    db_mock.get_user_profile.return_value = profile
    with patch("backend.planner.tools._db", db_mock):
        result = load_user_profile.invoke({})
    assert result["goal"] == "Improve career"
    assert result["level"] == 6


def test_load_user_profile_returns_error_when_none():
    """load_user_profile returns error dict when no profile found."""
    from unittest.mock import MagicMock, patch

    db_mock = MagicMock()
    db_mock.get_user_profile.return_value = None
    with patch("backend.planner.tools._db", db_mock):
        result = load_user_profile.invoke({})
    assert "error" in result


# ---------------------------------------------------------------------------
# save_daily_lesson
# ---------------------------------------------------------------------------

LONG_TEXT_PL = (
    "Para one is a long paragraph with enough text to pass validation requirements. "
    "\n\nPara two contains more content for the article body text. "
    "\n\nPara three concludes the article with additional prose to exceed the minimum."
)

LONG_INSTRUCTION_PL = (
    "Write a professional email addressing the key points of the article above, "
    "demonstrating clear argumentation and structured reasoning in your response."
)


def test_save_daily_lesson_calls_db_and_returns_confirmation():
    """save_daily_lesson persists the article and task and returns a confirmation string."""
    from unittest.mock import MagicMock, patch

    from backend.models import ArticleCreate, WritingTaskCreate

    db_mock = MagicMock()
    db_mock.save_daily_lesson.return_value = (1, 1)

    article = ArticleCreate(
        date="2026-03-19",
        source_url="https://example.com",
        original_title="AI in 2026",
        full_text=LONG_TEXT_PL,
        highlight_indices=[0, 1, 2],
        article_logic="compare",
        topic_tags=["AI"],
    )
    task = WritingTaskCreate(
        article_id=1,
        mode="professional",
        instruction=LONG_INSTRUCTION_PL,
        min_words=100,
    )

    with patch("backend.planner.tools._db", db_mock):
        result = save_daily_lesson.invoke({"article": article, "task": task})
    assert isinstance(result, str)
    assert "AI in 2026" in result
    db_mock.save_daily_lesson.assert_called()


# ---------------------------------------------------------------------------
# highlight_key_paragraphs — empty response branch
# ---------------------------------------------------------------------------


def test_highlight_raises_on_empty_response_then_succeeds():
    """Empty LLM response triggers ValueError; next attempt with valid JSON succeeds."""
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        _llm_response(""),  # empty → raises ValueError internally
        _llm_response(VALID_HIGHLIGHT_JSON),
    ]
    with patch("backend.planner.tools._get_llm", return_value=mock_llm):
        result = highlight_key_paragraphs.invoke(
            {
                "full_text": THREE_PARA_TEXT,
                "user_goal": "improve professional writing",
                "interests": ["technology"],
            }
        )

    assert "highlight_indices" in result
    assert mock_llm.invoke.call_count == 2


# ---------------------------------------------------------------------------
# generate_writing_task — empty response branch
# ---------------------------------------------------------------------------


def test_generate_writing_task_raises_on_empty_response_then_succeeds():
    """Empty LLM response triggers ValueError; next attempt with valid JSON succeeds."""
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        _llm_response(""),  # empty → raises ValueError internally
        _llm_response(VALID_WRITING_TASK_JSON),
    ]
    with patch("backend.planner.tools._get_llm", return_value=mock_llm):
        result = generate_writing_task.invoke(
            {
                "article": {
                    "original_title": "How AI is changing software development",
                    "article_logic": "cause_effect",
                },
                "profile": {
                    "goal": "advance career in tech",
                    "level": 7,
                    "writing_mode": "professional",
                },
            }
        )

    assert "mode" in result
    assert mock_llm.invoke.call_count == 2


# ---------------------------------------------------------------------------
# _get_llm lru_cache (planner/tools.py line 24)
# ---------------------------------------------------------------------------


def test_planner_tools_get_llm_caches_result():
    """_get_llm() calls get_llm() once and returns the cached result on repeat calls."""
    _tools_mod._get_llm.cache_clear()
    mock_llm = MagicMock()
    with patch("backend.planner.tools.get_llm", return_value=mock_llm) as mock_get_llm:
        r1 = _tools_mod._get_llm()
        r2 = _tools_mod._get_llm()
    assert r1 is mock_llm
    assert r1 is r2
    assert mock_get_llm.call_count == 1
    _tools_mod._get_llm.cache_clear()


# ---------------------------------------------------------------------------
# scrape_article (lines 89-104) and _trafilatura_scrape (lines 62-77)
# ---------------------------------------------------------------------------


def test_scrape_article_falls_back_to_trafilatura_when_scraper_is_none():
    """When Scrapling is unavailable, scrape_article delegates to _trafilatura_scrape."""
    with patch.object(
        _tools_mod, "_trafilatura_scrape", return_value="article body"
    ) as mock_scrape:
        result = scrape_article.invoke({"url": "https://example.com"})
    assert result == "article body"
    mock_scrape.assert_called_once_with("https://example.com")


def test_scrape_article_raises_when_trafilatura_also_fails():
    """RuntimeError is raised when both Scrapling and trafilatura fail."""
    with patch.object(_tools_mod, "_trafilatura_scrape", side_effect=RuntimeError("network error")):
        with pytest.raises(RuntimeError, match="Could not scrape"):
            scrape_article.invoke({"url": "https://example.com"})


def test_trafilatura_scrape_returns_extracted_text():
    """_trafilatura_scrape returns text extracted by trafilatura on success."""
    mock_response = MagicMock()
    mock_response.text = "<html><body>Article content here</body></html>"

    mock_http_client = MagicMock()
    mock_http_client.get.return_value = mock_response
    mock_http_ctx = MagicMock()
    mock_http_ctx.__enter__ = MagicMock(return_value=mock_http_client)
    mock_http_ctx.__exit__ = MagicMock(return_value=False)

    with (
        patch("httpx.Client", return_value=mock_http_ctx),
        patch("trafilatura.extract", return_value="Extracted article text"),
    ):
        result = _trafilatura_scrape("https://example.com/article")
    assert result == "Extracted article text"


def test_trafilatura_scrape_raises_when_no_text_extracted():
    """_trafilatura_scrape raises RuntimeError when trafilatura returns None."""
    mock_response = MagicMock()
    mock_response.text = "<html></html>"

    mock_http_client = MagicMock()
    mock_http_client.get.return_value = mock_response
    mock_http_ctx = MagicMock()
    mock_http_ctx.__enter__ = MagicMock(return_value=mock_http_client)
    mock_http_ctx.__exit__ = MagicMock(return_value=False)

    with (
        patch("httpx.Client", return_value=mock_http_ctx),
        patch("trafilatura.extract", return_value=None),
    ):
        with pytest.raises(RuntimeError, match="no extractable text"):
            _trafilatura_scrape("https://example.com/empty")
