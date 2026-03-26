"""Extended tests for backend/tutor/nodes.py — covers save_results, edge cases."""

from datetime import date
from unittest.mock import MagicMock, patch

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
        highlight_indices=[0, 1, 2],
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


# ---------------------------------------------------------------------------
# _extract_sentence — unit tests
# ---------------------------------------------------------------------------


def test_extract_sentence_finds_containing_sentence():
    """`_extract_sentence` returns the sentence that contains the phrase."""
    from backend.tutor.nodes import _extract_sentence

    text = "Climate change is urgent. Scientists are alarmed by the data. Action is needed."
    result = _extract_sentence(text, "alarmed")
    assert result == "Scientists are alarmed by the data."


def test_extract_sentence_case_insensitive():
    """`_extract_sentence` matches regardless of case."""
    from backend.tutor.nodes import _extract_sentence

    text = "He made an inroads into the market. The results were positive."
    result = _extract_sentence(text, "Inroads")
    assert "inroads" in result.lower()


def test_extract_sentence_multi_word_phrase():
    """`_extract_sentence` handles multi-word chinglish phrases."""
    from backend.tutor.nodes import _extract_sentence

    text = "We should do a contribution to the project. Everyone agreed."
    result = _extract_sentence(text, "do a contribution")
    assert "do a contribution" in result


def test_extract_sentence_fallback_when_not_found():
    """`_extract_sentence` returns the phrase itself when no sentence matches."""
    from backend.tutor.nodes import _extract_sentence

    result = _extract_sentence("Completely unrelated text.", "missing_phrase")
    assert result == "missing_phrase is used in this context."


def test_extract_sentence_empty_text_returns_phrase():
    """`_extract_sentence` handles empty text gracefully."""
    from backend.tutor.nodes import _extract_sentence

    result = _extract_sentence("", "word")
    assert result == "word is used in this context."


# ---------------------------------------------------------------------------
# _find_valid_item — unit tests
# ---------------------------------------------------------------------------


def _make_vocab(word: str, context: str, idx: int = 1) -> VocabItem:
    return VocabItem(
        id=idx,
        word=word,
        context_sentence=context,
        source="reading_click",
        next_review=date.today().isoformat(),
        fsrs_state={},
        article_id=None,
    )


def test_find_valid_item_returns_first_valid():
    from backend.tutor.nodes import _find_valid_item

    items = [
        _make_vocab("unprecedented", "AI tools are deployed at unprecedented pace.", i)
        for i in range(3)
    ]
    idx, item = _find_valid_item(items, 0)
    assert idx == 0
    assert item is not None
    assert item.word == "unprecedented"


def test_find_valid_item_skips_empty_context():
    from backend.tutor.nodes import _find_valid_item

    bad = _make_vocab("inroads", "", 0)
    good = _make_vocab("unprecedented", "The unprecedented scale shocked experts.", 1)
    idx, item = _find_valid_item([bad, good], 0)
    assert idx == 1
    assert item is not None
    assert item.word == "unprecedented"


def test_find_valid_item_skips_context_equals_word():
    """Items where context_sentence == word (writing_error bug) are skipped."""
    from backend.tutor.nodes import _find_valid_item

    bad = _make_vocab("do a contribution", "do a contribution", 0)
    good = _make_vocab("make", "You should make a contribution to the project.", 1)
    idx, item = _find_valid_item([bad, good], 0)
    assert idx == 1
    assert item is not None
    assert item.word == "make"


def test_find_valid_item_all_bad_returns_none():
    from backend.tutor.nodes import _find_valid_item

    items = [
        _make_vocab("bad1", "", 0),
        _make_vocab("bad2", "bad2", 1),  # context == word
    ]
    idx, item = _find_valid_item(items, 0)
    assert idx == len(items)
    assert item is None


def test_find_valid_item_respects_start_index():
    from backend.tutor.nodes import _find_valid_item

    items = [
        _make_vocab("first", "The first item is valid.", 0),
        _make_vocab("second", "The second item is valid.", 1),
    ]
    idx, item = _find_valid_item(items, 1)  # skip first
    assert idx == 1
    assert item is not None
    assert item.word == "second"


# ---------------------------------------------------------------------------
# spaced_review — skipping bad items
# ---------------------------------------------------------------------------


