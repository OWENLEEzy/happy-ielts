"""Tests for backend/general/nodes.py — _auto_grade and quiz_session logic."""

import random
from datetime import UTC, timedelta
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
    assert result == {
        "quiz_answers": [],
        "quiz_score": 0,
        "phase": "free_qa",
        "fsrs_wrong_items": [],
        "fsrs_review_updates": [],
    }
    types = [e.get("type") for e in events]
    assert "quiz_skipped" in types


# ---------------------------------------------------------------------------
# _get_valid_reshuffled_quiz helper
# ---------------------------------------------------------------------------


def test_get_valid_reshuffled_quiz_filters_legacy_and_shuffles():
    """Helper drops legacy-format questions and shuffles remaining options."""
    from backend.general.nodes import _get_valid_reshuffled_quiz

    valid_q = _make_question(0)
    legacy_q = _make_legacy_question()
    result = _get_valid_reshuffled_quiz([valid_q, legacy_q, valid_q], lesson_id=7)
    assert len(result) == 2
    for q in result:
        assert all(isinstance(o, dict) for o in q["answerOptions"])
        assert sum(1 for o in q["answerOptions"] if o.get("isCorrect")) == 1


def test_get_valid_reshuffled_quiz_deterministic():
    """Same lesson_id always produces the same shuffle."""
    from backend.general.nodes import _get_valid_reshuffled_quiz

    quiz = [_make_question(0), _make_question(1), _make_question(2)]
    r1 = _get_valid_reshuffled_quiz(quiz, lesson_id=42)
    r2 = _get_valid_reshuffled_quiz(quiz, lesson_id=42)
    assert [q["answerOptions"] for q in r1] == [q["answerOptions"] for q in r2]


# ---------------------------------------------------------------------------
# route_start retry_hint logic
# ---------------------------------------------------------------------------


def _make_quiz_with_correct_at(correct_idx: int) -> list[dict]:
    """3-question quiz where each question's correct answer is at index correct_idx."""
    return [_make_question(correct_idx) for _ in range(3)]


def test_route_start_no_prior_returns_empty_hint():
    """No prior session → retry_hint is [], normal mode, goto reading."""
    from langgraph.types import Command

    from backend.general.nodes import route_start

    lesson = _make_lesson(lesson_id=1)
    mock_db = MagicMock()
    mock_db.get_last_session_for_lesson.return_value = None

    with patch("backend.general.nodes.get_db", return_value=mock_db):
        result = route_start({"lesson": lesson, "project": {"id": 1}})

    assert isinstance(result, Command)
    assert result.update is not None
    assert result.update["retry_hint"] == []
    assert result.update["phase"] == "reading"
    assert result.update["session_mode"] == "normal"
    assert result.goto == "reading"
    # [P1#4] new fields initialized
    assert result.update["metacog_question"] is None
    assert result.update["metacog_feedback"] == ""
    assert result.update["review_questions_cache"] == []
    assert result.update["fsrs_review_updates"] == []


def test_route_start_score_below_46_scaffold_mode():
    """Score < 46 → scaffold mode, goto reading."""
    from langgraph.types import Command

    from backend.general.nodes import route_start

    lesson = _make_lesson(lesson_id=1, quiz=_make_quiz_with_correct_at(0))
    mock_db = MagicMock()
    mock_db.get_last_session_for_lesson.return_value = {
        "quiz_score": 30,
        "quiz_answers": [1, 1, 1],
    }

    with patch("backend.general.nodes.get_db", return_value=mock_db):
        result = route_start({"lesson": lesson, "project": {"id": 1}})

    assert isinstance(result, Command)
    assert result.update is not None
    assert result.update["session_mode"] == "scaffold"
    assert result.goto == "reading"


