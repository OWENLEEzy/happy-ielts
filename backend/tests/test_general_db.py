import pytest

from backend.database import Database
from backend.models import (
    DimensionState,
    GeneralStudentModel,
    LearningChapter,
    LearningLesson,
    LearningMap,
    UserGoalProfile,
)


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


def _make_profile() -> UserGoalProfile:
    return UserGoalProfile(
        mode="skill",
        topic="吉他",
        motivation="兴趣",
        goal_outcome="婚礼演奏《小幸运》",
        context="婚礼现场",
        current_level="零基础",
        time_per_week=5,
        duration_weeks=8,
    )


def _make_map() -> LearningMap:
    return LearningMap(
        topic="吉他",
        total_weeks=8,
        chapters=[
            LearningChapter(
                title="基础入门",
                lessons=[LearningLesson(title="认识吉他"), LearningLesson(title="基本和弦")],
            )
        ],
    )


def test_update_project_profile_and_map(db):
    pid = db.create_general_project("吉他", None, tier="free")
    profile = _make_profile()
    lmap = _make_map()
    db.update_general_project_profile_and_map(pid, profile, lmap)

    project = db.get_general_project(pid)
    assert project is not None
    assert project.goal_profile is not None
    assert project.goal_profile.goal_outcome == "婚礼演奏《小幸运》"
    assert project.learning_map is not None
    assert project.learning_map.chapters[0].title == "基础入门"


def test_dashboard_returns_real_goal_progress(db):
    profile = _make_profile()
    pid = db.create_general_project("吉他", profile, tier="free")
    db.update_general_project_profile_and_map(pid, profile, _make_map())

    model = GeneralStudentModel(
        project_id=pid,
        goal_outcome="婚礼演奏",
        goal_progress=0.65,
        dimensions={
            "基础入门": DimensionState(mastery=0.65, sessions=2, last_reviewed="2026-03-23")
        },
        fsrs_due=[],
        updated="2026-03-23",
    )
    db.save_general_student_model(pid, model)

    dashboard = db.get_general_project_dashboard(pid)
    assert dashboard["goal_progress"] == pytest.approx(0.65, abs=1e-3)
    assert "基础入门" in dashboard["dimensions"]


def test_dashboard_goal_progress_zero_without_student_model(db):
    pid = db.create_general_project("吉他", _make_profile(), tier="free")
    dashboard = db.get_general_project_dashboard(pid)
    assert dashboard["goal_progress"] == 0.0
