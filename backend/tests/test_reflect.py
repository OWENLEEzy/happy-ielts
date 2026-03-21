from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models import ReflectHandoff, TutorHandoff
from backend.reflect.agent import run_reflect


@pytest.fixture
def sample_handoff():
    return TutorHandoff(
        date="2026-03-21",
        phases_completed=["review", "reading", "writing", "feedback"],
        writing_score=7,
        observations=["thesis statement weak, 3rd time"],
        vocab_reviewed=5,
        vocab_correct=4,
        article_topic="climate",
        article_logic="argumentation",
    )


@pytest.fixture
def sample_stats():
    return {
        "writing_scores": [{"date": "2026-03-21", "score": 7}],
        "chinglish_counts": [{"issue": "logic_connector", "count": 3}],
        "vocab_mastered": 45,
        "topic_distribution": [{"topic": "climate", "count": 5}],
    }


@pytest.mark.anyio
async def test_run_reflect_returns_reflect_handoff(sample_handoff, sample_stats):
    mock_result = ReflectHandoff(
        date="2026-03-21",
        level_suggestion=5,
        top_weaknesses=["weak thesis", "run-on sentence"],
        improving_areas=["word choice"],
        topic_recommendation="climate + policy crossover",
        task_recommendation="focus on argumentation structure",
        teaching_insight="Weak thesis appears specifically in argumentation articles",
    )

    with patch("backend.reflect.agent.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_result)
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_llm.return_value = mock_llm

        result = await run_reflect(
            handoff=sample_handoff,
            weekly_stats=sample_stats,
            observations=[{"date": "2026-03-21", "observation": "thesis weak"}],
            insights_history=[],
        )

    assert isinstance(result, ReflectHandoff)
    assert result.date == "2026-03-21"
    assert len(result.top_weaknesses) > 0
    assert result.teaching_insight != ""
