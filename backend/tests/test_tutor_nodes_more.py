"""Tests for spaced_review, reading_session, evaluate_writing in tutor/nodes.py."""

from datetime import date
from unittest.mock import MagicMock, patch

from backend.fsrs_engine import new_card_state
from backend.models import Article, UserProfile, VocabItem, WritingFeedback, WritingTask

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


def _make_vocab(word: str = "leverage") -> VocabItem:
    return VocabItem(
        id=1,
        word=word,
        context_sentence=f"We can {word} this library.",
        source="reading_click",
        next_review=date.today().isoformat(),
        fsrs_state=new_card_state(),
        article_id=None,
    )


def _make_task() -> WritingTask:
    return WritingTask(
        id=1,
        article_id=1,
        mode="professional",
        instruction=LONG_INSTRUCTION,
        min_words=100,
    )


def _make_profile() -> UserProfile:
    return UserProfile(
        goal="Improve writing",
        interests=["tech"],
        level=6,
        bandwidth_minutes=30,
        writing_mode="professional",
    )


def _make_article() -> Article:
    return Article(
        id=1,
        date=date.today().isoformat(),
        source_url="https://example.com",
        original_title="Test Article",
        full_text=LONG_TEXT,
        highlight_indices=[0, 1, 2],
        article_logic="compare",
        topic_tags=["tech"],
    )


def _make_feedback() -> WritingFeedback:
    return WritingFeedback(
        overall_score=8,
        grammar_errors=[],
        chinglish_flags=[],
        rewrite_suggestions=["Version A", "Version B"],
    )


# ---------------------------------------------------------------------------
# spaced_review
# ---------------------------------------------------------------------------


def test_spaced_review_correct_answer_advances_index():
    """Correct answer increments review_index and loops back to spaced_review."""
    from backend.tutor.nodes import spaced_review

    item = _make_vocab("leverage")
    state = _make_state(
        review_queue=[item, _make_vocab("synergy")],
        review_index=0,
    )
    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        patch(
            "backend.tutor.nodes.interrupt",
            return_value={"answer": "leverage", "response_seconds": 3.0},
        ),
        patch("backend.tutor.nodes._db") as mock_db,
    ):
        result = spaced_review(state)

    assert result.goto == "spaced_review"
    assert result.update["review_index"] == 1  # type: ignore[index]
    mock_db.upsert_vocab_item.assert_called_once()


def test_spaced_review_last_item_goes_to_reading():
    """Finishing the last review item routes to reading."""
    from backend.tutor.nodes import spaced_review

    item = _make_vocab("leverage")
    state = _make_state(review_queue=[item], review_index=0)

    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        patch(
            "backend.tutor.nodes.interrupt",
            return_value={"answer": "leverage", "response_seconds": 3.0},
        ),
        patch("backend.tutor.nodes._db"),
    ):
        result = spaced_review(state)

    assert result.goto == "reading"


def test_spaced_review_wrong_answer_still_updates_card():
    """Wrong answer still upserts the vocab item with updated FSRS state."""
    from backend.tutor.nodes import spaced_review

    item = _make_vocab("leverage")
    state = _make_state(review_queue=[item], review_index=0)

    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        patch(
            "backend.tutor.nodes.interrupt",
            return_value={"answer": "wrong_word", "response_seconds": 20.0},
        ),
        patch("backend.tutor.nodes._db") as mock_db,
    ):
        spaced_review(state)

    mock_db.upsert_vocab_item.assert_called_once()


def test_spaced_review_accepts_dict_item_data():
    """spaced_review handles review_queue items stored as dicts (not VocabItem objects)."""
    from backend.tutor.nodes import spaced_review

    item = _make_vocab("leverage")
    state = _make_state(review_queue=[item.model_dump()], review_index=0)

    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        patch(
            "backend.tutor.nodes.interrupt",
            return_value={"answer": "leverage", "response_seconds": 5.0},
        ),
        patch("backend.tutor.nodes._db"),
    ):
        result = spaced_review(state)

    assert result.goto == "reading"


def test_spaced_review_slow_correct_answer_uses_hard_rating():
    """A slow but correct answer (>15s) should still update the card."""
    from backend.tutor.nodes import spaced_review

    item = _make_vocab("leverage")
    state = _make_state(review_queue=[item], review_index=0)

    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        patch(
            "backend.tutor.nodes.interrupt",
            return_value={"answer": "leverage", "response_seconds": 20.0},
        ),
        patch("backend.tutor.nodes._db") as mock_db,
    ):
        spaced_review(state)

    mock_db.upsert_vocab_item.assert_called_once()
    call_arg = mock_db.upsert_vocab_item.call_args[0][0]
    assert call_arg.word == "leverage"


