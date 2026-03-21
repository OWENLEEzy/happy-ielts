import asyncio
import logging
import threading
from datetime import date, timedelta

from backend import memory
from backend.models import ReflectHandoff, TutorHandoff
from backend.reflect.agent import run_reflect

logger = logging.getLogger(__name__)

# Shared in-memory planner run state per date: date_str -> {"status": str, "error": str | None}
# Imported by main.py so both paths (manual /run and orchestrator) share the same dict.
planner_state: dict[str, dict] = {}


async def orchestrate_after_tutor(handoff: TutorHandoff, db) -> None:
    """
    Called after Tutor completes. Decides whether to trigger Reflect → Planner chain.
    Runs in the current event loop — caller is responsible for not blocking the main loop.
    """
    if len(handoff.phases_completed) < 3:
        logger.info("Orchestrator: skipping (only %d phases)", len(handoff.phases_completed))
        return

    weekly_stats = db.query_weekly_stats()
    observations = memory.read_observations(days=7)
    insights_history = memory.read_insights(days=14)

    # Fetch profile early to pass current level as hint to Reflect
    profile = db.get_user_profile()
    current_level = profile.level if profile else 5

    reflect_handoff = await run_reflect(
        handoff, weekly_stats, observations, insights_history, current_level=current_level
    )

    # Quality gate: if insight is empty, retry with extended observations
    if not reflect_handoff.teaching_insight.strip():
        logger.warning("Orchestrator: Reflect returned empty insight, retrying with 14-day window")
        observations_ext = memory.read_observations(days=14)
        reflect_handoff = await run_reflect(
            handoff, weekly_stats, observations_ext, insights_history, current_level=current_level
        )
        if not reflect_handoff.teaching_insight.strip():
            logger.warning("Orchestrator: Reflect still empty after retry — storing as-is")

    # Persist LLM-generated insight (only non-structured, SQL can't derive this)
    memory.append_insight(
        {
            "date": reflect_handoff.date,
            "insight": reflect_handoff.teaching_insight,
            "action": reflect_handoff.task_recommendation,
        }
    )

    # Level auto-adjustment (only if Reflect recommends a change)
    if profile and reflect_handoff.level_suggestion != profile.level:
        updated = profile.model_copy(update={"level": reflect_handoff.level_suggestion})
        db.upsert_user_profile(updated)
        logger.info(
            "Orchestrator: level %d → %d",
            profile.level,
            reflect_handoff.level_suggestion,
        )

    # Fire-and-forget Planner for tomorrow
    _start_planner_thread(reflect_handoff)


def _start_planner_thread(reflect_handoff: ReflectHandoff | None = None) -> None:
    """Start Planner in a background thread (same pattern as /api/planner/run)."""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    planner_state[tomorrow] = {"status": "running", "error": None}
    thread = threading.Thread(
        target=_run_planner_sync,
        args=(tomorrow, reflect_handoff),
        daemon=True,
        name=f"planner-{tomorrow}",
    )
    thread.start()
    logger.info("Orchestrator: started Planner thread for %s", tomorrow)


def _run_planner_sync(target_date: str, reflect_handoff: ReflectHandoff | None) -> None:
    """Blocking planner run — must be called in a background thread."""
    try:
        asyncio.run(_run_planner_async(target_date, reflect_handoff))
        planner_state[target_date] = {"status": "done", "error": None}
        logger.info("Orchestrator: Planner completed for %s", target_date)
    except Exception as exc:
        planner_state[target_date] = {"status": "error", "error": str(exc)}
        logger.exception("Orchestrator: Planner failed for %s", target_date)


async def _run_planner_async(target_date: str, reflect_handoff: ReflectHandoff | None) -> None:
    import time as _time

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    from backend.planner.agent import create_deep_agent_planner, get_planner_config

    async with AsyncSqliteSaver.from_conn_string("./checkpoints.sqlite3") as cp:
        await cp.setup()
        planner = create_deep_agent_planner(cp, reflect_handoff=reflect_handoff)
        config = get_planner_config(f"-{int(_time.time())}")
        target_msg = f"为 {target_date} 准备一节课"
        await planner.ainvoke(  # type: ignore[attr-defined]
            {"messages": [{"role": "user", "content": target_msg}]},
            config,
        )
