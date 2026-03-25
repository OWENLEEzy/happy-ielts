"""Tests for backend/general/nodes.py — _auto_grade and quiz_session logic."""

import random
from unittest.mock import MagicMock, patch

from backend.general.nodes import _auto_grade

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_question(correct_idx: int, n_opts: int = 4, question: str = "Q?") -> dict:
    """Build a well-formed question dict with n_opts options."""
    opts = [
        {
            "text": f"option_{i}",
            "isCorrect": i == correct_idx,
            "rationale": f"rationale_{i}",
        }
        for i in range(n_opts)
    ]
    return {"question": question, "hint": "hint", "answerOptions": opts}


def _make_lesson(lesson_id: int = 1, quiz: list | None = None) -> MagicMock:
    lesson = MagicMock()
    lesson.id = lesson_id
    lesson.quiz_json = quiz or [_make_question(0), _make_question(1), _make_question(2)]
    lesson.title = f"Lesson {lesson_id}"
    return lesson


# ---------------------------------------------------------------------------
# _auto_grade
# ---------------------------------------------------------------------------


def test_auto_grade_all_correct_index():
    quiz = [_make_question(2), _make_question(0), _make_question(3)]
    assert _auto_grade(quiz, [2, 0, 3]) == 100


def test_auto_grade_all_wrong():
    quiz = [_make_question(0), _make_question(1)]
    assert _auto_grade(quiz, [1, 0]) == 0


def test_auto_grade_partial():
    quiz = [_make_question(0), _make_question(1), _make_question(2), _make_question(3)]
    # first 2 correct, last 2 wrong
    assert _auto_grade(quiz, [0, 1, 0, 0]) == 50


def test_auto_grade_empty_quiz():
    assert _auto_grade([], []) == 100


def test_auto_grade_missing_answers():
    """Unanswered questions count as wrong."""
    quiz = [_make_question(0), _make_question(1), _make_question(2)]
    # Only 1 answer provided for 3 questions
    score = _auto_grade(quiz, [0])
    assert score == 33  # 1/3 * 100


def test_auto_grade_text_fallback():
    """String answer matched against isCorrect option text."""
    quiz = [
        {
            "question": "Q?",
            "answerOptions": [
                {"text": "Paris", "isCorrect": True},
                {"text": "London", "isCorrect": False},
            ],
        }
    ]
    assert _auto_grade(quiz, ["paris"]) == 100
    assert _auto_grade(quiz, ["london"]) == 0


# ---------------------------------------------------------------------------
# Deterministic shuffle
# ---------------------------------------------------------------------------


def test_deterministic_shuffle_same_seed_same_order():
    """Same lesson ID always produces the same shuffle."""
    opts: list[dict] = [{"text": str(i), "isCorrect": i == 0} for i in range(4)]

    def shuffle_with_seed(seed):
        rng = random.Random(seed)
        o = list(opts)
        rng.shuffle(o)
        return [x["text"] for x in o]

    result1 = shuffle_with_seed(42)
    result2 = shuffle_with_seed(42)
    assert result1 == result2


def test_deterministic_shuffle_different_seeds_differ():
    """Different lesson IDs produce different shuffles."""
    opts = [{"text": str(i), "isCorrect": i == 0} for i in range(4)]

    def shuffle_with_seed(seed):
        rng = random.Random(seed)
        o = list(opts)
        rng.shuffle(o)
        return [x["text"] for x in o]

    assert shuffle_with_seed(1) != shuffle_with_seed(2)


def test_deterministic_shuffle_preserves_correctness():
    """After shuffling, exactly one option still has isCorrect=True."""
    quiz = [_make_question(correct_idx=2, n_opts=4)]
    rng = random.Random(99)
    opts = list(quiz[0]["answerOptions"])
    rng.shuffle(opts)
    correct_count = sum(1 for o in opts if o.get("isCorrect"))
    assert correct_count == 1


# ---------------------------------------------------------------------------
# quiz_session legacy format filtering
# ---------------------------------------------------------------------------


def _make_legacy_question(n_opts: int = 4) -> dict:
    """Old NLM format: answerOptions is a list of plain strings."""
    return {
        "question": "Q?",
        "answerOptions": [f"option_{i}" for i in range(n_opts)],
        "rationale": "top-level rationale",
    }


