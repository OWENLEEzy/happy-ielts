"""Tests for tutor/graph.py, llm.py, planner/agent.py, onboarding/agent.py,
and the _get_llm cache in tutor/tools.py.

load_dotenv() is called before importing any module that reads env vars at
import time (e.g. planner/agent.py which creates TavilySearch at module level).
"""

from datetime import date
from unittest.mock import MagicMock, patch

from dotenv import load_dotenv

load_dotenv()  # must run before any module that needs DASHSCOPE_API_KEY / TAVILY_API_KEY

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

import backend.planner.agent as _agent_mod  # noqa: E402
import backend.tutor.graph as _graph_mod  # noqa: E402

# ---------------------------------------------------------------------------
# tutor/graph.py
# ---------------------------------------------------------------------------


def test_build_tutor_graph_returns_compiled_graph():
    """build_tutor_graph returns a compiled graph that has an astream method."""
    _graph_mod._graph = None
    cp = InMemorySaver()
    graph = _graph_mod.build_tutor_graph(cp)
    assert hasattr(graph, "astream")
    _graph_mod._graph = None


def test_get_tutor_graph_is_singleton():
    """get_tutor_graph returns the same compiled graph on subsequent calls."""
    _graph_mod._graph = None
    cp = InMemorySaver()
    g1 = _graph_mod.get_tutor_graph(cp)
    g2 = _graph_mod.get_tutor_graph(cp)
    assert g1 is g2
    _graph_mod._graph = None


def test_get_tutor_graph_builds_only_once():
    """build_tutor_graph is called exactly once even with multiple get_tutor_graph calls."""
    _graph_mod._graph = None
    cp = InMemorySaver()
    with patch.object(
        _graph_mod, "build_tutor_graph", wraps=_graph_mod.build_tutor_graph
    ) as mock_build:
        _graph_mod.get_tutor_graph(cp)
        _graph_mod.get_tutor_graph(cp)
    assert mock_build.call_count == 1
    _graph_mod._graph = None


# ---------------------------------------------------------------------------
# llm.py
# ---------------------------------------------------------------------------


def test_get_llm_instantiates_chat_openai_with_dashscope_url():
    """get_llm creates a ChatOpenAI pointed at the DashScope international endpoint."""
    mock_instance = MagicMock()
    with (
        patch.dict("os.environ", {"DASHSCOPE_API_KEY": "fake-key"}),
        patch("backend.llm.ChatOpenAI", return_value=mock_instance) as mock_cls,
    ):
        from backend.llm import get_llm

        result = get_llm()

    assert result is mock_instance
    call_kwargs = mock_cls.call_args.kwargs
    assert "dashscope" in call_kwargs.get("base_url", "")


# ---------------------------------------------------------------------------
# planner/agent.py
# ---------------------------------------------------------------------------


def test_get_planner_config_returns_today_thread_id():
    """get_planner_config returns a config whose thread_id encodes today's date."""
    config = _agent_mod.get_planner_config()
    today = date.today().isoformat()
    assert config["configurable"]["thread_id"] == f"planner-{today}"


def test_create_deep_agent_planner_delegates_to_create_deep_agent():
    """create_deep_agent_planner returns the object returned by create_deep_agent."""
    mock_agent = MagicMock()
    with (
        patch("backend.planner.agent.create_deep_agent", return_value=mock_agent),
        patch("backend.planner.agent.get_llm", return_value=MagicMock()),
    ):
        result = _agent_mod.create_deep_agent_planner(MagicMock())
    assert result is mock_agent


# ---------------------------------------------------------------------------
# onboarding/agent.py
# ---------------------------------------------------------------------------


def test_create_onboarding_agent_delegates_to_create_deep_agent():
    """create_onboarding_agent returns the object returned by create_deep_agent."""
    import backend.onboarding.agent as _onboarding_mod

    mock_agent = MagicMock()
    with (
        patch("backend.onboarding.agent.create_deep_agent", return_value=mock_agent),
        patch("backend.onboarding.agent.get_llm", return_value=MagicMock()),
    ):
        result = _onboarding_mod.create_onboarding_agent(MagicMock())
    assert result is mock_agent


def test_save_partial_profile_tool_persists_profile_and_returns_confirmation():
    """save_partial_profile writes a UserProfile to the database."""
    import backend.onboarding.agent as _onboarding_mod

    mock_db = MagicMock()
    with patch("backend.onboarding.agent._db", mock_db):
        result = _onboarding_mod.save_partial_profile.invoke(
            {"goal": "Read TypeScript docs", "interests": ["AI", "TypeScript"], "level": 6}
        )
    assert "level-6" in result
    mock_db.upsert_user_profile.assert_called_once()


# ---------------------------------------------------------------------------
# tutor/tools.py — _get_llm lru_cache (line 15)
# ---------------------------------------------------------------------------


def test_tutor_tools_get_llm_caches_result():
    """_get_llm() calls the underlying get_llm exactly once due to lru_cache."""
    from backend.tutor.tools import _get_llm

    _get_llm.cache_clear()
    mock_llm = MagicMock()
    with patch("backend.tutor.tools.get_llm", return_value=mock_llm) as mock_get_llm:
        r1 = _get_llm()
        r2 = _get_llm()  # cache hit — get_llm not called again
    assert r1 is mock_llm
    assert r1 is r2
    assert mock_get_llm.call_count == 1
    _get_llm.cache_clear()
