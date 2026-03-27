import asyncio
import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, timedelta

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.models import (
    GeneralOnboardingStartResponse,
    GeneralProject,
    LearningMap,
    PlannerStatusResponse,
    ProjectDashboardResponse,
    ReadyStatusResponse,
    UserGoalProfile,
    WritingMode,
)

load_dotenv()

_logger = logging.getLogger(__name__)


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
async def _make_checkpointer(max_size: int = 5):
    """Yield a LangGraph checkpointer. Uses AsyncPostgresSaver when DATABASE_URL is set,
    falls back to AsyncSqliteSaver otherwise (state lost on process restart)."""
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg_pool import AsyncConnectionPool

        async with AsyncConnectionPool(conninfo=database_url, max_size=max_size, open=True) as pool:
            saver = AsyncPostgresSaver(pool)
            await saver.setup()
            yield saver
    else:
        _logger.warning(
            "DATABASE_URL not set — using SQLite checkpointer (state lost on restart). "
            "Set DATABASE_URL on Render to enable persistent PostgreSQL checkpoints."
        )
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite3") as saver:
            yield saver


@asynccontextmanager
async def lifespan(app: FastAPI):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    async with _make_checkpointer(max_size=5) as cp:
        app.state.checkpointer = cp

        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            _cron_prepare_next,
            CronTrigger(hour=2, minute=0, timezone="Asia/Shanghai"),
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
    from backend.database import get_db
    from backend.orchestrator import _start_planner_thread

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    db = get_db()
    if db.get_article_for_date(tomorrow) is not None:
        _logger.info("Cron: tomorrow's lesson already ready, skipping")
        return
    _logger.info("Cron: triggering Planner for %s", tomorrow)
    _start_planner_thread(reflect_handoff=None)


app = FastAPI(title="DynamicLingo API", lifespan=lifespan)


# ─── API Key Middleware ────────────────────────────────────────────────────────

_API_KEYS: set[str] = set()
_raw_keys = os.environ.get("API_KEY", "")
if _raw_keys.strip():
    _API_KEYS = {k.strip() for k in _raw_keys.split(",") if k.strip()}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip check when no API keys are configured (local dev)
        if not _API_KEYS:
            return await call_next(request)
        # Skip /api/cron/ routes — they use their own CRON_SECRET auth
        path = request.url.path
        if not path.startswith("/api/") or path.startswith("/api/cron/"):
            return await call_next(request)
        key = request.headers.get("X-API-Key", "")
        if key not in _API_KEYS:
            return JSONResponse({"detail": "Invalid API key"}, status_code=401)
        return await call_next(request)


app.add_middleware(ApiKeyMiddleware)

# Shared planner state from orchestrator so both /run and orchestrator paths use same dict.
from backend.orchestrator import _planner_lock  # noqa: E402
from backend.orchestrator import planner_state as _planner_state  # noqa: E402

# Hold strong references to fire-and-forget asyncio tasks to prevent GC before completion.
_background_tasks: set[asyncio.Task] = set()


@app.get("/health")
async def health():
    return {"status": "ok"}


# ─── Planner ──────────────────────────────────────────────────────────────────


@app.post("/api/planner/jobs")
async def run_planner():
    from backend.database import get_db

    today = date.today().isoformat()
    db = get_db()
    if db.get_today_article() is not None:
        _planner_state[today] = {"status": "done", "error": None}
        return {"status": "already_ready", "date": today}

    with _planner_lock:
        prev_status = _planner_state.get(today, {}).get("status")
        if prev_status == "running":
            return {"status": "running", "date": today}
        thread_suffix = f"-{int(time.time())}"
        _planner_state[today] = {"status": "running", "error": None}

    async def _run_planner() -> None:
        from backend.planner.agent import get_planner, get_planner_config

        async with _make_checkpointer(max_size=2) as cp:
            planner = get_planner(cp)
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


@app.get("/api/planner/status", response_model=PlannerStatusResponse)
async def planner_status():
    from backend.database import get_db

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    db = get_db()
    article = db.get_today_article()
    task = db.get_today_writing_task()
    ready = article is not None and task is not None
    tomorrow_ready = db.get_article_for_date(tomorrow) is not None
    today_state = _planner_state.get(today, {"status": "idle", "error": None})
    tomorrow_state = _planner_state.get(tomorrow, {"status": "idle", "error": None})
    return {
        "ready": ready,
        "ready_for_tomorrow": tomorrow_ready,
        "status": today_state["status"],
        "error": today_state["error"],
        "status_tomorrow": tomorrow_state["status"],
        "error_tomorrow": tomorrow_state["error"],
    }


