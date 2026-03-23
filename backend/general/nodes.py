import asyncio
import logging

from langgraph.config import get_stream_writer
from langgraph.types import interrupt

from backend.database import get_db
from backend.general.notebooklm import get_nlm_client
from backend.models import GeneralLesson

_logger = logging.getLogger(__name__)


def route_start(state: dict) -> dict:
    return {"phase": "reading"}


def reading_session(state: dict) -> dict:
    lesson: GeneralLesson = state["lesson"]
    while True:
        action = interrupt(
            {
                "type": "reading",
                "study_guide": lesson.study_guide or "",
                "title": lesson.title,
            }
        )
        if action.get("type") == "next":
            break
    return {"phase": "quiz"}


def quiz_session(state: dict) -> dict:
    lesson: GeneralLesson = state["lesson"]
    quiz = lesson.quiz_json or []

    action = interrupt({"type": "quiz", "questions": quiz})

    answers = action.get("answers", [])
    score = _auto_grade(quiz, answers)
    return {"quiz_answers": answers, "quiz_score": score, "phase": "free_qa"}


def _auto_grade(quiz: list[dict], answers: list[str]) -> int:
    if not quiz:
        return 100
    correct = 0
    for i, q in enumerate(quiz):
        user_ans = answers[i].strip().lower() if i < len(answers) else ""
        expected = str(q.get("answer", q.get("a", ""))).strip().lower()
        if user_ans and expected and user_ans[:20] == expected[:20]:
            correct += 1
    return int(correct / len(quiz) * 100)


async def free_qa_session(state: dict) -> dict:
    # IMPORTANT: This node re-runs from the top on every resume (LangGraph HITL rule —
    # all code before an interrupt() call re-executes on each resume). The local variable
    # `qa_history` must therefore be seeded from persisted state, NOT initialised as [].
    nlm = get_nlm_client()
    project = state["project"]
    qa_history: list = list(state.get("qa_history", []))

    while True:
        action = interrupt({"type": "free_qa", "history": qa_history})
        if action.get("type") == "exit":
            break
        question = action.get("question", "")
        if question:
            # nlm.ask is placed AFTER interrupt() — executes only once per resume.
            answer = await nlm.ask(project["notebook_id"], question)
            qa_history = [*qa_history, {"q": question, "a": answer}]
            writer = get_stream_writer()
            writer({"type": "free_qa_answer", "answer": answer, "history": qa_history})

    return {"qa_history": qa_history, "phase": "save"}


def save_results(state: dict) -> dict:
    db = get_db()
    db.save_general_session(
        project_id=state["project"]["id"],
        lesson_id=state["lesson"].id,
        quiz_answers=state.get("quiz_answers", []),
        quiz_score=state.get("quiz_score", 0),
        qa_history=state.get("qa_history", []),
    )
    asyncio.create_task(_run_reflect_background(state["project"]["id"]))
    return {"phase": "done"}


async def _run_reflect_background(project_id: int) -> None:
    from backend.general.reflect import run_reflect

    try:
        await run_reflect(project_id)
    except Exception as e:
        _logger.error("Reflect failed: %s", e)