def test_route_start_score_46_to_81_normal_mode():
    """Score 46-81 → normal mode, goto reading."""
    from backend.general.nodes import route_start

    lesson = _make_lesson(lesson_id=1, quiz=_make_quiz_with_correct_at(0))
    mock_db = MagicMock()
    mock_db.get_last_session_for_lesson.return_value = {
        "quiz_score": 60,
        "quiz_answers": [0, 0, 0],
    }

    with patch("backend.general.nodes.get_db", return_value=mock_db):
        result = route_start({"lesson": lesson, "project": {"id": 1}})

    assert result.update is not None
    assert result.update["session_mode"] == "normal"
    assert result.goto == "reading"


def test_route_start_score_above_81_challenge_mode():
    """Score > 81 → challenge mode, goto challenge_quiz."""
    from backend.general.nodes import route_start

    lesson = _make_lesson(lesson_id=1, quiz=_make_quiz_with_correct_at(0))
    mock_db = MagicMock()
    mock_db.get_last_session_for_lesson.return_value = {
        "quiz_score": 85,
        "quiz_answers": [0, 0, 0],
    }

    with patch("backend.general.nodes.get_db", return_value=mock_db):
        result = route_start({"lesson": lesson, "project": {"id": 1}})

    assert result.update is not None
    assert result.update["session_mode"] == "challenge"
    assert result.goto == "challenge_quiz"


def test_route_start_low_score_returns_wrong_questions():
    """Prior session score < 60 → retry_hint populated with wrong answers."""
    from backend.general.nodes import route_start

    # Use a quiz with predictable shuffle: all questions have correct at idx 0.
    lesson = _make_lesson(lesson_id=1, quiz=_make_quiz_with_correct_at(0))
    mock_db = MagicMock()
    mock_db.get_last_session_for_lesson.return_value = {
        "quiz_score": 20,
        "quiz_answers": [1, 1, 1],
    }

    with patch("backend.general.nodes.get_db", return_value=mock_db):
        result = route_start({"lesson": lesson, "project": {"id": 1}})

    assert result.update is not None
    hint = result.update["retry_hint"]
    assert len(hint) > 0
    for item in hint:
        assert "question" in item
        assert "correct_answer" in item


def test_route_start_db_error_degrades_gracefully():
    """DB error in route_start → normal mode, retry_hint is []."""
    from backend.general.nodes import route_start

    lesson = _make_lesson(lesson_id=1)
    mock_db = MagicMock()
    mock_db.get_last_session_for_lesson.side_effect = RuntimeError("DB unavailable")

    with patch("backend.general.nodes.get_db", return_value=mock_db):
        result = route_start({"lesson": lesson, "project": {"id": 1}})

    assert result.update is not None
    assert result.update["retry_hint"] == []
    assert result.update["session_mode"] == "normal"
    assert result.goto == "reading"


# ---------------------------------------------------------------------------
# quiz_session FSRS wrong-item tracking
# ---------------------------------------------------------------------------


def _run_quiz_session_with_answers(lesson_id: int, quiz: list, answers: list) -> dict:
    """Run quiz_session with given answers and return the result dict."""
    lesson = _make_lesson(lesson_id, quiz)
    state = {"lesson": lesson}
    events = []

    def fake_writer(d):
        events.append(d)

    mock_writer = MagicMock(side_effect=fake_writer)

    def fake_interrupt(_data):
        return {"type": "answers", "answers": answers}

    with (
        patch("backend.general.nodes.get_stream_writer", return_value=mock_writer),
        patch("backend.general.nodes.interrupt", side_effect=fake_interrupt),
    ):
        from backend.general import nodes

        return nodes.quiz_session(state)


def test_quiz_session_builds_fsrs_wrong_items():
    """Wrong answers are collected into fsrs_wrong_items with FSRS state."""
    # 3-question quiz, correct answers all at index 0.
    quiz = _make_quiz_with_correct_at(0)
    # Student answers index 1 for all → all wrong.
    result = _run_quiz_session_with_answers(lesson_id=5, quiz=quiz, answers=[1, 1, 1])

    wrong = result.get("fsrs_wrong_items", [])
    assert len(wrong) > 0
    for item in wrong:
        assert "q" in item
        assert "correct" in item
        assert "fsrs_state" in item
        assert isinstance(item["fsrs_state"], dict)


