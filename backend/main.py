import json
from contextlib import asynccontextmanager
from datetime import date

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from langgraph.checkpoint.sqlite import SqliteSaver
    with SqliteSaver.from_conn_string("./db.sqlite3") as cp:
        cp.setup()
        app.state.checkpointer = cp
        yield


app = FastAPI(title="DynamicLingo API", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ─── Planner ──────────────────────────────────────────────────────────────────

@app.post("/api/planner/run")
async def run_planner(background_tasks: BackgroundTasks):
    from backend.planner.agent import get_planner, get_planner_config
    planner = get_planner(app.state.checkpointer)
    config = get_planner_config()
    background_tasks.add_task(
        planner.ainvoke,
        {"messages": [{"role": "user", "content": "为今天准备一节课"}]},
        config,
    )
    return {"status": "started", "date": date.today().isoformat()}


@app.get("/api/planner/status")
async def planner_status():
    from backend.database import Database
    db = Database()
    article = db.get_today_article()
    task = db.get_today_writing_task()
    return {"ready": article is not None and task is not None}


# ─── Onboarding ───────────────────────────────────────────────────────────────

@app.post("/api/onboarding/message")
async def onboarding_message(body: dict):
    from backend.onboarding.agent import create_onboarding_agent, ONBOARDING_CONFIG
    agent = create_onboarding_agent(app.state.checkpointer)

    async def generate():
        async for chunk in agent.astream(
            {"messages": [{"role": "user", "content": body.get("message", "")}]},
            config=ONBOARDING_CONFIG,
            stream_mode="messages",
        ):
            token, _ = chunk
            if hasattr(token, "content") and token.content:
                yield f"data: {json.dumps({'type': 'token', 'content': token.content})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/onboarding/status")
async def onboarding_status():
    from backend.database import Database
    db = Database()
    profile = db.get_user_profile()
    return {"ready": profile is not None}


@app.post("/api/onboarding/preferences")
async def save_preferences(body: dict):
    from backend.database import Database
    db = Database()
    profile = db.get_user_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    updated = profile.model_copy(update={
        "bandwidth_minutes": body.get("bandwidth_minutes", 25),
        "writing_mode": body.get("writing_mode", "professional"),
    })
    db.upsert_user_profile(updated)
    return {"status": "ok"}


# ─── Lesson ───────────────────────────────────────────────────────────────────

@app.get("/api/lesson/today")
async def get_today_lesson():
    from backend.database import Database
    db = Database()
    article = db.get_today_article()
    task = db.get_today_writing_task()
    if article is None or task is None:
        raise HTTPException(status_code=404, detail="Today's lesson not ready. Run planner first.")
    return {"article": article.model_dump(), "task": task.model_dump()}


@app.post("/api/lesson/action")
async def lesson_action(action: dict):
    from backend.tutor.graph import get_tutor_graph
    from langgraph.types import Command
    graph = get_tutor_graph(app.state.checkpointer)
    config = {"configurable": {"thread_id": date.today().isoformat()}}

    async def generate():
        async for chunk in graph.astream(
            Command(resume=action),
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
    config = {"configurable": {"thread_id": date.today().isoformat()}}

    async def generate():
        async for chunk in graph.astream(
            {"user_profile": None, "today_article": None, "today_task": None,
             "review_queue": [], "review_index": 0, "user_writing": None,
             "writing_feedback": None, "messages": []},
            config=config,
            stream_mode="custom",
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ─── Profile ──────────────────────────────────────────────────────────────────

@app.get("/api/profile")
async def get_profile():
    from backend.database import Database
    db = Database()
    profile = db.get_user_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile.model_dump()


@app.patch("/api/profile")
async def update_profile(body: dict):
    from backend.database import Database
    db = Database()
    profile = db.get_user_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    new_interests_str = body.get("interests_update", "")
    if new_interests_str:
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(model="claude-haiku-4-5-20251001")
        response = llm.invoke(f"""
Current interests: {profile.interests}
User update: "{new_interests_str}"
Return a JSON array of updated interests (3-5 items). Only the array, no explanation.
""")
        new_interests = json.loads(response.content)
        profile = profile.model_copy(update={"interests": new_interests})
    db.upsert_user_profile(profile)
    return profile.model_dump()


# ─── Vocab ────────────────────────────────────────────────────────────────────

@app.get("/api/vocab")
async def get_vocab():
    from backend.database import Database
    db = Database()
    items = db.get_all_vocab_items()
    return [item.model_dump() for item in items]
