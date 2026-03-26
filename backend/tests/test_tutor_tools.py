"""Tests for backend/tutor/tools.py — explain_word, analyze_sentence, run_feedback."""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.models import WritingTask

LONG_INSTRUCTION = (
    "Write a professional email addressing the key points of the article above, "
    "demonstrating clear argumentation and structured reasoning in your response."
)

VALID_FEEDBACK_JSON = json.dumps(
    {
        "overall_score": 7,
        "grammar_errors": [],
        "chinglish_flags": [],
        "rewrite_suggestions": ["Version A", "Version B"],
    }
)


def _make_task() -> WritingTask:
    return WritingTask(
        id=1,
        article_id=1,
        mode="professional",
        instruction=LONG_INSTRUCTION,
        min_words=100,
    )


def _llm_response(content: str) -> MagicMock:
    return MagicMock(content=content)


# ---------------------------------------------------------------------------
# explain_word
# ---------------------------------------------------------------------------


def test_explain_word_returns_string():
    from backend.tutor.tools import explain_word

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _llm_response("The word explanation in Chinese.")
    with patch("backend.tutor.tools._get_llm", return_value=mock_llm):
        result = explain_word.invoke(
            {"word": "leverage", "context": "We leverage this library.", "level": 5}
        )
    assert isinstance(result, str)
    assert len(result) > 0


def test_explain_word_passes_word_and_level_to_llm():
    from backend.tutor.tools import explain_word

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _llm_response("Explanation text.")
    with patch("backend.tutor.tools._get_llm", return_value=mock_llm):
        explain_word.invoke({"word": "synergy", "context": "The synergy is clear.", "level": 8})

    prompt = mock_llm.invoke.call_args[0][0]
    assert "synergy" in prompt
    assert "8/10" in prompt


def test_explain_word_low_level_in_prompt():
    from backend.tutor.tools import explain_word

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _llm_response("Simple definition.")
    with patch("backend.tutor.tools._get_llm", return_value=mock_llm):
        explain_word.invoke({"word": "cat", "context": "The cat sat.", "level": 2})

    prompt = mock_llm.invoke.call_args[0][0]
    assert "2/10" in prompt


# ---------------------------------------------------------------------------
# analyze_sentence
# ---------------------------------------------------------------------------


def test_analyze_sentence_returns_string():
    from backend.tutor.tools import analyze_sentence

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _llm_response("Sentence analysis result.")
    with patch("backend.tutor.tools._get_llm", return_value=mock_llm):
        result = analyze_sentence.invoke(
            {"sentence": "The quick brown fox jumps over the lazy dog."}
        )
    assert isinstance(result, str)


def test_analyze_sentence_includes_sentence_in_prompt():
    from backend.tutor.tools import analyze_sentence

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _llm_response("Analysis.")
    with patch("backend.tutor.tools._get_llm", return_value=mock_llm):
        analyze_sentence.invoke({"sentence": "Technology transforms industries rapidly."})

    prompt = mock_llm.invoke.call_args[0][0]
    assert "Technology transforms industries rapidly." in prompt


# ---------------------------------------------------------------------------
# run_feedback
# ---------------------------------------------------------------------------


def test_run_feedback_returns_writing_feedback():
    from backend.tutor.tools import run_feedback

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _llm_response(VALID_FEEDBACK_JSON)
    with patch("backend.tutor.tools._get_llm", return_value=mock_llm):
        result = run_feedback(
            user_text="My professional essay text.",
            task=_make_task(),
            user_goal="improve professional writing",
            level=5,
        )
    assert result.overall_score == 7
    assert result.grammar_errors == []
    assert len(result.rewrite_suggestions) == 2


def test_run_feedback_retries_on_parse_failure():
    from backend.tutor.tools import run_feedback

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        _llm_response("not json %%%"),
        _llm_response(VALID_FEEDBACK_JSON),
    ]
    with patch("backend.tutor.tools._get_llm", return_value=mock_llm):
        result = run_feedback(
            user_text="My essay.",
            task=_make_task(),
            user_goal="improve",
            level=4,
        )
    assert result.overall_score == 7
    assert mock_llm.invoke.call_count == 2


def test_run_feedback_raises_after_3_failures():
    from backend.tutor.tools import run_feedback

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _llm_response("garbage %%% not json")
    with patch("backend.tutor.tools._get_llm", return_value=mock_llm):
        with pytest.raises(ValueError, match="3 attempts"):
            run_feedback(
                user_text="My essay.",
                task=_make_task(),
                user_goal="improve",
                level=4,
            )
    assert mock_llm.invoke.call_count == 3


def test_run_feedback_includes_user_text_in_prompt():
    from backend.tutor.tools import run_feedback

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _llm_response(VALID_FEEDBACK_JSON)
    with patch("backend.tutor.tools._get_llm", return_value=mock_llm):
        run_feedback(
            user_text="My unique essay submission text.",
            task=_make_task(),
            user_goal="career advancement",
            level=6,
        )

    prompt = mock_llm.invoke.call_args[0][0]
    assert "My unique essay submission text." in prompt
    assert "career advancement" in prompt
