from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models import LearningChapter, LearningLesson, LearningMap, UserGoalProfile


@pytest.fixture
def profile():
    return UserGoalProfile(
        mode="skill",
        topic="吉他",
        motivation="x",
        goal_outcome="婚礼演奏",
        context="婚礼",
        current_level="零基础",
        time_per_week=5,
        duration_weeks=8,
    )


@pytest.fixture
def draft_map():
    return LearningMap(
        topic="吉他",
        total_weeks=8,
        chapters=[
            LearningChapter(
                title="基础乐理", lessons=[LearningLesson(title="认识音符", objectives=[])]
            )
        ],
    )


@pytest.mark.asyncio
async def test_researcher_terminates_on_complete(profile, draft_map):
    from backend.general.researcher import run_researcher

    with (
        patch("backend.general.researcher.get_db") as mock_db,
        patch("backend.general.researcher.get_nlm_client") as mock_nlm,
    ):
        db = MagicMock()
        db.get_general_project.return_value = MagicMock(
            notebook_id=None, tier="free", budget_used=0
        )
        mock_db.return_value = db

        nlm = AsyncMock()
        nlm.create_notebook.return_value = "nb-test-123"
        nlm.add_research.return_value = 10
        nlm.ask.return_value = "COMPLETE"
        nlm.generate_mind_map.return_value = {"nodes": []}
        mock_nlm.return_value = nlm

        with patch("backend.general.researcher._adapt_mind_map_to_profile", return_value=draft_map):
            await run_researcher(1, profile, draft_map)

        db.update_general_project_notebook.assert_called_once_with(1, "nb-test-123")
        db.update_general_project_status.assert_called_with(1, "extracting")
