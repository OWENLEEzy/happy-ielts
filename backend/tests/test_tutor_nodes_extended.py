"""Extended tests for backend/tutor/nodes.py — covers save_results, edge cases."""

from datetime import date
from unittest.mock import patch

from backend.models import (
    Article,
    ChinglishFlag,
    GrammarError,
    UserProfile,
    VocabItem,
    WritingFeedback,
    WritingTask,
)

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

LONG_TEXT = (
    "Para one is a long paragraph with enough text to pass validation requirements. "
    "\n\nPara two contains more content for the article body text. "
    "\n\nPara three concludes the article."
)

LONG_INSTRUCTION = (
    "Write a professional email addressing the key points of the article above, "
    "demonstrating clear argumentation and structured reasoning in your response."
)


def _make_state(**overrides) -> dict:
    defaults: dict = {
        "user_profile": None,
        "today_article": None,
        "today_task": None,
        "review_queue": [],
        "review_index": 0,
        "user_writing": None,
        "writing_feedback": None,
        "messages": [],
    }
    defaults.update(overrides)
    return defaults


def _sample_article() -> Article:
    return Article(
        id=1,
        date=date.today().isoformat(),
        source_url="https://example.com",
        original_title="Test Article",
        full_text=LONG_TEXT,
        highlight_indices=[0, 1],
        article_logic="compare",
        topic_tags=["tech"],
    )


def _sample_task() -> WritingTask:
    return WritingTask(
        id=1,
        article_id=1,
        mode="professional",
        instruction=LONG_INSTRUCTION,
        min_words=100,
    )


def _sample_profile() -> UserProfile:
    return UserProfile(
        goal="Improve writing",
        interests=["tech"],
        level=6,
        bandwidth_minutes=30,
        writing_mode="professional",
    )


def _sample_feedback(n_chinglish: int = 2) -> WritingFeedback:
    flags = [
        ChinglishFlag(
            original=f"phrase_{i}",
            issue="word_choice",
            explanation_zh="使用了不地道的表达",
            native_alternative=f"better_phrase_{i}",
        )
        for i in range(n_chinglish)
    ]
    return WritingFeedback(
        overall_score=7,
        grammar_errors=[
            GrammarError(
                original="He go home",
                correction="He goes home",
                explanation_zh="第三人称单数需要加 s",
            )
        ],
        chinglish_flags=flags,
        rewrite_suggestions=["Version A", "Version B"],
    )


# ---------------------------------------------------------------------------
# route_start — edge cases
# ---------------------------------------------------------------------------


def test_route_start_with_multiple_due_items():
    """review_queue should contain all due items, not just the first."""
    from backend.tutor.nodes import route_start

    items = [
        VocabItem(
            id=i,
            word=f"word{i}",
            context_sentence=f"Sentence {i}",
            source="reading_click",
            next_review=date.today().isoformat(),
            fsrs_state={},
            article_id=None,
        )
        for i in range(3)
    ]

    with patch("backend.tutor.nodes._db") as mock_db:
        mock_db.get_due_vocab_items.return_value = items
        result = route_start(_make_state())

    assert result.goto == "spaced_review"
    assert len(result.update["review_queue"]) == 3  # type: ignore[index]
    assert result.update["review_index"] == 0  # type: ignore[index]


def test_route_start_loads_profile_article_task():
    """route_start writes profile/article/task into the state update."""
    from backend.tutor.nodes import route_start

    article = _sample_article()
    task = _sample_task()
    profile = _sample_profile()

    with patch("backend.tutor.nodes._db") as mock_db:
        mock_db.get_user_profile.return_value = profile
        mock_db.get_today_article.return_value = article
        mock_db.get_today_writing_task.return_value = task
        mock_db.get_due_vocab_items.return_value = []
        result = route_start(_make_state())

    assert result.goto == "reading"
    assert result.update["user_profile"] is profile  # type: ignore[index]
    assert result.update["today_article"] is article  # type: ignore[index]
    assert result.update["today_task"] is task  # type: ignore[index]


def test_route_start_review_index_reset_to_zero():
    """review_index is always reset to 0 when routing to spaced_review."""
    from backend.models import VocabItem
    from backend.tutor.nodes import route_start

    due = VocabItem(
        id=1,
        word="leverage",
        context_sentence="We leverage this.",
        source="reading_click",
        next_review=date.today().isoformat(),
        fsrs_state={},
        article_id=None,
    )

    # Simulate a state that already has a non-zero review_index
    state = _make_state(review_index=5)

    with patch("backend.tutor.nodes._db") as mock_db:
        mock_db.get_due_vocab_items.return_value = [due]
        result = route_start(state)

    assert result.update["review_index"] == 0  # type: ignore[index]


# ---------------------------------------------------------------------------
# save_results
# ---------------------------------------------------------------------------


def test_save_results_persists_submission_and_vocab():
    """save_results must call save_writing_submission and upsert each chinglish flag."""
    from backend.tutor.nodes import save_results

    feedback = _sample_feedback(n_chinglish=2)
    state = _make_state(
        today_article=_sample_article(),
        today_task=_sample_task(),
        user_writing="My writing submission.",
        writing_feedback=feedback,
    )

    with patch("backend.tutor.nodes._db") as mock_db:
        result = save_results(state)

    # Submission saved
    mock_db.save_writing_submission.assert_called_once()
    # Vocab upserted for each chinglish flag
    assert mock_db.upsert_vocab_item.call_count == 2
    # State cleared
    assert result["user_writing"] is None
    assert result["writing_feedback"] is None


