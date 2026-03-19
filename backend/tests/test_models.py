"""Tests for backend/models.py — field validation and WritingMode constraints."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.models import (
    ArticleCreate,
    ChinglishFlag,
    GrammarError,
    UserProfile,
    VocabItemCreate,
    WritingFeedback,
    WritingSubmissionCreate,
    WritingTaskCreate,
)

LONG_TEXT = (
    "Para one is a long paragraph with enough text to pass validation requirements. "
    "\n\nPara two contains more content for the article body text. "
    "\n\nPara three concludes the article with additional prose to exceed the minimum."
)
LONG_INSTRUCTION = (
    "Write a professional email addressing the key points of the article above, "
    "demonstrating clear argumentation and structured reasoning in your response."
)


# ─── WritingMode / UserProfile ────────────────────────────────────────────────


def test_writing_mode_valid_professional():
    profile = UserProfile(
        goal="Improve writing",
        interests=["tech"],
        level=5,
        bandwidth_minutes=30,
        writing_mode="professional",
    )
    assert profile.writing_mode == "professional"


def test_writing_mode_valid_ielts_task1():
    profile = UserProfile(
        goal="IELTS prep",
        interests=["charts"],
        level=4,
        bandwidth_minutes=30,
        writing_mode="ielts_task1",
    )
    assert profile.writing_mode == "ielts_task1"


def test_writing_mode_valid_ielts_task2():
    profile = UserProfile(
        goal="IELTS prep",
        interests=["essays"],
        level=6,
        bandwidth_minutes=30,
        writing_mode="ielts_task2",
    )
    assert profile.writing_mode == "ielts_task2"


def test_writing_mode_rejects_legacy_ielts():
    """Old 'ielts' alias must be rejected — only the specific task variants are valid."""
    with pytest.raises(ValidationError):
        UserProfile(
            goal="IELTS prep",
            interests=["essays"],
            level=6,
            bandwidth_minutes=30,
            writing_mode="ielts",  # type: ignore[arg-type]
        )


def test_writing_mode_rejects_both():
    """Old 'both' alias must be rejected."""
    with pytest.raises(ValidationError):
        UserProfile(
            goal="IELTS prep",
            interests=["essays"],
            level=6,
            bandwidth_minutes=30,
            writing_mode="both",  # type: ignore[arg-type]
        )


def test_writing_mode_rejects_arbitrary_string():
    with pytest.raises(ValidationError):
        UserProfile(
            goal="Test",
            interests=["x"],
            level=5,
            bandwidth_minutes=20,
            writing_mode="casual",  # type: ignore[arg-type]
        )


# ─── UserProfile field constraints ────────────────────────────────────────────


def test_user_profile_level_too_low():
    with pytest.raises(ValidationError):
        UserProfile(
            goal="Test",
            interests=["x"],
            level=0,
            bandwidth_minutes=20,
            writing_mode="professional",
        )


def test_user_profile_level_too_high():
    with pytest.raises(ValidationError):
        UserProfile(
            goal="Test",
            interests=["x"],
            level=11,
            bandwidth_minutes=20,
            writing_mode="professional",
        )


# ─── ArticleCreate validation ─────────────────────────────────────────────────


def test_article_create_valid():
    article = ArticleCreate(
        date="2026-03-19",
        source_url="https://example.com",
        original_title="Title",
        full_text=LONG_TEXT,
        highlight_indices=[0, 1],
        article_logic="compare",
        topic_tags=["tech"],
    )
    assert article.original_title == "Title"
    assert len(article.highlight_indices) == 2


def test_article_create_full_text_too_short():
    """full_text must be at least 100 characters."""
    with pytest.raises(ValidationError):
        ArticleCreate(
            date="2026-03-19",
            source_url="https://example.com",
            original_title="Title",
            full_text="Short.",
            highlight_indices=[0, 1],
            article_logic="compare",
            topic_tags=["tech"],
        )


def test_article_create_highlight_too_few():
    """highlight_indices requires at least 2 entries."""
    with pytest.raises(ValidationError):
        ArticleCreate(
            date="2026-03-19",
            source_url="https://example.com",
            original_title="Title",
            full_text=LONG_TEXT,
            highlight_indices=[0],
            article_logic="compare",
            topic_tags=["tech"],
        )


def test_article_create_highlight_too_many():
    """highlight_indices allows at most 5 entries."""
    with pytest.raises(ValidationError):
        ArticleCreate(
            date="2026-03-19",
            source_url="https://example.com",
            original_title="Title",
            full_text=LONG_TEXT,
            highlight_indices=[0, 1, 2, 3, 4, 5],
            article_logic="compare",
            topic_tags=["tech"],
        )


def test_article_create_no_topic_tags():
    """At least one topic tag required."""
    with pytest.raises(ValidationError):
        ArticleCreate(
            date="2026-03-19",
            source_url="https://example.com",
            original_title="Title",
            full_text=LONG_TEXT,
            highlight_indices=[0, 1],
            article_logic="compare",
            topic_tags=[],
        )


def test_article_create_too_many_topic_tags():
    with pytest.raises(ValidationError):
        ArticleCreate(
            date="2026-03-19",
            source_url="https://example.com",
            original_title="Title",
            full_text=LONG_TEXT,
            highlight_indices=[0, 1],
            article_logic="compare",
            topic_tags=["a", "b", "c", "d", "e", "f"],
        )


# ─── VocabItemCreate ──────────────────────────────────────────────────────────


def test_vocab_item_fsrs_state_accepts_arbitrary_dict():
    """fsrs_state is dict[str, Any] — any dict structure is valid."""
    item = VocabItemCreate(
        word="serendipity",
        context_sentence="It was pure serendipity.",
        source="reading_click",
        next_review="2026-03-20",
        fsrs_state={"nested": {"a": 1, "b": [1, 2, 3]}, "flag": True, "score": 0.95},
        article_id=None,
    )
    assert item.fsrs_state["flag"] is True
    assert item.fsrs_state["nested"]["a"] == 1


def test_vocab_item_fsrs_state_empty_dict():
    item = VocabItemCreate(
        word="test",
        context_sentence="A test sentence.",
        source="writing_error",
        next_review="2026-03-20",
        fsrs_state={},
        article_id=42,
    )
    assert item.fsrs_state == {}


def test_vocab_item_source_invalid():
    with pytest.raises(ValidationError):
        VocabItemCreate(
            word="test",
            context_sentence="A test sentence.",
            source="unknown_source",  # type: ignore[arg-type]
            next_review="2026-03-20",
            fsrs_state={},
            article_id=None,
        )


# ─── WritingTaskCreate ────────────────────────────────────────────────────────


def test_writing_task_create_instruction_too_short():
    with pytest.raises(ValidationError):
        WritingTaskCreate(
            article_id=1,
            mode="professional",
            instruction="Short.",
            min_words=100,
        )


def test_writing_task_create_min_words_out_of_range():
    with pytest.raises(ValidationError):
        WritingTaskCreate(
            article_id=1,
            mode="professional",
            instruction=LONG_INSTRUCTION,
            min_words=300,
        )


# ─── WritingFeedback ──────────────────────────────────────────────────────────


def test_writing_feedback_score_bounds():
    with pytest.raises(ValidationError):
        WritingFeedback(
            overall_score=11,
            grammar_errors=[],
            chinglish_flags=[],
            rewrite_suggestions=[],
        )

    with pytest.raises(ValidationError):
        WritingFeedback(
            overall_score=0,
            grammar_errors=[],
            chinglish_flags=[],
            rewrite_suggestions=[],
        )


def test_writing_feedback_valid():
    fb = WritingFeedback(
        overall_score=7,
        grammar_errors=[
            GrammarError(
                original="He go to school",
                correction="He goes to school",
                explanation_zh="第三人称单数动词需加 s",
            )
        ],
        chinglish_flags=[
            ChinglishFlag(
                original="we have a meeting",
                issue="word_choice",
                explanation_zh="应使用更强的动词",
                native_alternative="we hold a meeting",
            )
        ],
        rewrite_suggestions=["Rewrite version 1.", "Rewrite version 2."],
    )
    assert fb.overall_score == 7
    assert len(fb.grammar_errors) == 1
    assert len(fb.chinglish_flags) == 1


# ─── WritingSubmissionCreate ──────────────────────────────────────────────────


def test_writing_submission_create_valid():
    sub = WritingSubmissionCreate(
        task_id=1,
        user_text="My essay text here.",
        overall_score=8,
        grammar_errors=[],
        chinglish_flags=[],
        rewrite_suggestions=["Better version."],
        submitted_at=datetime(2026, 3, 19, 12, 0, 0),
    )
    assert sub.task_id == 1
    assert sub.overall_score == 8
