import asyncio
import json
from contextlib import asynccontextmanager
from datetime import date

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from backend.models import WritingMode

load_dotenv()


class OnboardingMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    thread_id: str = "onboarding"


class SavePreferencesRequest(BaseModel):
    bandwidth_minutes: int = Field(ge=5, le=120, default=25)
    writing_mode: WritingMode = "professional"


class LessonActionRequest(BaseModel):
    type: str = Field(min_length=1, max_length=50)
    word: str | None = Field(default=None, max_length=100)
    context: str | None = Field(default=None, max_length=2000)
    sentence: str | None = Field(default=None, max_length=2000)
    text: str | None = Field(default=None, max_length=10000)
    answer: str | None = Field(default=None, max_length=200)
    response_seconds: float | None = None


class UpdateProfileRequest(BaseModel):
    interests_update: str = Field(min_length=1, max_length=500)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async with AsyncSqliteSaver.from_conn_string("./checkpoints.sqlite3") as cp:
        await cp.setup()
        app.state.checkpointer = cp

        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            _cron_prepare_next,
            CronTrigger(hour=2, minute=0),
            id="daily-planner",
            replace_existing=True,
        )
        scheduler.start()
        try:
            yield
        finally:
            scheduler.shutdown(wait=False)


async def _cron_prepare_next() -> None:
    """Cron job: check if tomorrow's lesson is ready; if not, run Planner (cold path)."""
    import logging
    from datetime import timedelta

    from backend.database import get_db
    from backend.orchestrator import _start_planner_thread

    _logger = logging.getLogger(__name__)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    db = get_db()
    if db.get_article_for_date(tomorrow) is not None:
        _logger.info("Cron: tomorrow's lesson already ready, skipping")
        return
    _logger.info("Cron: triggering Planner for %s", tomorrow)
    _start_planner_thread(reflect_handoff=None)


app = FastAPI(title="DynamicLingo API", lifespan=lifespan)

# Shared planner state from orchestrator so both /run and orchestrator paths use same dict.
from backend.orchestrator import _planner_lock  # noqa: E402
from backend.orchestrator import planner_state as _planner_state  # noqa: E402

# Hold strong references to fire-and-forget asyncio tasks to prevent GC before completion.
_background_tasks: set[asyncio.Task] = set()


@app.get("/health")
async def health():
    return {"status": "ok"}


# ─── Planner ──────────────────────────────────────────────────────────────────


@app.post("/api/planner/run")
async def run_planner():
    import logging
    import threading

    from backend.database import get_db

    today = date.today().isoformat()
    db = get_db()
    if db.get_today_article() is not None:
        _planner_state[today] = {"status": "done", "error": None}
        return {"status": "already_ready", "date": today}

    import time as _time

    with _planner_lock:
        prev_status = _planner_state.get(today, {}).get("status")
        if prev_status == "running":
            return {"status": "running", "date": today}
        thread_suffix = f"-{int(_time.time())}"
        _planner_state[today] = {"status": "running", "error": None}

    async def _run_planner() -> None:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        from backend.planner.agent import create_deep_agent_planner, get_planner_config

        async with AsyncSqliteSaver.from_conn_string("./checkpoints.sqlite3") as cp:
            await cp.setup()
            planner = create_deep_agent_planner(cp)
            config = get_planner_config(thread_suffix)
            await planner.ainvoke(  # type: ignore[attr-defined]
                {"messages": [{"role": "user", "content": "为今天准备一节课"}]},
                config,
            )

    def run_in_thread() -> None:
        try:
            asyncio.run(_run_planner())
            _planner_state[today] = {"status": "done", "error": None}
        except Exception as exc:
            logging.exception("Planner failed for %s", today)
            _planner_state[today] = {"status": "error", "error": str(exc)}

    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()
    return {"status": "started", "date": today}


@app.get("/api/planner/status")
async def planner_status():
    from datetime import timedelta

    from backend.database import get_db

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    db = get_db()
    article = db.get_today_article()
    task = db.get_today_writing_task()
    ready = article is not None and task is not None
    tomorrow_ready = db.get_article_for_date(tomorrow) is not None
    state = _planner_state.get(today, {"status": "idle", "error": None})
    return {
        "ready": ready,
        "ready_for_tomorrow": tomorrow_ready,
        "status": state["status"],
        "error": state["error"],
    }


@app.post("/api/planner/prepare-next")
async def prepare_next_lesson():
    """Prepare tomorrow's lesson. Called by Orchestrator (hot) or cron (cold)."""
    from datetime import timedelta

    from backend.database import get_db
    from backend.orchestrator import _start_planner_thread

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    db = get_db()

    if db.get_article_for_date(tomorrow) is not None:
        return {"status": "already_ready", "date": tomorrow}

    _start_planner_thread(reflect_handoff=None)
    return {"status": "started", "date": tomorrow}


# ─── Onboarding ───────────────────────────────────────────────────────────────


@app.post("/api/onboarding/message")
async def onboarding_message(body: OnboardingMessageRequest):
    from backend.onboarding.agent import ONBOARDING_CONFIG, create_onboarding_agent

    agent = create_onboarding_agent(app.state.checkpointer)

    async def generate():
        async for chunk in agent.astream(  # type: ignore[attr-defined]
            {"messages": [{"role": "user", "content": body.message}]},
            config=ONBOARDING_CONFIG,
            stream_mode="messages",
        ):
            token, _ = chunk
            if hasattr(token, "content") and token.content:
                content = token.content if isinstance(token.content, str) else str(token.content)
                yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/onboarding/status")
async def onboarding_status():
    from backend.database import get_db

    db = get_db()
    profile = db.get_user_profile()
    return {"ready": profile is not None}