def test_quiz_session_empty_items_on_perfect_score():
    """Perfect score → fsrs_wrong_items is empty."""
    # All questions have correct answer at index 0; student answers 0 everywhere.
    # After shuffle the correct answer may not be at index 0 anymore, so we
    # need to find the correct indices from the reshuffled quiz.
    # Use a lesson_id that keeps correct at position 0 after shuffle (just verify empty).
    # Instead: build quiz where all options are identical except one is correct.
    # The simplest approach: 1-option quiz so shuffle doesn't matter.
    single_opt_quiz = [
        {"question": "Q?", "hint": "", "answerOptions": [{"text": "A", "isCorrect": True}]}
    ]
    result = _run_quiz_session_with_answers(lesson_id=7, quiz=single_opt_quiz, answers=[0])
    assert result.get("fsrs_wrong_items") == []


# ---------------------------------------------------------------------------
# _get_review_questions
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# reading_session Command routing (Task 5)
# ---------------------------------------------------------------------------


def test_reading_routes_to_scaffold_quiz_in_scaffold_mode():
    from langgraph.types import Command

    from backend.general.nodes import reading_session

    lesson = _make_lesson()
    lesson.study_guide = "guide"
    lesson.title = "T"
    state = {"lesson": lesson, "session_mode": "scaffold", "retry_hint": []}

    with (
        patch("backend.general.nodes.get_stream_writer", return_value=MagicMock()),
        patch("backend.general.nodes.interrupt", return_value={"type": "next"}),
    ):
        result = reading_session(state)

    assert isinstance(result, Command)
    assert result.goto == "scaffold_quiz"


def test_reading_routes_to_quiz_in_normal_mode():
    from langgraph.types import Command

    from backend.general.nodes import reading_session

    lesson = _make_lesson()
    lesson.study_guide = "guide"
    lesson.title = "T"
    state = {"lesson": lesson, "session_mode": "normal", "retry_hint": []}

    with (
        patch("backend.general.nodes.get_stream_writer", return_value=MagicMock()),
        patch("backend.general.nodes.interrupt", return_value={"type": "next"}),
    ):
        result = reading_session(state)

    assert isinstance(result, Command)
    assert result.goto == "quiz"


def test_get_review_questions_returns_due_items():
    from datetime import datetime

    from backend.general.nodes import _get_review_questions

    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    quiz_json = [_make_question(0, question="Q1?")]
    lesson_mock = MagicMock()
    lesson_mock.quiz_json = quiz_json
    db_mock = MagicMock()
    db_mock.get_general_lesson.return_value = lesson_mock

    fsrs_due = [{"lesson_id": 1, "q": "Q1?", "correct": "opt_0", "fsrs_state": {"due": past}}]
    result = _get_review_questions(fsrs_due, db_mock, max_count=3)
    assert len(result) == 1
    assert result[0]["question"] == "Q1?"
    assert result[0].get("_is_review") is True
    assert result[0].get("_fsrs_item") is not None


def test_get_review_questions_skips_future_items():
    from datetime import datetime

    from backend.general.nodes import _get_review_questions

    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    db_mock = MagicMock()
    fsrs_due = [{"lesson_id": 1, "q": "Q1?", "correct": "A", "fsrs_state": {"due": future}}]
    result = _get_review_questions(fsrs_due, db_mock, max_count=3)
    assert result == []