@app.post("/api/planner/jobs/next")
async def prepare_next_lesson():
    """Prepare tomorrow's lesson. Called by Orchestrator (hot) or cron (cold)."""
    from backend.database import get_db
    from backend.orchestrator import _start_planner_thread

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    db = get_db()

    if db.get_article_for_date(tomorrow) is not None:
        return {"status": "already_ready", "date": tomorrow}

    _start_planner_thread(reflect_handoff=None)
    return {"status": "started", "date": tomorrow}


# ─── Onboarding ───────────────────────────────────────────────────────────────


@app.post("/api/onboarding/messages")
async def onboarding_message(body: OnboardingMessageRequest):
    from backend.onboarding.agent import ONBOARDING_CONFIG, create_onboarding_agent

    agent = create_onboarding_agent(app.state.checkpointer)

    async def generate():
        try:
            async for chunk in agent.astream(  # type: ignore[attr-defined]
                {"messages": [{"role": "user", "content": body.message}]},
                config=ONBOARDING_CONFIG,
                stream_mode="messages",
            ):
                token, _ = chunk
                if hasattr(token, "content") and token.content:
                    content = (
                        token.content if isinstance(token.content, str) else str(token.content)
                    )
                    yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
        except Exception as exc:
            _logger.error("onboarding stream error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Stream interrupted'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/onboarding/status", response_model=ReadyStatusResponse)
async def onboarding_status():
    from backend.database import get_db

    db = get_db()
    profile = db.get_user_profile()
    return {"ready": profile is not None}


@app.patch("/api/onboarding/preferences")
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


@app.get("/api/lessons/today")
async def get_today_lesson():
    from backend.database import get_db

    db = get_db()
    article = db.get_today_article()
    task = db.get_today_writing_task()
    if article is None or task is None:
        raise HTTPException(status_code=404, detail="Today's lesson not ready. Run planner first.")
    return {"article": article.model_dump(), "task": task.model_dump()}


