from backend.models import (
    DimensionState,
    GeneralStudentModel,
    LearningChapter,
    LearningLesson,
    LearningMap,
    UserGoalProfile,
)


def test_user_goal_profile_skill_mode():
    p = UserGoalProfile(
        mode="skill",
        topic="吉他",
        motivation="想在婚礼上弹一首歌",
        goal_outcome="能完整演奏一首曲子",
        context="婚礼现场",
        current_level="完全零基础",
        time_per_week=5,
        duration_weeks=8,
        constraints=["没有吉他，需要先买"],
    )
    assert p.mode == "skill"
    assert p.time_per_week == 5


def test_learning_map_structure():
    m = LearningMap(
        topic="吉他",
        total_weeks=4,
        chapters=[
            LearningChapter(
                title="基础乐理",
                lessons=[LearningLesson(title="认识音符", objectives=["识别五线谱"])],
            )
        ],
    )
    assert len(m.chapters) == 1
    assert m.chapters[0].lessons[0].title == "认识音符"


def test_student_model_goal_progress():
    m = GeneralStudentModel(
        project_id=1,
        goal_outcome="婚礼演奏",
        goal_progress=0.35,
        dimensions={
            "基础乐理": DimensionState(
                mastery=0.8, sessions=2, last_reviewed="2026-03-23", trend="stable"
            ),
            "和弦转换": DimensionState(
                mastery=0.2, sessions=1, last_reviewed="2026-03-23", trend="worsening"
            ),
        },
        fsrs_due=[],
        updated="2026-03-23",
    )
    assert m.goal_progress == 0.35
    assert m.dimensions["和弦转换"].mastery == 0.2
