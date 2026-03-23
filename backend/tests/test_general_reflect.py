"""Tests for backend.general.reflect — trend detection and student model update."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.database import Database
from backend.models import (
    LearningChapter,
    LearningLesson,
    LearningMap,
    UserGoalProfile,
)


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "test.sqlite3"))


def _setup_project(db: Database) -> tuple[int, int, int]:
    """Create project with map and two lessons. Returns (project_id, lesson_id_0, lesson_id_1)."""
    profile = UserGoalProfile(
        mode="skill",
        topic="吉他",
        motivation="兴趣",
        goal_outcome="婚礼演奏",
        context="婚礼",
        current_level="零基础",
        time_per_week=5,
        duration_weeks=8,
    )
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
    """goal_progress is the mean mastery across all chapters."""
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
    # mastery = mean([1.0, 0.6]) = 0.8
    assert dashboard["goal_progress"] == pytest.approx(0.8, abs=0.01)