# ---------------------------------------------------------------------------
# reading_session
# ---------------------------------------------------------------------------


def test_reading_session_done_reading_exits_loop():
    """done_reading action breaks the loop and returns Command(goto='writing_task')."""
    from backend.tutor.nodes import reading_session

    state = _make_state(today_article=_make_article(), user_profile=_make_profile())

    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        patch("backend.tutor.nodes.interrupt", return_value={"type": "done_reading"}),
        patch("backend.tutor.nodes._db"),
    ):
        result = reading_session(state)

    assert result.goto == "writing_task"


def test_reading_session_explain_word_action():
    """explain_word action calls explain_word tool and continues the loop."""
    from backend.tutor.nodes import reading_session

    state = _make_state(today_article=_make_article(), user_profile=_make_profile())

    interrupt_responses = [
        {"type": "explain_word", "word": "leverage", "context": "We leverage this."},
        {"type": "done_reading"},
    ]
    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        patch("backend.tutor.nodes.interrupt", side_effect=interrupt_responses),
        patch("backend.tutor.nodes.explain_word") as mock_explain,
        patch("backend.tutor.nodes._db"),
    ):
        mock_explain.invoke.return_value = "Word explanation."
        result = reading_session(state)

    assert result.goto == "writing_task"
    mock_explain.invoke.assert_called_once()


def test_reading_session_explain_word_without_article_skips_vocab_upsert():
    """explain_word without a today_article does not call upsert_vocab_item."""
    from backend.tutor.nodes import reading_session

    state = _make_state(today_article=None, user_profile=_make_profile())

    interrupt_responses = [
        {"type": "explain_word", "word": "leverage", "context": "We leverage this."},
        {"type": "done_reading"},
    ]
    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        patch("backend.tutor.nodes.interrupt", side_effect=interrupt_responses),
        patch("backend.tutor.nodes.explain_word") as mock_explain,
        patch("backend.tutor.nodes._db") as mock_db,
    ):
        mock_explain.invoke.return_value = "Word explanation."
        reading_session(state)

    mock_db.upsert_vocab_item.assert_not_called()


def test_reading_session_explain_word_missing_word_sends_error_and_continues():
    """explain_word without 'word' field sends error event and continues the loop."""
    from backend.tutor.nodes import reading_session

    state = _make_state(today_article=_make_article(), user_profile=_make_profile())

    writer_mock = MagicMock()
    interrupt_responses = [
        {"type": "explain_word"},  # no 'word' key
        {"type": "done_reading"},
    ]
    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=writer_mock),
        patch("backend.tutor.nodes.interrupt", side_effect=interrupt_responses),
        patch("backend.tutor.nodes._db"),
    ):
        result = reading_session(state)

    assert result.goto == "writing_task"
    error_calls = [c for c in writer_mock.call_args_list if "error" in str(c)]
    assert len(error_calls) > 0


def test_reading_session_analyze_sentence_action():
    """analyze_sentence action calls analyze_sentence tool and continues the loop."""
    from backend.tutor.nodes import reading_session

    state = _make_state(today_article=_make_article(), user_profile=_make_profile())

    interrupt_responses = [
        {"type": "analyze_sentence", "sentence": "The quick brown fox."},
        {"type": "done_reading"},
    ]
    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        patch("backend.tutor.nodes.interrupt", side_effect=interrupt_responses),
        patch("backend.tutor.nodes.analyze_sentence") as mock_analyze,
        patch("backend.tutor.nodes._db"),
    ):
        mock_analyze.invoke.return_value = "Sentence analysis."
        result = reading_session(state)

    assert result.goto == "writing_task"
    mock_analyze.invoke.assert_called_once()


def test_reading_session_analyze_sentence_missing_field_sends_error():
    """analyze_sentence without 'sentence' field sends error and continues."""
    from backend.tutor.nodes import reading_session

    state = _make_state(today_article=_make_article(), user_profile=_make_profile())

    writer_mock = MagicMock()
    interrupt_responses = [
        {"type": "analyze_sentence"},  # no 'sentence' key
        {"type": "done_reading"},
    ]
    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=writer_mock),
        patch("backend.tutor.nodes.interrupt", side_effect=interrupt_responses),
        patch("backend.tutor.nodes._db"),
    ):
        result = reading_session(state)

    assert result.goto == "writing_task"
    error_calls = [c for c in writer_mock.call_args_list if "error" in str(c)]
    assert len(error_calls) > 0


