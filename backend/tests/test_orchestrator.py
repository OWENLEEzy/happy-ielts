from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models import ReflectHandoff, TutorHandoff, UserProfile


def make_handoff(phases=None, score=7):
    return TutorHandoff(
        date="2026-03-21",
        phases_completed=phases or ["review", "reading", "writing", "feedback"],
        writing_score=score,
        observations=["thesis weak"],
        vocab_reviewed=5,
        vocab_correct=4,
        article_topic="climate",
        article_logic="argumentation",
    )


def make_reflect_handoff(level=5, insight="test insight"):
    return ReflectHandoff(
        date="2026-03-21",
        level_suggestion=level,
        top_weaknesses=["weak thesis"],
        improving_areas=["word choice"],
        topic_recommendation="climate policy",
        task_recommendation="argumentation structure",
        teaching_insight=insight,
    )


@pytest.mark.anyio
async def test_orchestrate_skips_on_incomplete_session():
    """Less than 3 phases = skip Reflect entirely."""
    mock_db = MagicMock()
    with patch("backend.orchestrator.run_reflect", new_callable=AsyncMock) as mock_reflect:
        from backend.orchestrator import orchestrate_after_tutor

        await orchestrate_after_tutor(make_handoff(phases=["review"]), mock_db)
        mock_reflect.assert_not_called()


@pytest.mark.anyio
async def test_orchestrate_persists_insight():
    mock_db = MagicMock()
    mock_db.query_weekly_stats.return_value = {
        "writing_scores": [],
        "chinglish_counts": [],
        "vocab_mastered": 0,
        "topic_distribution": [],
    }
    mock_db.get_user_profile.return_value = UserProfile(
        goal="test",
        interests=[],
        level=5,
        bandwidth_minutes=25,
        writing_mode="professional",
    )
    reflect_result = make_reflect_handoff(level=5, insight="real insight")

    with (
        patch("backend.orchestrator.run_reflect", return_value=reflect_result),
        patch("backend.orchestrator.memory") as mock_mem,
        patch("backend.orchestrator._start_planner_thread") as mock_planner,
    ):
        mock_mem.read_observations.return_value = []
        mock_mem.read_insights.return_value = []

        from backend.orchestrator import orchestrate_after_tutor

        await orchestrate_after_tutor(make_handoff(), mock_db)

        mock_mem.append_insight.assert_called_once()
        call_args = mock_mem.append_insight.call_args[0][0]
        assert call_args["insight"] == "real insight"
        mock_planner.assert_called_once()


@pytest.mark.anyio
async def test_orchestrate_updates_level_when_suggestion_differs():
    mock_db = MagicMock()
    mock_db.query_weekly_stats.return_value = {
        "writing_scores": [],
        "chinglish_counts": [],
        "vocab_mastered": 0,
        "topic_distribution": [],
    }
    current_profile = UserProfile(
        goal="test",
        interests=[],
        level=5,
        bandwidth_minutes=25,
        writing_mode="professional",
    )
    mock_db.get_user_profile.return_value = current_profile
    reflect_result = make_reflect_handoff(level=6)  # suggest level up

    with (
        patch("backend.orchestrator.run_reflect", return_value=reflect_result),
        patch("backend.orchestrator.memory") as mock_mem,
        patch("backend.orchestrator._start_planner_thread"),
    ):
        mock_mem.read_observations.return_value = []
        mock_mem.read_insights.return_value = []

        from backend.orchestrator import orchestrate_after_tutor

        await orchestrate_after_tutor(make_handoff(), mock_db)

        mock_db.upsert_user_profile.assert_called_once()
        updated = mock_db.upsert_user_profile.call_args[0][0]
        assert updated.level == 6