def test_quiz_session_filters_legacy_questions():
    """quiz_session drops questions with string-format answerOptions."""
    valid_q = _make_question(1)
    legacy_q = _make_legacy_question()
    mixed = [valid_q, legacy_q, valid_q]

    valid_only = [
        q for q in mixed if q.get("answerOptions") and isinstance(q["answerOptions"][0], dict)
    ]
    assert len(valid_only) == 2
    # Verify no legacy questions leaked through
    for q in valid_only:
        assert all(isinstance(o, dict) for o in q["answerOptions"])


def test_quiz_session_all_legacy_returns_empty():
    """When every question is legacy format, valid list is empty."""
    all_legacy = [_make_legacy_question() for _ in range(5)]
    valid_only = [
        q for q in all_legacy if q.get("answerOptions") and isinstance(q["answerOptions"][0], dict)
    ]
    assert valid_only == []


# ---------------------------------------------------------------------------
# quiz_session integration (stream writer mock)
# ---------------------------------------------------------------------------


def _run_quiz_session_to_interrupt(lesson_id: int, quiz: list) -> dict:
    """Run quiz_session up to the interrupt point and return interrupt_data."""
    lesson = _make_lesson(lesson_id, quiz)
    state = {"lesson": lesson}
    captured = {}

    class _FakeInterrupt(Exception):
        pass

    def fake_writer(data):
        if data.get("type") == "quiz":
            captured["interrupt_data"] = data

    def fake_interrupt(data):
        raise _FakeInterrupt()

    mock_writer = MagicMock(side_effect=fake_writer)

    # get_stream_writer() returns a writer callable; mock it to return mock_writer
    with (
        patch("backend.general.nodes.get_stream_writer", return_value=mock_writer),
        patch("backend.general.nodes.interrupt", side_effect=fake_interrupt),
    ):
        from backend.general import nodes

        try:
            nodes.quiz_session(state)
        except _FakeInterrupt:
            pass

    return captured.get("interrupt_data", {})


def test_quiz_session_sends_shuffled_questions():
    quiz = [_make_question(0), _make_question(1), _make_question(2)]
    data = _run_quiz_session_to_interrupt(lesson_id=7, quiz=quiz)
    assert data.get("type") == "quiz"
    questions = data.get("questions", [])
    assert len(questions) == 3
    # Each question still has exactly one correct option
    for q in questions:
        assert sum(1 for o in q["answerOptions"] if o.get("isCorrect")) == 1


def test_quiz_session_skips_all_legacy_quiz():
    """quiz_session emits quiz_skipped and returns without interrupt."""
    all_legacy = [_make_legacy_question() for _ in range(3)]
    lesson = _make_lesson(lesson_id=10, quiz=all_legacy)
    state = {"lesson": lesson}
    events = []

    mock_writer = MagicMock(side_effect=lambda d: events.append(d))

    with (
        patch("backend.general.nodes.get_stream_writer", return_value=mock_writer),
        patch("backend.general.nodes.interrupt") as mock_interrupt,
    ):
        from backend.general import nodes

        result = nodes.quiz_session(state)

    mock_interrupt.assert_not_called()
    assert result == {"quiz_answers": [], "quiz_score": 0, "phase": "free_qa"}
    types = [e.get("type") for e in events]
    assert "quiz_skipped" in types


def test_quiz_session_total_matches_valid_count():
    """quiz_result.total reflects filtered question count, not raw DB count."""
    valid_q = _make_question(0)
    legacy_q = _make_legacy_question()
    # 2 valid + 1 legacy = total should be 2
    mixed = [valid_q, valid_q, legacy_q]
    lesson = _make_lesson(lesson_id=5, quiz=mixed)
    state = {"lesson": lesson}
    events = []

    def fake_writer(d):
        events.append(d)

    mock_writer = MagicMock(side_effect=fake_writer)

    resume_value = [0, 0]  # both answers = index 0

    def fake_interrupt(data):
        return {"type": "answers", "answers": resume_value}

    with (
        patch("backend.general.nodes.get_stream_writer", return_value=mock_writer),
        patch("backend.general.nodes.interrupt", side_effect=fake_interrupt),
    ):
        from backend.general import nodes

        nodes.quiz_session(state)

    result_event = next((e for e in events if e.get("type") == "quiz_result"), None)
    assert result_event is not None
    assert result_event["total"] == 2  # not 3