def test_get_review_questions_respects_max_count():
    from datetime import datetime

    from backend.general.nodes import _get_review_questions

    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    quiz_json = [_make_question(0, question="Q1?")]
    lesson_mock = MagicMock()
    lesson_mock.quiz_json = quiz_json
    db_mock = MagicMock()
    db_mock.get_general_lesson.return_value = lesson_mock

    fsrs_due = [
        {"lesson_id": 1, "q": "Q1?", "correct": "A", "fsrs_state": {"due": past}},
        {"lesson_id": 1, "q": "Q1?", "correct": "A", "fsrs_state": {"due": past}},
        {"lesson_id": 1, "q": "Q1?", "correct": "A", "fsrs_state": {"due": past}},
    ]
    result = _get_review_questions(fsrs_due, db_mock, max_count=2)
    assert len(result) <= 2


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


# ---------------------------------------------------------------------------
# _grade_and_build_details (Task 5.5)
# ---------------------------------------------------------------------------


def _make_quiz_q(correct_idx: int = 0, n_opts: int = 3, hint: str = "hint text") -> dict:
    """Factory for a single MCQ question dict."""
    return {
        "question": "Q?",
        "hint": hint,
        "answerOptions": [
            {"text": f"opt_{i}", "isCorrect": i == correct_idx, "rationale": "r"}
            for i in range(n_opts)
        ],
    }


def test_grade_perfect_score():
    from backend.general.nodes import _grade_and_build_details

    qs = [_make_quiz_q(correct_idx=0)]
    lesson_score, display_score, details, wrong, reviews = _grade_and_build_details(qs, [0])
    assert lesson_score == 100
    assert display_score == 100
    assert len(wrong) == 0
    assert details[0]["is_correct"] is True


def test_grade_zero_score():
    from backend.general.nodes import _grade_and_build_details

    qs = [_make_quiz_q(correct_idx=0)]
    lesson_score, display_score, details, wrong, reviews = _grade_and_build_details(qs, [1])
    assert lesson_score == 0
    assert len(wrong) == 1


def test_grade_excludes_review_from_lesson_score():
    """[P0#3] Review questions must NOT affect lesson_score used for routing."""
    from backend.general.nodes import _grade_and_build_details

    lesson_q = _make_quiz_q(correct_idx=0)
    review_q = {
        **_make_quiz_q(correct_idx=0),
        "_is_review": True,
        "_fsrs_item": {"lesson_id": 99, "q": "Q?"},
    }
    # Student gets lesson Q right (idx=0), review Q wrong (idx=1)
    lesson_score, display_score, details, wrong, reviews = _grade_and_build_details(
        [lesson_q, review_q], [0, 1]
    )
    assert lesson_score == 100  # only lesson Q counts
    assert display_score == 50  # both count for display
    assert len(reviews) == 1  # review FSRS update tracked
    assert len(wrong) == 0  # review wrong NOT in fsrs_wrong_items


def test_grade_review_correct_tracks_fsrs_update():
    from backend.general.nodes import _grade_and_build_details

    review_q = {
        **_make_quiz_q(correct_idx=0),
        "_is_review": True,
        "_fsrs_item": {"lesson_id": 5, "q": "Q?"},
    }
    _, _, _, _, reviews = _grade_and_build_details([review_q], [0])
    assert len(reviews) == 1
    assert reviews[0][1] is True  # is_correct=True


# ---------------------------------------------------------------------------
# scaffold_quiz (Task 6)
# ---------------------------------------------------------------------------


def _run_scaffold_quiz(lesson_id: int, quiz: list, answers: list) -> tuple[list, dict]:
    """Run scaffold_quiz with given answers; returns (events, result)."""
    lesson = _make_lesson(lesson_id=lesson_id, quiz=quiz)
    state = {"lesson": lesson}
    emitted: list = []
    mock_writer = MagicMock(side_effect=lambda d: emitted.append(d))

    def fake_interrupt(_data):
        return {"type": "answers", "answers": answers}

    with (
        patch("backend.general.nodes.get_stream_writer", return_value=mock_writer),
        patch("backend.general.nodes.interrupt", side_effect=fake_interrupt),
    ):
        from backend.general import nodes

        result = nodes.scaffold_quiz(state)

    return emitted, result