@app.post("/api/onboarding/preferences")
async def save_preferences(body: SavePreferencesRequest):
    from backend.database import get_db

    db = get_db()
    profile = db.get_user_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    updated = profile.model_copy(
        update={
            "bandwidth_minutes": body.bandwidth_minutes,
            "writing_mode": body.writing_mode,
        }
    )
    db.upsert_user_profile(updated)
    return {"status": "ok"}


# ─── Lesson ───────────────────────────────────────────────────────────────────


@app.get("/api/lesson/today")
async def get_today_lesson():
    from backend.database import get_db

    db = get_db()
    article = db.get_today_article()
    task = db.get_today_writing_task()
    if article is None or task is None:
        raise HTTPException(status_code=404, detail="Today's lesson not ready. Run planner first.")
    return {"article": article.model_dump(), "task": task.model_dump()}


@app.post("/api/lesson/action")
async def lesson_action(action: LessonActionRequest):
    from langgraph.types import Command

    from backend.tutor.graph import get_tutor_graph

    graph = get_tutor_graph(app.state.checkpointer)
    config: RunnableConfig = {"configurable": {"thread_id": date.today().isoformat()}}

    async def generate():
        async for chunk in graph.astream(
            Command(resume=action.model_dump(exclude_none=False)),
            config=config,
            stream_mode="custom",
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

        # After stream: check if graph is done and trigger orchestrator.
        # Hold a strong reference to prevent the task from being GC'd mid-execution.
        try:
            state_snapshot = await graph.aget_state(config)
            if not state_snapshot.next:  # No pending nodes = graph reached END
                task = asyncio.create_task(_trigger_orchestrator(config, graph))
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)
        except Exception:
            pass  # Never block the SSE response for orchestrator errors

    return StreamingResponse(generate(), media_type="text/event-stream")


async def _trigger_orchestrator(config, graph) -> None:
    """Build TutorHandoff from DB and fire Orchestrator."""
    import logging

    from backend.database import get_db
    from backend.models import TutorHandoff
    from backend.orchestrator import orchestrate_after_tutor

    _logger = logging.getLogger(__name__)
    try:
        db = get_db()
        article = db.get_today_article()
        state = await graph.aget_state(config)
        values = state.values

        feedback = values.get("writing_feedback")
        handoff = TutorHandoff(
            date=date.today().isoformat(),
            phases_completed=_infer_phases(values),
            writing_score=feedback.overall_score if feedback else 0,
            observations=[],  # Already written to memory in save_results
            vocab_reviewed=len(values.get("review_queue", [])),
            vocab_correct=0,  # Not tracked in current state; future enhancement
            article_topic=article.topic_tags[0] if article and article.topic_tags else "",
            article_logic=article.article_logic if article else "",
        )
        await orchestrate_after_tutor(handoff, db)
    except Exception:
        _logger.exception("Orchestrator trigger failed (non-fatal)")


def _infer_phases(state_values: dict) -> list[str]:
    """Infer which phases completed based on present state values."""
    phases = []
    if state_values.get("review_queue"):
        phases.append("review")
    if state_values.get("today_article") is not None:
        phases.append("reading")
    if (
        state_values.get("user_writing") is not None
        or state_values.get("writing_feedback") is not None
    ):
        phases.append("writing")
    if state_values.get("writing_feedback") is not None:
        phases.append("feedback")
    return phases


@app.post("/api/lesson/start")
async def start_lesson():
    """Initialize or resume today's LangGraph session."""
    from backend.tutor.graph import get_tutor_graph

    graph = get_tutor_graph(app.state.checkpointer)
    config: RunnableConfig = {"configurable": {"thread_id": date.today().isoformat()}}

    checkpoint_tuple = await app.state.checkpointer.aget_tuple(config)
    if checkpoint_tuple is not None and checkpoint_tuple.metadata.get("next"):
        next_nodes: list[str] = list(checkpoint_tuple.metadata.get("next", []))
        # Attach interrupt data so the frontend can restore fill_blank state
        interrupt_value: dict | None = None
        state = await graph.aget_state(config)
        for task in state.tasks:
            if task.interrupts:
                interrupt_value = task.interrupts[0].value
                break
        return JSONResponse(
            {"status": "already_started", "next": next_nodes, "interrupt": interrupt_value},
            status_code=409,
        )

    async def generate():
        async for chunk in graph.astream(
            {
                "user_profile": None,
                "today_article": None,
                "today_task": None,
                "review_queue": [],
                "review_index": 0,
                "user_writing": None,
                "writing_feedback": None,
                "messages": [],
            },
            config=config,
            stream_mode="custom",
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ─── Profile ──────────────────────────────────────────────────────────────────


@app.get("/api/profile")
async def get_profile():
    from backend.database import get_db

    db = get_db()
    profile = db.get_user_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile.model_dump()


@app.patch("/api/profile")
async def update_profile(body: UpdateProfileRequest):
    from backend.database import get_db

    db = get_db()
    profile = db.get_user_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    new_interests_str = body.interests_update
    if new_interests_str:
        from pydantic import BaseModel

        from backend.llm import get_llm

        class _InterestList(BaseModel):
            interests: list[str]

        llm = get_llm()
        result: _InterestList = llm.with_structured_output(_InterestList).invoke(  # type: ignore[assignment]
            f"""
Current interests: {profile.interests}
User update: "{new_interests_str}"
Return 3-5 updated interest keywords.
"""
        )
        profile = profile.model_copy(update={"interests": result.interests})
    db.upsert_user_profile(profile)
    return profile.model_dump()


# ─── Vocab ────────────────────────────────────────────────────────────────────


@app.get("/api/vocab")
async def get_vocab():
    from backend.database import get_db

    db = get_db()
    items = db.get_all_vocab_items()
    return [item.model_dump() for item in items]
