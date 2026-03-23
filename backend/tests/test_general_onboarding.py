from unittest.mock import MagicMock, patch

from backend.general.onboarding import (
    SKILL_ONBOARDING_PROMPT,
    generate_draft_learning_map,
    make_save_goal_profile_tool,
)
from backend.models import LearningMap, UserGoalProfile


def test_skill_prompt_contains_goal_outcome():
    assert "goal_outcome" in SKILL_ONBOARDING_PROMPT or "应用场景" in SKILL_ONBOARDING_PROMPT


def test_save_goal_profile_tool_persists_to_db():
    """save_goal_profile must write to DB — not just return a string."""
    with patch("backend.general.onboarding.get_db") as mock_db_fn:
        db = MagicMock()
        mock_db_fn.return_value = db
        save_tool = make_save_goal_profile_tool(project_id=42)
        result = save_tool.invoke(
            {
                "topic": "吉他",
                "motivation": "x",
                "goal_outcome": "婚礼演奏",
                "context": "婚礼",
                "current_level": "零基础",
                "time_per_week": 5,
                "duration_weeks": 8,
                "constraints": [],
            }
        )
        db.update_general_project_goal_profile.assert_called_once()
        assert "42" in result


def test_generate_draft_map_structure():
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
    with patch("backend.general.onboarding.get_llm") as mock_llm:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = LearningMap(
            topic="吉他",
            total_weeks=8,
            chapters=[],
        )
        mock_llm.return_value.with_structured_output.return_value = mock_chain
        result = generate_draft_learning_map(profile)
    assert isinstance(result, LearningMap)
    assert result.topic == "吉他"
