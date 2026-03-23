from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models import (
    GeneralProject,
    LearningChapter,
    LearningLesson,
    LearningMap,
    UserGoalProfile,
)


@pytest.mark.asyncio
async def test_extractor_upserts_all_lessons():
    from backend.general.extractor import run_extractor

    mock_project = MagicMock(spec=GeneralProject)
    mock_project.id = 1
    mock_project.notebook_id = "nb-123"
    mock_project.goal_profile = UserGoalProfile(
        mode="skill",
        topic="吉他",
        motivation="x",
        goal_outcome="婚礼演奏",
        context="婚礼",
        current_level="零基础",
        time_per_week=5,
        duration_weeks=8,
    )
    mock_project.learning_map = LearningMap(
        topic="吉他",
        total_weeks=4,
        chapters=[
            LearningChapter(
                title="基础乐理",
                lessons=[
                    LearningLesson(title="认识音符", objectives=[]),
                    LearningLesson(title="节拍感", objectives=[]),
                ],
            )
        ],
    )

    with (
        patch("backend.general.extractor.get_db") as mock_db_fn,
        patch("backend.general.extractor.get_nlm_client") as mock_nlm_fn,
    ):
        db = MagicMock()
        db.get_general_project.return_value = mock_project
        mock_db_fn.return_value = db

        nlm = AsyncMock()
        nlm.ask.return_value = "详细内容..."
        nlm.generate_study_guide.return_value = "# Study Guide"
        nlm.generate_quiz.return_value = [{"q": "问题1", "a": "答案1"}]
        nlm.generate_flashcards.return_value = [{"front": "音符", "back": "note"}]
        mock_nlm_fn.return_value = nlm

        await run_extractor(1)

    assert db.upsert_general_lesson.call_count == 2
    db.update_general_project_status.assert_called_with(1, "active")