def test_scaffold_quiz_emits_hints_visible_flag():
    """scaffold_quiz sends hints_visible=True in the quiz SSE event."""
    quiz = [_make_quiz_q(correct_idx=0)]
    emitted, _ = _run_scaffold_quiz(lesson_id=1, quiz=quiz, answers=[0])
    quiz_event = next((e for e in emitted if e.get("type") == "quiz"), None)
    assert quiz_event is not None
    assert quiz_event.get("hints_visible") is True


def test_scaffold_quiz_injects_growth_mindset_on_low_score():
    """scaffold_quiz adds growth_mindset_message when lesson_score < 46."""
    quiz = [_make_quiz_q(correct_idx=0) for _ in range(3)]
    # Empty answers → all unanswered → all wrong → score = 0 < 46
    emitted, _ = _run_scaffold_quiz(lesson_id=1, quiz=quiz, answers=[])
    result_event = next((e for e in emitted if e.get("type") == "quiz_result"), None)
    assert result_event is not None
    assert result_event.get("growth_mindset_message") is not None
    assert result_event.get("lesson_score", 100) < 46


# ---------------------------------------------------------------------------
# challenge_quiz (Task 7)
# ---------------------------------------------------------------------------


def _run_challenge_quiz(
    lesson_id: int,
    quiz: list,
    answers: list,
    review_cache: list | None = None,
    project_id: int = 1,
) -> tuple[list, dict]:
    """Run challenge_quiz with given answers; returns (events, result)."""
    lesson = _make_lesson(lesson_id=lesson_id, quiz=quiz)
    state = {
        "lesson": lesson,
        "project": {"id": project_id},
        "review_questions_cache": review_cache if review_cache is not None else [],
    }
    emitted: list = []
    mock_writer = MagicMock(side_effect=lambda d: emitted.append(d))

    def fake_interrupt(_data):
        return {"type": "answers", "answers": answers}

    mock_db = MagicMock()
    mock_db.get_general_student_model_full.return_value = None

    with (
        patch("backend.general.nodes.get_stream_writer", return_value=mock_writer),
        patch("backend.general.nodes.interrupt", side_effect=fake_interrupt),
        patch("backend.general.nodes.get_db", return_value=mock_db),
    ):
        from backend.general import nodes

        result = nodes.challenge_quiz(state)

    return emitted, result


def test_challenge_quiz_hides_hints():
    """challenge_quiz sends hints_visible=False in the quiz SSE event."""
    quiz = [_make_quiz_q(correct_idx=0)]
    emitted, _ = _run_challenge_quiz(lesson_id=1, quiz=quiz, answers=[0])
    quiz_event = next((e for e in emitted if e.get("type") == "quiz"), None)
    assert quiz_event is not None
    assert quiz_event.get("hints_visible") is False


def test_challenge_quiz_strips_internal_fields_from_sse():
    """[P0#2] _is_review and _fsrs_item must not leak to frontend via SSE."""
    review_q = {**_make_quiz_q(0), "_is_review": True, "_fsrs_item": {"lesson_id": 99}}
    quiz = [_make_quiz_q(correct_idx=0)]
    emitted, _ = _run_challenge_quiz(
        lesson_id=1, quiz=quiz, answers=[0, 0], review_cache=[review_q]
    )
    quiz_event = next((e for e in emitted if e.get("type") == "quiz"), None)
    assert quiz_event is not None
    for q in quiz_event.get("questions", []):
        assert "_is_review" not in q
        assert "_fsrs_item" not in q


