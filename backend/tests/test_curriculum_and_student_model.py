"""Unit tests for curriculum.py and student_model.py."""

from __future__ import annotations

import json
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# curriculum.py
# ---------------------------------------------------------------------------


def test_next_logic_type_cycles():
    from backend.curriculum import LOGIC_SEQUENCE, next_logic_type

    for i in range(len(LOGIC_SEQUENCE) * 3):
        assert next_logic_type(i) == LOGIC_SEQUENCE[i % len(LOGIC_SEQUENCE)]


def test_next_logic_type_session_zero():
    from backend.curriculum import next_logic_type

    assert next_logic_type(0) == "argumentation"


def test_compute_current_task_type_no_history():
    from backend.curriculum import compute_current_task_type

    assert compute_current_task_type({}) == "argumentation"


def test_compute_current_task_type_promotion():
    from backend.curriculum import compute_current_task_type

    history = {"argumentation": {"count": 3, "avg_score": 8.0}}
    assert compute_current_task_type(history) == "compare"


def test_compute_current_task_type_not_enough_submissions():
    from backend.curriculum import compute_current_task_type

    history = {"argumentation": {"count": 2, "avg_score": 9.0}}
    assert compute_current_task_type(history) == "argumentation"


def test_compute_current_task_type_avg_below_threshold():
    from backend.curriculum import compute_current_task_type

    history = {"argumentation": {"count": 5, "avg_score": 7.0}}
    assert compute_current_task_type(history) == "argumentation"


def test_compute_current_task_type_demotion_from_compare():
    from backend.curriculum import compute_current_task_type

    history = {
        "argumentation": {"count": 4, "avg_score": 8.0},
        "compare": {"count": 2, "avg_score": 5.5},
    }
    assert compute_current_task_type(history) == "argumentation"


def test_compute_current_task_type_stays_compare_if_compare_ok():
    from backend.curriculum import compute_current_task_type

    history = {
        "argumentation": {"count": 4, "avg_score": 8.0},
        "compare": {"count": 2, "avg_score": 6.5},
    }
    assert compute_current_task_type(history) == "compare"


# ---------------------------------------------------------------------------
# student_model.py — helpers
# ---------------------------------------------------------------------------


def test_compute_streak_empty():
    from backend.student_model import _compute_streak

    assert _compute_streak([]) == 0


def test_compute_streak_today_only():
    from backend.student_model import _compute_streak

    assert _compute_streak([date.today().isoformat()]) == 1


def test_compute_streak_consecutive_ending_today():
    from backend.student_model import _compute_streak

    today = date.today()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(4)]
    assert _compute_streak(dates) == 4


def test_compute_streak_gap_today_counts_yesterday():
    from backend.student_model import _compute_streak

    today = date.today()
    yesterday = today - timedelta(days=1)
    day_before = today - timedelta(days=2)
    assert _compute_streak([yesterday.isoformat(), day_before.isoformat()]) == 2


def test_compute_streak_old_dates_only():
    from backend.student_model import _compute_streak

    old = (date.today() - timedelta(days=10)).isoformat()
    assert _compute_streak([old]) == 0


def test_update_error_patterns_new_weakness():
    from backend.student_model import _update_error_patterns

    result = _update_error_patterns({}, ["run-on sentences"], [])
    assert "run-on sentences" in result
    assert result["run-on sentences"]["total"] == 1
    assert result["run-on sentences"]["trend"] == "stable"


def test_update_error_patterns_improving_trend():
    from backend.student_model import _update_error_patterns

    existing = {"run-on sentences": {"total": 2, "trend": "stable"}}
    result = _update_error_patterns(existing, ["run-on sentences"], ["run-on sentences"])
    assert result["run-on sentences"]["trend"] == "improving"


def test_update_error_patterns_does_not_mutate_existing():
    from backend.student_model import _update_error_patterns

    existing = {"run-on sentences": {"total": 1, "trend": "stable"}}
    _update_error_patterns(existing, ["run-on sentences"], [])
    assert existing["run-on sentences"]["total"] == 1  # original unchanged


def test_update_error_patterns_improving_area_not_in_weaknesses():
    from backend.student_model import _update_error_patterns

    existing = {"thesis": {"total": 3, "trend": "stable"}}
    result = _update_error_patterns(existing, [], ["thesis"])
    assert result["thesis"]["trend"] == "improving"


# ---------------------------------------------------------------------------
# student_model.py — read / write / default
# ---------------------------------------------------------------------------


def test_read_student_model_returns_deepcopy_of_default():
    """Two calls to read when no file exists must return independent dicts."""
    import backend.student_model as sm

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(sm, "STUDENT_MODEL_PATH", Path(tmpdir) / "student_model.json"):
            a = sm.read_student_model()
            b = sm.read_student_model()
            a["levels"]["writing"] = 9
            assert b["levels"]["writing"] == 5  # deep copy — b is not affected


def test_read_write_roundtrip():
    import backend.student_model as sm

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "student_model.json"
        with patch.object(sm, "STUDENT_MODEL_PATH", path):
            data = {"updated": "2026-03-21", "levels": {"writing": 7}}
            sm.write_student_model(data)
            loaded = sm.read_student_model()
            assert loaded["levels"]["writing"] == 7


def test_read_student_model_bad_json_returns_default():
    import backend.student_model as sm

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "student_model.json"
        path.write_text("{not valid json", encoding="utf-8")
        with patch.object(sm, "STUDENT_MODEL_PATH", path):
            result = sm.read_student_model()
            assert result["levels"]["writing"] == 5


# ---------------------------------------------------------------------------
# student_model.py — update_student_model integration
# ---------------------------------------------------------------------------