@app.post("/api/lessons/today/actions")
async def lesson_action(action: LessonActionRequest):
    from langgraph.types import Command

    from backend.tutor.graph import get_tutor_graph

    graph = get_tutor_graph(app.state.checkpointer)
    config: RunnableConfig = {"configurable": {"thread_id": date.today().isoformat()}}

    async def generate():
        try:
            async for chunk in graph.astream(
                Command(resume=action.model_dump(exclude_none=False)),
                config=config,
                stream_mode="custom",
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as exc:
            _logger.error("lesson action stream error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Stream interrupted'})}\n\n"
        yield "data: [DONE]\n\n"

        # After stream: check if graph is done and trigger orchestrator.
        # Hold a strong reference to prevent the task from being GC'd mid-execution.
        try:
            state_snapshot = await graph.aget_state(config)
            if not state_snapshot.next:  # No pending nodes = graph reached END
                task = asyncio.create_task(_trigger_orchestrator(config, state_snapshot))
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)
        except Exception:
            pass  # Never block the SSE response for orchestrator errors

    return StreamingResponse(generate(), media_type="text/event-stream")


async def _trigger_orchestrator(_config, state_snapshot) -> None:
    """Build TutorHandoff from DB and fire Orchestrator."""
    from backend.database import get_db
    from backend.models import TutorHandoff
    from backend.orchestrator import orchestrate_after_tutor

    try:
        db = get_db()
        article = db.get_today_article()
        values = state_snapshot.values

        feedback = values.get("writing_feedback")
        handoff = TutorHandoff(
            date=date.today().isoformat(),
            phases_completed=values.get("phases_completed", []),
            writing_score=feedback.overall_score if feedback else 0,
            observations=[],  # Already written to memory in save_results
            vocab_reviewed=len(values.get("review_queue", [])),
            vocab_correct=values.get("vocab_correct", 0),
            article_topic=article.topic_tags[0] if article and article.topic_tags else "",
            article_logic=article.article_logic if article else "",
        )
        await orchestrate_after_tutor(handoff, db)
    except Exception:
        _logger.exception("Orchestrator trigger failed (non-fatal)")


@app.post("/api/lessons/today/session")
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
        try:
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
                    "phases_completed": [],
                    "vocab_correct": 0,
                },
                config=config,
                stream_mode="custom",
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as exc:
            _logger.error("lesson start stream error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Stream interrupted'})}\n\n"
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


# ─── General Learning ─────────────────────────────────────────────────────────


class GeneralOnboardingStartRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    tier: str = "free"


class GeneralOnboardingMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class GeneralOnboardingConfirmRequest(BaseModel):
    goal_profile: UserGoalProfile
    learning_map: LearningMap


@app.post("/api/learn/projects", response_model=GeneralOnboardingStartResponse)
async def general_onboarding_start(req: GeneralOnboardingStartRequest):
    from backend.database import get_db

    db = get_db()
    pid = db.create_general_project(req.topic, profile=None, tier=req.tier)
    return JSONResponse({"project_id": pid}, status_code=201)


@app.post("/api/learn/projects/{project_id}/messages")
async def general_onboarding_message(project_id: int, req: GeneralOnboardingMessageRequest):
    from backend.database import get_db
    from backend.general.onboarding import get_onboarding_agent

    db = get_db()
    project = db.get_general_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    agent = get_onboarding_agent(
        app.state.checkpointer,
        project_id=project_id,
        topic=project.user_topic,
    )
    config = {"configurable": {"thread_id": f"general-onboarding-{project_id}"}}

    async def stream():
        try:
            async for event in agent.astream_events(
                {"messages": [{"role": "user", "content": req.message}]},
                config=config,
                version="v2",
            ):
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"].content
                    if chunk:
                        yield f"data: {chunk}\n\n"
        except Exception as exc:
            _logger.error("general onboarding stream error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Stream interrupted'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.patch("/api/learn/projects/{project_id}")
async def general_onboarding_confirm(
    project_id: int, req: GeneralOnboardingConfirmRequest, background_tasks: BackgroundTasks
):
    from backend.database import get_db

    db = get_db()
    project = db.get_general_project(project_id)
    if not project or project.status != "onboarding":
        raise HTTPException(status_code=409, detail="Project already confirmed")
    profile = req.goal_profile
    learning_map = req.learning_map
    db.update_general_project_status(project_id, "researching")
    db.update_general_project_profile_and_map(project_id, profile, learning_map)
    background_tasks.add_task(_run_researcher, project_id, profile, learning_map)
    return {"status": "researching", "project_id": project_id}


@app.get("/api/learn/projects/{project_id}", response_model=GeneralProject)
async def get_general_project(project_id: int):
    from backend.database import get_db

    db = get_db()
    project = db.get_general_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.get("/api/learn/projects/{project_id}/dashboard", response_model=ProjectDashboardResponse)
async def get_general_dashboard(project_id: int):
    from backend.database import get_db

    db = get_db()
    data = db.get_general_project_dashboard(project_id)
    if not data:
        raise HTTPException(status_code=404, detail="Project not found")
    return data


class GeneralLessonActionRequest(BaseModel):
    type: str = Field(min_length=1, max_length=50)
    answer: str | None = None
    answers: list[int | str] | None = None
    question: str | None = None
    explanation: str | None = None  # metacog_session: student's self-explanation


class FsrsReviewItem(BaseModel):
    lesson_id: int
    q: str
    correct: str
    fsrs_state: dict


class FsrsReviewResponse(BaseModel):
    items: list[FsrsReviewItem]
    count: int


class FsrsReviewResponseItem(BaseModel):
    q: str
    lesson_id: int
    is_correct: bool
    response_seconds: float


class FsrsReviewResponseRequest(BaseModel):
    responses: list[FsrsReviewResponseItem]


@app.get("/api/learn/projects/{project_id}/review", response_model=FsrsReviewResponse)
async def get_fsrs_review(project_id: int):
    from backend.database import get_db

    db = get_db()
    model = db.get_general_student_model_full(project_id)
    if not model or not model.fsrs_due:
        return FsrsReviewResponse(items=[], count=0)
    items = [
        FsrsReviewItem(
            lesson_id=item["lesson_id"],
            q=item["q"],
            correct=item["correct"],
            fsrs_state=item["fsrs_state"],
        )
        for item in model.fsrs_due
    ]
    return FsrsReviewResponse(items=items, count=len(items))


@app.post("/api/learn/projects/{project_id}/review/responses")
async def post_fsrs_review_responses(project_id: int, req: FsrsReviewResponseRequest):
    from backend.database import get_db
    from backend.fsrs_engine import update_card

    db = get_db()
    model = db.get_general_student_model_full(project_id)
    if not model:
        raise HTTPException(status_code=404, detail="Project student model not found")

    # Build a mutable copy of fsrs_due indexed by (lesson_id, q)
    due_list: list[dict] = [dict(item) for item in model.fsrs_due]
    index: dict[tuple[int, str], int] = {
        (item["lesson_id"], item["q"]): i for i, item in enumerate(due_list)
    }

    for resp in req.responses:
        key = (resp.lesson_id, resp.q)
        if key not in index:
            continue
        pos = index[key]
        new_state = update_card(due_list[pos]["fsrs_state"], resp.is_correct, resp.response_seconds)
        due_list[pos] = {**due_list[pos], "fsrs_state": new_state}

    updated_model = model.model_copy(update={"fsrs_due": due_list})
    db.save_general_student_model(project_id, updated_model)
    return {"updated": len(req.responses)}


@app.post("/api/learn/projects/{project_id}/lessons/{lesson_id}/reextract")
async def general_lesson_reextract(project_id: int, lesson_id: int):
    """Re-extract study guide / quiz / flashcards for a single lesson.

    Useful when a lesson has degraded (fallback) content from a failed extraction.
    Runs asynchronously in the background; returns immediately.
    """
    import asyncio as _asyncio

    from backend.general.extractor import reextract_lesson

    _asyncio.create_task(reextract_lesson(project_id, lesson_id))
    return {"status": "reextract_started", "project_id": project_id, "lesson_id": lesson_id}


@app.post("/api/learn/projects/{project_id}/lessons/{lesson_id}/sessions")
async def general_lesson_start(project_id: int, lesson_id: int):
    import json as _json

    from backend.database import get_db
    from backend.general.graph import get_general_lesson_graph

    db = get_db()
    project = db.get_general_project(project_id)
    lessons = db.get_project_lessons(project_id)
    lesson = next((ls for ls in lessons if ls.id == lesson_id), None)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    graph = get_general_lesson_graph(app.state.checkpointer)
    thread_id = f"general-{project_id}-{lesson_id}"
    config = {"configurable": {"thread_id": thread_id}}

    # Check if session already exists with pending interrupt
    # Note: LangGraph checkpoint metadata does not include "next" in all versions;
    # use graph.aget_state() instead which is always authoritative.
    checkpoint_tuple = await app.state.checkpointer.aget_tuple(config)
    if checkpoint_tuple is not None:
        state = await graph.aget_state(config)
        if state.next:
            interrupt_value: dict | None = None
            for task in state.tasks:
                if task.interrupts:
                    interrupt_value = task.interrupts[0].value
                    break
            return JSONResponse(
                {"status": "already_started", "interrupt": interrupt_value},
                status_code=409,
            )

    project_dict = project.model_dump() if project else {}

    async def stream():
        try:
            async for chunk in graph.astream(
                {
                    "project": project_dict,
                    "lesson": lesson,
                    "phase": "start",
                    "messages": [],
                    # [P1#9] Explicit defaults for all new adaptive-learning fields
                    "session_mode": "normal",
                    "metacog_question": None,
                    "metacog_feedback": "",
                    "review_questions_cache": [],
                    "fsrs_review_updates": [],
                },
                config=config,
                stream_mode="custom",
            ):
                yield f"data: {_json.dumps(chunk)}\n\n"
        except Exception as exc:
            _logger.error("general lesson start stream error: %s", exc)
            yield f"data: {_json.dumps({'type': 'error', 'message': 'Stream interrupted'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/learn/projects/{project_id}/lessons/{lesson_id}/actions")
async def general_lesson_action(project_id: int, lesson_id: int, req: GeneralLessonActionRequest):
    import json as _json

    from langchain_core.runnables import RunnableConfig
    from langgraph.types import Command

    from backend.general.graph import get_general_lesson_graph

    graph = get_general_lesson_graph(app.state.checkpointer)
    thread_id = f"general-{project_id}-{lesson_id}"
    config = RunnableConfig(configurable={"thread_id": thread_id})

    action_payload: dict = {"type": req.type}
    if req.answer:
        action_payload["answer"] = req.answer
    if req.answers:
        action_payload["answers"] = req.answers
    if req.question:
        action_payload["question"] = req.question
    if req.explanation is not None:
        action_payload["explanation"] = req.explanation

    async def stream():
        try:
            async for chunk in graph.astream(
                Command(resume=action_payload),
                config=config,
                stream_mode="custom",
            ):
                if isinstance(chunk, dict) and chunk.get("type") == "done":
                    task = asyncio.create_task(
                        _run_reflect_background(chunk.get("project_id", project_id))
                    )
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)
                yield f"data: {_json.dumps(chunk)}\n\n"
        except Exception as exc:
            _logger.error("general lesson action stream error: %s", exc)
            yield f"data: {_json.dumps({'type': 'error', 'message': 'Stream interrupted'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


async def _run_reflect_background(project_id: int) -> None:
    from backend.general.reflect import run_reflect

    try:
        await run_reflect(project_id)
    except Exception as e:
        _logger.error("Reflect failed for project %d: %s", project_id, e)


async def _run_researcher(project_id: int, profile, learning_map):
    """Background task: researcher loop + extractor."""
    from backend.general.extractor import run_extractor
    from backend.general.researcher import run_researcher

    try:
        await run_researcher(project_id, profile, learning_map)
        await run_extractor(project_id)
    except Exception as e:
        _logger.error("researcher/extractor failed for project %d: %s", project_id, e)
        from backend.database import get_db

        get_db().update_general_project_status(project_id, "error")
