"""Tests for backend.general.reflect — trend detection and student model update."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.models import (
    DimensionState,
    GeneralStudentModel,
    LearningChapter,
    LearningLesson,
    LearningMap,
    UserGoalProfile,
)


def _make_profile() -> UserGoalProfile:
    return UserGoalProfile(
        mode="skill",
        topic="吉他",
        motivation="兴趣",
        goal_outcome="婚礼演奏",
        context="婚礼",
        current_level="零基础",
        time_per_week=5,
        duration_weeks=8,
    )


def _setup_project(db) -> tuple[int, int, int]:
    """Create project with 1-chapter map and two lessons. Returns (project_id, lid0, lid1)."""
    profile = _make_profile()
    lmap = LearningMap(
        topic="吉他",
        total_weeks=8,
        chapters=[
            LearningChapter(
                title="基础入门",
                lessons=[LearningLesson(title="认识吉他"), LearningLesson(title="基本和弦")],
            )
        ],
    )
    pid = db.create_general_project("吉他", profile, tier="free")
    db.update_general_project_profile_and_map(pid, profile, lmap)
    db.upsert_general_lesson(pid, 0, 0, "认识吉他", "guide", [], [])
    db.upsert_general_lesson(pid, 0, 1, "基本和弦", "guide", [], [])

    lessons = db.get_project_lessons(pid)
    lid0 = lessons[0].id
    lid1 = lessons[1].id
    return pid, lid0, lid1


def _setup_two_chapter_project(db) -> tuple[int, int, int]:
    """Create project with 2-chapter map and one lesson each. Returns (project_id, lid0, lid1)."""
    profile = _make_profile()
    lmap = LearningMap(
        topic="吉他",
        total_weeks=8,
        chapters=[
            LearningChapter(title="基础入门", lessons=[LearningLesson(title="认识吉他")]),
            LearningChapter(title="进阶技巧", lessons=[LearningLesson(title="指弹练习")]),
        ],
    )
    pid = db.create_general_project("吉他", profile, tier="free")
    db.update_general_project_profile_and_map(pid, profile, lmap)
    db.upsert_general_lesson(pid, 0, 0, "认识吉他", "guide", [], [])
    db.upsert_general_lesson(pid, 1, 0, "指弹练习", "guide", [], [])

    lessons = db.get_project_lessons(pid)
    # lessons are ordered by (chapter, lesson): [认识吉他, 指弹练习]
    lid0 = lessons[0].id
    lid1 = lessons[1].id
    return pid, lid0, lid1


@pytest.mark.asyncio
async def test_reflect_trend_improving(db):
    """Two sessions with rising score → trend == improving."""
    pid, lid, _ = _setup_project(db)
    db.save_general_session(pid, lid, [], quiz_score=40, qa_history=[])
    db.save_general_session(pid, lid, [], quiz_score=80, qa_history=[])

    with (
        patch("backend.general.reflect.get_db", return_value=db),
        patch("backend.general.researcher.run_targeted_research", new_callable=AsyncMock),
    ):
        from backend.general.reflect import run_reflect

        await run_reflect(pid)

    dashboard = db.get_general_project_dashboard(pid)
    assert dashboard["dimensions"]["基础入门"]["trend"] == "improving"


@pytest.mark.asyncio
async def test_reflect_trend_worsening(db):
    """Two sessions with falling score → trend == worsening."""
    pid, lid, _ = _setup_project(db)
    db.save_general_session(pid, lid, [], quiz_score=80, qa_history=[])
    db.save_general_session(pid, lid, [], quiz_score=30, qa_history=[])

    with (
        patch("backend.general.reflect.get_db", return_value=db),
        patch("backend.general.researcher.run_targeted_research", new_callable=AsyncMock),
    ):
        from backend.general.reflect import run_reflect

        await run_reflect(pid)

    dashboard = db.get_general_project_dashboard(pid)
    assert dashboard["dimensions"]["基础入门"]["trend"] == "worsening"


@pytest.mark.asyncio
async def test_reflect_trend_stable_single_session(db):
    """Single session → trend == stable."""
    pid, lid, _ = _setup_project(db)
    db.save_general_session(pid, lid, [], quiz_score=60, qa_history=[])

    with (
        patch("backend.general.reflect.get_db", return_value=db),
        patch("backend.general.researcher.run_targeted_research", new_callable=AsyncMock),
    ):
        from backend.general.reflect import run_reflect

        await run_reflect(pid)

    dashboard = db.get_general_project_dashboard(pid)
    assert dashboard["dimensions"]["基础入门"]["trend"] == "stable"


@pytest.mark.asyncio
async def test_reflect_goal_progress_written(db):
    """goal_progress counts mastered chapters (>= 0.5), not mean mastery."""
    pid, lid0, lid1 = _setup_project(db)
    # Both lessons are in chapter 0 ("基础入门"), so they share one dimension.
    db.save_general_session(pid, lid0, [], quiz_score=100, qa_history=[])
    db.save_general_session(pid, lid1, [], quiz_score=60, qa_history=[])

    with (
        patch("backend.general.reflect.get_db", return_value=db),
        patch("backend.general.researcher.run_targeted_research", new_callable=AsyncMock),
    ):
        from backend.general.reflect import run_reflect

        await run_reflect(pid)

    dashboard = db.get_general_project_dashboard(pid)
    # "基础入门" mastery = mean([0.6, 1.0]) = 0.8 >= 0.5 → 1 mastered / 1 total = 1.0
    assert dashboard["goal_progress"] == pytest.approx(1.0, abs=0.01)


@pytest.mark.asyncio
async def test_reflect_unattempted_chapters_reduce_progress(db):
    """Progress is 0.5 when only 1 of 2 chapters has been attempted."""
    pid, lid0, _lid1 = _setup_two_chapter_project(db)
    # Only chapter 0 ("基础入门") has a session.
    db.save_general_session(pid, lid0, [], quiz_score=80, qa_history=[])

    with (
        patch("backend.general.reflect.get_db", return_value=db),
        patch("backend.general.researcher.run_targeted_research", new_callable=AsyncMock),
    ):
        from backend.general.reflect import run_reflect

        await run_reflect(pid)

    dashboard = db.get_general_project_dashboard(pid)
    # "基础入门" mastery=0.8 → mastered; "进阶技巧" not attempted → 1/2 = 0.5
    assert dashboard["goal_progress"] == pytest.approx(0.5, abs=0.01)


@pytest.mark.asyncio
async def test_reflect_all_mastered(db):
    """Progress is 1.0 when both chapters are mastered (score >= 50%)."""
    pid, lid0, lid1 = _setup_two_chapter_project(db)
    db.save_general_session(pid, lid0, [], quiz_score=70, qa_history=[])
    db.save_general_session(pid, lid1, [], quiz_score=60, qa_history=[])

    with (
        patch("backend.general.reflect.get_db", return_value=db),
        patch("backend.general.researcher.run_targeted_research", new_callable=AsyncMock),
    ):
        from backend.general.reflect import run_reflect

        await run_reflect(pid)

    dashboard = db.get_general_project_dashboard(pid)
    # Both chapters mastered → 2/2 = 1.0
    assert dashboard["goal_progress"] == pytest.approx(1.0, abs=0.01)


@pytest.mark.asyncio
async def test_reflect_no_session_chapters(db):
    """Progress is 0.0 when no sessions have been completed (early return)."""
    pid, _lid0, _lid1 = _setup_two_chapter_project(db)
    # No sessions added — run_reflect returns early without writing a model.

    with (
        patch("backend.general.reflect.get_db", return_value=db),
        patch("backend.general.researcher.run_targeted_research", new_callable=AsyncMock),
    ):
        from backend.general.reflect import run_reflect

        await run_reflect(pid)

    dashboard = db.get_general_project_dashboard(pid)
    assert dashboard["goal_progress"] == 0.0


@pytest.mark.asyncio
async def test_reflect_fsrs_due_preserved(db):
    """run_reflect preserves existing fsrs_due items instead of overwriting with []."""
    pid, lid0, _ = _setup_project(db)
    db.save_general_session(pid, lid0, [], quiz_score=80, qa_history=[])

    # Pre-populate student model with an fsrs_due item.
    existing_fsrs_item = {
        "lesson_id": 99,
        "q": "What is a chord?",
        "correct": "A",
        "fsrs_state": {},
    }
    model = GeneralStudentModel(
        project_id=pid,
        goal_outcome="婚礼演奏",
        goal_progress=0.0,
        dimensions={
            "基础入门": DimensionState(mastery=0.8, sessions=1, last_reviewed="2026-01-01")
        },
        fsrs_due=[existing_fsrs_item],
        updated="2026-01-01",
    )
    db.save_general_student_model(pid, model)

    with (
        patch("backend.general.reflect.get_db", return_value=db),
        patch("backend.general.researcher.run_targeted_research", new_callable=AsyncMock),
    ):
        from backend.general.reflect import run_reflect

        await run_reflect(pid)

    updated = db.get_general_student_model_full(pid)
    assert updated is not None
    assert len(updated.fsrs_due) == 1
    assert updated.fsrs_due[0]["q"] == "What is a chord?"
