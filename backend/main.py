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
    word: str | None = None
    context: str | None = None
    sentence: str | None = None
    text: str | None = None
    answer: str | None = None
    response_seconds: float | None = None


class UpdateProfileRequest(BaseModel):
    interests_update: str = Field(min_length=1, max_length=500)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async with AsyncSqliteSaver.from_conn_string("./checkpoints.sqlite3") as cp:
        await cp.setup()
        app.state.checkpointer = cp
        yield


app = FastAPI(title="DynamicLingo API", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ─── Planner ──────────────────────────────────────────────────────────────────


@app.post("/api/planner/run")
async def run_planner():
    import threading

    from backend.database import get_db

    db = get_db()
    if db.get_today_article() is not None:
        return {"status": "already_ready", "date": date.today().isoformat()}

    async def _run_planner() -> None:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        from backend.planner.agent import create_deep_agent_planner, get_planner_config

        async with AsyncSqliteSaver.from_conn_string("./checkpoints.sqlite3") as cp:
            await cp.setup()
            planner = create_deep_agent_planner(cp)
            config = get_planner_config()
            await planner.ainvoke(  # type: ignore[attr-defined]
                {"messages": [{"role": "user", "content": "为今天准备一节课"}]},
                config,
            )

    def run_in_thread() -> None:
        asyncio.run(_run_planner())

    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()
    return {"status": "started", "date": date.today().isoformat()}


@app.get("/api/planner/status")
async def planner_status():
    from backend.database import get_db

    db = get_db()
    article = db.get_today_article()
    task = db.get_today_writing_task()
    return {"ready": article is not None and task is not None}


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

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/lesson/start")
async def start_lesson():
    """Initialize or resume today's LangGraph session."""
    from backend.tutor.graph import get_tutor_graph

    graph = get_tutor_graph(app.state.checkpointer)
    config: RunnableConfig = {"configurable": {"thread_id": date.today().isoformat()}}

    checkpoint_tuple = await app.state.checkpointer.aget_tuple(config)
    if checkpoint_tuple is not None and checkpoint_tuple.metadata.get("next"):
        return JSONResponse({"status": "already_started"}, status_code=409)

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