def test_reading_session_none_article_and_profile():
    """reading_session handles None article/profile without crashing."""
    from backend.tutor.nodes import reading_session

    state = _make_state(today_article=None, user_profile=None)

    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        patch("backend.tutor.nodes.interrupt", return_value={"type": "done_reading"}),
        patch("backend.tutor.nodes._db"),
    ):
        result = reading_session(state)

    assert result.goto == "writing_task"


# ---------------------------------------------------------------------------
# evaluate_writing
# ---------------------------------------------------------------------------


def test_evaluate_writing_missing_user_text_returns_empty():
    """evaluate_writing returns {} when user_writing is empty string."""
    from backend.tutor.nodes import evaluate_writing

    state = _make_state(
        user_profile=_make_profile(),
        today_task=_make_task(),
        user_writing="",
    )
    with patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()):
        result = evaluate_writing(state)

    assert result == {}


def test_evaluate_writing_missing_task_returns_empty():
    """evaluate_writing returns {} when today_task is None."""
    from backend.tutor.nodes import evaluate_writing

    state = _make_state(
        user_profile=_make_profile(),
        today_task=None,
        user_writing="My essay text.",
    )
    with patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()):
        result = evaluate_writing(state)

    assert result == {}


def test_evaluate_writing_missing_profile_returns_empty():
    """evaluate_writing returns {} when user_profile is None."""
    from backend.tutor.nodes import evaluate_writing

    state = _make_state(
        user_profile=None,
        today_task=_make_task(),
        user_writing="My essay text.",
    )
    with patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()):
        result = evaluate_writing(state)

    assert result == {}


def test_evaluate_writing_happy_path_returns_feedback():
    """evaluate_writing calls run_feedback and returns writing_feedback in state."""
    from backend.tutor.nodes import evaluate_writing

    feedback = _make_feedback()
    state = _make_state(
        user_profile=_make_profile(),
        today_task=_make_task(),
        user_writing="My well-written essay text.",
    )

    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        patch("backend.tutor.nodes.run_feedback", return_value=feedback),
    ):
        result = evaluate_writing(state)

    assert result["writing_feedback"] is feedback
    assert result["writing_feedback"].overall_score == 8
    assert "messages" in result


def test_evaluate_writing_sends_feedback_event_to_writer():
    """evaluate_writing writes a 'feedback' type event via the stream writer."""
    from backend.tutor.nodes import evaluate_writing

    feedback = _make_feedback()
    writer_mock = MagicMock()
    state = _make_state(
        user_profile=_make_profile(),
        today_task=_make_task(),
        user_writing="My essay.",
    )

    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=writer_mock),
        patch("backend.tutor.nodes.run_feedback", return_value=feedback),
    ):
        evaluate_writing(state)

    writer_mock.assert_called()
    feedback_calls = [c for c in writer_mock.call_args_list if "feedback" in str(c)]
    assert len(feedback_calls) > 0


def test_save_results_writes_observation_to_memory(tmp_path):
    """save_results should append an observation to memory when writing_feedback present."""
    import backend.memory as mem_mod

    mem_mod.MEMORY_DIR = tmp_path

    from unittest.mock import MagicMock, patch

    from backend.models import Article, WritingFeedback, WritingTask
    from backend.tutor.nodes import save_results

    mock_db = MagicMock()
    state = {
        "writing_feedback": WritingFeedback(
            overall_score=7,
            grammar_errors=[],
            chinglish_flags=[],
            rewrite_suggestions=[],
        ),
        "today_task": WritingTask(
            id=1,
            article_id=1,
            mode="professional",
            instruction="Write about climate change policy and its effects." * 2,
            min_words=50,
        ),
        "today_article": Article(
            id=1,
            date="2026-03-21",
            source_url="http://x.com",
            original_title="Climate",
            full_text="x" * 200,
            highlight_indices=[0, 1, 2],
            article_logic="argumentation",
            topic_tags=["climate"],
        ),
        "user_writing": "test text here",
        "review_queue": [],
        "review_index": 0,
    }

    with patch("backend.tutor.nodes._db", mock_db):
        save_results(state)

    obs = mem_mod.read_observations(days=7)
    assert len(obs) == 1
    assert "7" in obs[0]["observation"]  # score is in observation