def test_save_results_no_feedback_skips_db():
    """save_results does nothing when writing_feedback is None."""
    from backend.tutor.nodes import save_results

    state = _make_state(
        today_task=_sample_task(),
        user_writing="Some text.",
        writing_feedback=None,
    )

    with patch("backend.tutor.nodes._db") as mock_db:
        result = save_results(state)

    mock_db.save_writing_submission.assert_not_called()
    mock_db.upsert_vocab_item.assert_not_called()
    assert result["user_writing"] is None
    assert result["writing_feedback"] is None


def test_save_results_no_user_writing_skips_db():
    """save_results does nothing when user_writing is empty."""
    from backend.tutor.nodes import save_results

    state = _make_state(
        today_task=_sample_task(),
        user_writing="",
        writing_feedback=_sample_feedback(),
    )

    with patch("backend.tutor.nodes._db") as mock_db:
        save_results(state)

    mock_db.save_writing_submission.assert_not_called()


def test_save_results_no_task_skips_db():
    """save_results does nothing when today_task is None."""
    from backend.tutor.nodes import save_results

    state = _make_state(
        today_task=None,
        user_writing="Some text.",
        writing_feedback=_sample_feedback(),
    )

    with patch("backend.tutor.nodes._db") as mock_db:
        save_results(state)

    mock_db.save_writing_submission.assert_not_called()


def test_save_results_zero_chinglish_flags():
    """No vocab upserted when chinglish_flags is empty."""
    from backend.tutor.nodes import save_results

    feedback = _sample_feedback(n_chinglish=0)
    state = _make_state(
        today_article=_sample_article(),
        today_task=_sample_task(),
        user_writing="My writing.",
        writing_feedback=feedback,
    )

    with patch("backend.tutor.nodes._db") as mock_db:
        save_results(state)

    mock_db.save_writing_submission.assert_called_once()
    mock_db.upsert_vocab_item.assert_not_called()


def test_save_results_vocab_source_is_writing_error():
    """Vocab items from chinglish flags must have source='writing_error'."""
    from backend.tutor.nodes import save_results

    feedback = _sample_feedback(n_chinglish=1)
    state = _make_state(
        today_article=_sample_article(),
        today_task=_sample_task(),
        user_writing="My writing.",
        writing_feedback=feedback,
    )

    with patch("backend.tutor.nodes._db") as mock_db:
        save_results(state)

    call_args = mock_db.upsert_vocab_item.call_args_list[0]
    vocab_item = call_args[0][0]  # first positional arg
    assert vocab_item.source == "writing_error"


def test_save_results_article_id_propagated_to_vocab():
    """Vocab items from chinglish flags inherit the article_id."""
    from backend.tutor.nodes import save_results

    article = _sample_article()  # id=1
    feedback = _sample_feedback(n_chinglish=1)
    state = _make_state(
        today_article=article,
        today_task=_sample_task(),
        user_writing="My writing.",
        writing_feedback=feedback,
    )

    with patch("backend.tutor.nodes._db") as mock_db:
        save_results(state)

    vocab_item = mock_db.upsert_vocab_item.call_args_list[0][0][0]
    assert vocab_item.article_id == article.id


def test_save_results_no_article_still_saves_submission():
    """save_results saves the submission even when today_article is None."""
    from backend.tutor.nodes import save_results

    feedback = _sample_feedback(n_chinglish=1)
    state = _make_state(
        today_article=None,
        today_task=_sample_task(),
        user_writing="My writing.",
        writing_feedback=feedback,
    )

    with patch("backend.tutor.nodes._db") as mock_db:
        save_results(state)

    mock_db.save_writing_submission.assert_called_once()
    vocab_item = mock_db.upsert_vocab_item.call_args_list[0][0][0]
    assert vocab_item.article_id is None


# ---------------------------------------------------------------------------
# writing_task node
# ---------------------------------------------------------------------------


def test_writing_task_returns_user_writing_from_action():
    """writing_task stores the 'text' key from the resumed action."""
    from backend.tutor.nodes import writing_task

    task = _sample_task()
    state = _make_state(today_task=task)

    with patch("backend.tutor.nodes.interrupt", return_value={"text": "My essay text here."}):
        result = writing_task(state)

    assert result["user_writing"] == "My essay text here."


def test_writing_task_returns_empty_string_when_text_missing():
    """writing_task gracefully handles missing 'text' key in action."""
    from backend.tutor.nodes import writing_task

    task = _sample_task()
    state = _make_state(today_task=task)

    with patch("backend.tutor.nodes.interrupt", return_value={}):
        result = writing_task(state)

    assert result["user_writing"] == ""


def test_writing_task_uses_task_instruction():
    """writing_task passes instruction and min_words to interrupt."""
    from backend.tutor.nodes import writing_task

    task = _sample_task()
    state = _make_state(today_task=task)

    captured_interrupt_payload: list = []

    def fake_interrupt(payload):
        captured_interrupt_payload.append(payload)
        return {"text": "some response"}

    with patch("backend.tutor.nodes.interrupt", side_effect=fake_interrupt):
        writing_task(state)

    assert len(captured_interrupt_payload) == 1
    payload = captured_interrupt_payload[0]
    assert payload["type"] == "writing_task"
    assert LONG_INSTRUCTION in payload["instruction"]
    assert payload["min_words"] == 100


def test_writing_task_handles_none_task_gracefully():
    """writing_task should not crash when today_task is None."""
    from backend.tutor.nodes import writing_task

    state = _make_state(today_task=None)

    with patch("backend.tutor.nodes.interrupt", return_value={"text": ""}):
        result = writing_task(state)

    assert result["user_writing"] == ""