def test_challenge_quiz_sets_metacog_question_on_correct_answer():
    """challenge_quiz picks metacog_question from first correct non-review answer."""
    # Single-option quiz: idx=0 is always correct regardless of shuffle
    single_opt = [
        {"question": "Why?", "hint": "", "answerOptions": [{"text": "A", "isCorrect": True}]}
    ]
    _, result = _run_challenge_quiz(lesson_id=1, quiz=single_opt, answers=[0])
    assert result.get("metacog_question") is not None
    assert result["metacog_question"]["question"] == "Why?"
    assert result["metacog_question"]["correct_answer"] == "A"


def test_challenge_quiz_no_metacog_when_all_wrong():
    """challenge_quiz sets metacog_question=None when all answers are wrong."""
    quiz = [_make_quiz_q(correct_idx=0)]
    # Empty answers → all unanswered → all wrong → no correct answer → no metacog
    _, result = _run_challenge_quiz(lesson_id=1, quiz=quiz, answers=[])
    assert result.get("metacog_question") is None


def test_challenge_quiz_uses_cached_review_questions():
    """[P0#1] When review_questions_cache is non-empty, DB must NOT be queried."""
    review_cache = [
        {**_make_quiz_q(0), "_is_review": True, "_fsrs_item": {"lesson_id": 5, "q": "Q?"}}
    ]
    quiz = [_make_quiz_q(correct_idx=0)]
    lesson = _make_lesson(lesson_id=1, quiz=quiz)
    state = {
        "lesson": lesson,
        "project": {"id": 1},
        "review_questions_cache": review_cache,
    }
    emitted: list = []
    mock_writer = MagicMock(side_effect=lambda d: emitted.append(d))
    mock_db = MagicMock()

    with (
        patch("backend.general.nodes.get_stream_writer", return_value=mock_writer),
        patch("backend.general.nodes.interrupt", side_effect=lambda _d: {"answers": [0, 0]}),
        patch("backend.general.nodes.get_db", return_value=mock_db),
    ):
        from backend.general import nodes

        nodes.challenge_quiz(state)

    mock_db.get_general_student_model_full.assert_not_called()


# ---------------------------------------------------------------------------
# metacog_session (Task 8)
# ---------------------------------------------------------------------------


async def test_metacog_session_skips_when_no_question():
    """metacog_session returns empty feedback when metacog_question is None."""
    from backend.general.nodes import metacog_session

    state = {"metacog_question": None, "metacog_feedback": ""}
    result = await metacog_session(state)
    assert result["metacog_feedback"] == ""


async def test_metacog_session_skips_when_already_has_feedback():
    """[P1#6] metacog_feedback is the idempotency guard — skip if already set."""
    from backend.general.nodes import metacog_session

    state = {
        "metacog_question": {"question": "Q?", "correct_answer": "A"},
        "metacog_feedback": "Already generated feedback",
    }
    result = await metacog_session(state)
    assert result["metacog_feedback"] == "Already generated feedback"


async def test_metacog_session_emits_prompt_and_feedback():
    """metacog_session emits metacog_prompt then metacog_feedback events."""
    from unittest.mock import AsyncMock

    from backend.general.nodes import metacog_session

    state = {
        "metacog_question": {"question": "Q?", "correct_answer": "A"},
        "metacog_feedback": "",
    }
    emitted: list = []
    mock_writer = MagicMock(side_effect=lambda d: emitted.append(d))
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="Good explanation!")

    with (
        patch("backend.general.nodes.get_stream_writer", return_value=mock_writer),
        patch(
            "backend.general.nodes.interrupt",
            side_effect=lambda _d: {"explanation": "Because A is right"},
        ),
        patch("backend.llm.get_llm", return_value=mock_llm),
    ):
        result = await metacog_session(state)

    prompt_event = next((e for e in emitted if e.get("type") == "metacog_prompt"), None)
    feedback_event = next((e for e in emitted if e.get("type") == "metacog_feedback"), None)
    assert prompt_event is not None
    assert feedback_event is not None
    assert feedback_event["feedback"] == "Good explanation!"
    assert result["metacog_feedback"] == "Good explanation!"
