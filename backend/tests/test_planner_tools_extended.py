"""Unit tests for highlight_key_paragraphs and generate_writing_task planner tools.

Because backend.planner.tools instantiates ChatTongyi and get_db() at module
level, we must stub those calls before the module is imported.  We do this by
inserting lightweight fakes into sys.modules / patching the constructors via
unittest.mock.patch before the real import executes.
"""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Prevent module-level side-effects (ChatTongyi, get_db) from running during
# collection.  We pre-populate sys.modules with stubs for the two transitive
# imports that require live credentials.
# ---------------------------------------------------------------------------


def _stub_langchain_community() -> None:
    """Ensure langchain_community.chat_models.ChatTongyi can be imported safely."""
    # Only patch if the real module hasn't been cleanly imported yet.
    stub_chat = MagicMock()
    stub_chat.ChatTongyi = MagicMock(return_value=MagicMock())
    if "langchain_community.chat_models" not in sys.modules:
        sys.modules["langchain_community.chat_models"] = stub_chat


_stub_langchain_community()

# Stub the database singleton so get_db() doesn't connect to a real DB.
_mock_db = MagicMock()
with patch("backend.database.get_db", return_value=_mock_db):
    # Force a fresh import (or re-use cached) with our stubs in place.
    if "backend.planner.tools" in sys.modules:
        del sys.modules["backend.planner.tools"]
    import backend.planner.tools as _tools_mod  # noqa: E402

    # Expose the @tool objects for use in tests.
    highlight_key_paragraphs = _tools_mod.highlight_key_paragraphs
    generate_writing_task = _tools_mod.generate_writing_task


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
    with patch("backend.planner.tools._llm") as mock_llm:
        mock_llm.invoke.return_value = _llm_response(VALID_HIGHLIGHT_JSON)

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
    with patch("backend.planner.tools._llm") as mock_llm:
        mock_llm.invoke.return_value = _llm_response(llm_json)

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
    with patch("backend.planner.tools._llm") as mock_llm:
        mock_llm.invoke.side_effect = [
            _llm_response("not json at all %%%"),
            _llm_response(VALID_HIGHLIGHT_JSON),
            _llm_response(VALID_HIGHLIGHT_JSON),  # never reached
        ]

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
    with patch("backend.planner.tools._llm") as mock_llm:
        mock_llm.invoke.return_value = _llm_response("garbage %%% not json")

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
    with patch("backend.planner.tools._llm") as mock_llm:
        mock_llm.invoke.return_value = _llm_response(VALID_WRITING_TASK_JSON)

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
    with patch("backend.planner.tools._llm") as mock_llm:
        mock_llm.invoke.side_effect = [
            _llm_response("bad response ###"),
            _llm_response(VALID_WRITING_TASK_JSON),
            _llm_response(VALID_WRITING_TASK_JSON),  # never reached
        ]

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
    with patch("backend.planner.tools._llm") as mock_llm:
        mock_llm.invoke.return_value = _llm_response("not json @@@ garbage")

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