def _make_reflect(level: int = 6, weaknesses=None, improving=None):
    from backend.models import ReflectHandoff

    return ReflectHandoff(
        date="2026-03-21",
        level_suggestion=level,
        top_weaknesses=weaknesses or ["run-on sentences"],
        improving_areas=improving or [],
        topic_recommendation="Tech",
        task_recommendation="argumentation",
        teaching_insight="Focus on thesis clarity.",
    )


def test_update_student_model_updates_writing_level():
    import backend.student_model as sm

    mock_db = MagicMock()
    mock_db.query_topic_performance.return_value = {}
    mock_db.query_writing_task_history.return_value = {}
    mock_db.count_sessions.return_value = 3
    mock_db.count_articles.return_value = 5
    mock_db.query_session_dates.return_value = [date.today().isoformat()]

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "student_model.json"
        with patch.object(sm, "STUDENT_MODEL_PATH", path):
            result = sm.update_student_model(_make_reflect(level=8), mock_db)
            assert result["levels"]["writing"] == 8


def test_update_student_model_completion_rate_uses_articles_count():
    import backend.student_model as sm

    mock_db = MagicMock()
    mock_db.query_topic_performance.return_value = {}
    mock_db.query_writing_task_history.return_value = {}
    mock_db.count_sessions.return_value = 3
    mock_db.count_articles.return_value = 6  # 3 submissions / 6 articles = 0.5
    mock_db.query_session_dates.return_value = [date.today().isoformat()]

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "student_model.json"
        with patch.object(sm, "STUDENT_MODEL_PATH", path):
            result = sm.update_student_model(_make_reflect(), mock_db)
            assert result["behavior"]["completion_rate"] == 0.5


def test_update_student_model_curriculum_uses_session_count():
    import backend.student_model as sm

    mock_db = MagicMock()
    mock_db.query_topic_performance.return_value = {}
    mock_db.query_writing_task_history.return_value = {}
    mock_db.count_sessions.return_value = 2
    mock_db.count_articles.return_value = 2
    mock_db.query_session_dates.return_value = []

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "student_model.json"
        with patch.object(sm, "STUDENT_MODEL_PATH", path):
            result = sm.update_student_model(_make_reflect(), mock_db)
            assert result["curriculum"]["session_index"] == 2
            from backend.curriculum import next_logic_type

            assert result["curriculum"]["next_logic_type"] == next_logic_type(2)


def test_update_student_model_persists_to_disk():
    import backend.student_model as sm

    mock_db = MagicMock()
    mock_db.query_topic_performance.return_value = {}
    mock_db.query_writing_task_history.return_value = {}
    mock_db.count_sessions.return_value = 1
    mock_db.count_articles.return_value = 1
    mock_db.query_session_dates.return_value = [date.today().isoformat()]

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "student_model.json"
        with patch.object(sm, "STUDENT_MODEL_PATH", path):
            sm.update_student_model(_make_reflect(level=7), mock_db)
            raw = json.loads(path.read_text(encoding="utf-8"))
            assert raw["levels"]["writing"] == 7


# ---------------------------------------------------------------------------
# evaluate_writing depth selection
# ---------------------------------------------------------------------------


def _make_evaluate_state(level: int):
    from backend.models import Article, UserProfile, WritingTask

    article = Article(
        id=1,
        date="2026-03-21",
        source_url="http://x.com",
        original_title="T",
        full_text="x" * 200,
        highlight_indices=[0, 1, 2],
        article_logic="argumentation",
        topic_tags=["tech"],
    )
    profile = UserProfile(
        goal="IELTS",
        interests=["tech"],
        level=level,
        bandwidth_minutes=30,
        writing_mode="ielts_task2",
    )
    task = WritingTask(
        id=1,
        article_id=1,
        mode="ielts_task2",
        instruction="Write an essay about technology and society. Consider the arguments.",
        min_words=100,
    )
    return {
        "today_article": article,
        "user_profile": profile,
        "today_task": task,
        "user_writing": "Technology is important.",
    }


def test_evaluate_writing_uses_basic_depth_for_low_level():
    from unittest.mock import MagicMock
    from unittest.mock import patch as mp

    from backend.models import WritingFeedback
    from backend.tutor.nodes import evaluate_writing

    captured_depth = []

    def mock_run_feedback(user_text, task, user_goal, level, depth="intermediate"):
        captured_depth.append(depth)
        return WritingFeedback(
            overall_score=4,
            grammar_errors=[],
            chinglish_flags=[],
            rewrite_suggestions=["Better version."],
        )

    with (
        mp("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        mp("backend.tutor.nodes.read_student_model", return_value={"levels": {"writing": 3}}),
        mp("backend.tutor.nodes.run_feedback", side_effect=mock_run_feedback),
    ):
        evaluate_writing(_make_evaluate_state(3))

    assert captured_depth[0] == "basic"


def test_evaluate_writing_uses_advanced_depth_for_high_level():
    from unittest.mock import MagicMock
    from unittest.mock import patch as mp

    from backend.models import WritingFeedback
    from backend.tutor.nodes import evaluate_writing

    captured_depth = []

    def mock_run_feedback(user_text, task, user_goal, level, depth="intermediate"):
        captured_depth.append(depth)
        return WritingFeedback(
            overall_score=9,
            grammar_errors=[],
            chinglish_flags=[],
            rewrite_suggestions=["Advanced rewrite."],
        )

    with (
        mp("backend.tutor.nodes.get_stream_writer", return_value=MagicMock()),
        mp("backend.tutor.nodes.read_student_model", return_value={"levels": {"writing": 9}}),
        mp("backend.tutor.nodes.run_feedback", side_effect=mock_run_feedback),
    ):
        evaluate_writing(_make_evaluate_state(9))

    assert captured_depth[0] == "advanced"