def test_spaced_review_skips_to_reading_when_all_items_bad():
    """If all queue items have unusable context, go straight to reading."""
    from unittest.mock import patch

    from backend.tutor.nodes import spaced_review

    bad_items = [
        _make_vocab("word1", "", 0),
        _make_vocab("word2", "word2", 1),
    ]
    state = _make_state(review_queue=bad_items, review_index=0)

    with (
        patch("backend.tutor.nodes.get_stream_writer"),
        patch("backend.tutor.nodes.interrupt"),
    ):
        result = spaced_review(state)

    assert result.goto == "reading"


def test_spaced_review_skips_empty_context_presents_next():
    """spaced_review skips item with empty context and presents the valid one."""
    from unittest.mock import patch

    from backend.tutor.nodes import spaced_review

    bad = _make_vocab("inroads", "", 0)
    good = _make_vocab("unprecedented", "AI deployed at unprecedented pace.", 1)
    state = _make_state(review_queue=[bad, good], review_index=0)

    writer_mock = MagicMock()
    interrupt_mock = MagicMock(return_value={"answer": "unprecedented", "response_seconds": 5.0})

    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=writer_mock),
        patch("backend.tutor.nodes.interrupt", interrupt_mock),
        patch("backend.tutor.nodes._db"),
        patch(
            "backend.tutor.nodes.update_card", return_value={"due": "2026-03-22", "stability": 1.0}
        ),
    ):
        spaced_review(state)

    # The event sent to the writer must reference the good item
    sent_event = writer_mock.call_args[0][0]
    assert sent_event["word"] == "unprecedented"
    assert "______" in sent_event["question"]


# ---------------------------------------------------------------------------
# save_results — context_sentence extracted from user_text
# ---------------------------------------------------------------------------


def test_save_results_context_sentence_extracted_from_user_text():
    """context_sentence is the sentence from user_text containing the flag, not flag.original."""
    from backend.tutor.nodes import save_results

    user_text = (
        "Climate change is a pressing issue. "
        "We must do a contribution to solve it. "
        "Everyone needs to act now."
    )
    feedback = WritingFeedback(
        overall_score=6,
        grammar_errors=[],
        chinglish_flags=[
            ChinglishFlag(
                original="do a contribution",
                issue="word_choice",
                explanation_zh="应使用 make a contribution",
                native_alternative="make a contribution",
            )
        ],
        rewrite_suggestions=[],
    )
    state = _make_state(
        today_article=_sample_article(),
        today_task=_sample_task(),
        user_writing=user_text,
        writing_feedback=feedback,
    )

    with patch("backend.tutor.nodes._db") as mock_db:
        save_results(state)

    vocab_create = mock_db.upsert_vocab_item.call_args[0][0]
    # Must NOT be the phrase itself
    assert vocab_create.context_sentence != "do a contribution"
    # Must be the full sentence containing the phrase
    assert "do a contribution" in vocab_create.context_sentence
    assert vocab_create.context_sentence.startswith("We must")


def test_save_results_context_sentence_fallback_when_phrase_not_in_text():
    """Falls back to flag.original when phrase can't be found in user_text."""
    from backend.tutor.nodes import save_results

    feedback = WritingFeedback(
        overall_score=7,
        grammar_errors=[],
        chinglish_flags=[
            ChinglishFlag(
                original="not_in_text",
                issue="word_choice",
                explanation_zh="test",
                native_alternative="better",
            )
        ],
        rewrite_suggestions=[],
    )
    state = _make_state(
        today_article=_sample_article(),
        today_task=_sample_task(),
        user_writing="This text does not contain that phrase.",
        writing_feedback=feedback,
    )

    with patch("backend.tutor.nodes._db") as mock_db:
        save_results(state)

    vocab_create = mock_db.upsert_vocab_item.call_args[0][0]
    assert (
        vocab_create.context_sentence == "not_in_text is used in this context."
    )  # graceful fallback


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

    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        patch("backend.tutor.nodes.interrupt", return_value={"text": "My essay text here."}),
    ):
        result = writing_task(state)

    assert result["user_writing"] == "My essay text here."


def test_writing_task_returns_empty_string_when_text_missing():
    """writing_task gracefully handles missing 'text' key in action."""
    from backend.tutor.nodes import writing_task

    task = _sample_task()
    state = _make_state(today_task=task)

    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        patch("backend.tutor.nodes.interrupt", return_value={}),
    ):
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

    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        patch("backend.tutor.nodes.interrupt", side_effect=fake_interrupt),
    ):
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

    with (
        patch("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        patch("backend.tutor.nodes.interrupt", return_value={"text": ""}),
    ):
        result = writing_task(state)

    assert result["user_writing"] == ""
