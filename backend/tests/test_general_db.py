import pytest

from backend.database import Database
from backend.models import UserGoalProfile


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "test.sqlite3"))


def test_create_and_get_project(db):
    profile = UserGoalProfile(
        mode="skill",
        topic="吉他",
        motivation="x",
        goal_outcome="婚礼演奏",
        context="婚礼",
        current_level="零基础",
        time_per_week=5,
        duration_weeks=8,
    )
    pid = db.create_general_project("吉他", profile, tier="free")
    assert pid > 0
    project = db.get_general_project(pid)
    assert project is not None
    assert project.user_topic == "吉他"
    assert project.status == "onboarding"
    assert project.tier == "free"


def test_update_project_status(db):
    pid = db.create_general_project("投资", None, tier="paid")
    db.update_general_project_status(pid, "researching")
    p = db.get_general_project(pid)
    assert p.status == "researching"


def test_upsert_lesson_is_idempotent(db):
    pid = db.create_general_project("吉他", None, tier="free")
    db.upsert_general_lesson(
        pid,
        chapter=0,
        lesson=0,
        title="认识音符",
        study_guide="guide text",
        quiz_json=[],
        flashcards=[],
    )
    db.upsert_general_lesson(
        pid,
        chapter=0,
        lesson=0,
        title="认识音符",
        study_guide="updated guide",
        quiz_json=[],
        flashcards=[],
    )
    lessons = db.get_project_lessons(pid)
    assert len(lessons) == 1
    assert lessons[0].study_guide == "updated guide"
