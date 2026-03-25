import logging
import random
from datetime import date

from langgraph.config import get_stream_writer
from langgraph.types import interrupt

from backend.database import get_db
from backend.fsrs_engine import new_card_state, update_card
from backend.general.notebooklm import get_nlm_client
from backend.models import GeneralLesson

_logger = logging.getLogger(__name__)


def _get_valid_reshuffled_quiz(quiz: list[dict], lesson_id: int) -> list[dict]:
    """Filter legacy-format questions and deterministically reshuffle answer options.

    Questions with string-format answerOptions (legacy NLM extraction) cannot be
    graded and are dropped. The remaining questions have their options shuffled
    with a seed derived from lesson_id so the same layout is used for display
    and grading across HITL re-executions.
    """
    valid = [q for q in quiz if q.get("answerOptions") and isinstance(q["answerOptions"][0], dict)]
    rng = random.Random(lesson_id)
    result = []
    for q in valid:
        opts = list(q.get("answerOptions", []))
        rng.shuffle(opts)
        result.append({**q, "answerOptions": opts})
    return result


def route_start(state: dict) -> dict:
    lesson: GeneralLesson = state["lesson"]
    retry_hint: list = []
    try:
        prior = get_db().get_last_session_for_lesson(state["project"]["id"], lesson.id)
        if prior and prior.get("quiz_score", 100) < 60:
            reshuffled = _get_valid_reshuffled_quiz(lesson.quiz_json or [], lesson.id)
            saved = prior.get("quiz_answers", [])
            for i, q in enumerate(reshuffled):
                opts = q.get("answerOptions", [])
                student_idx = saved[i] if i < len(saved) else None
                correct_idx = next((j for j, o in enumerate(opts) if o.get("isCorrect")), None)
                if student_idx != correct_idx and correct_idx is not None:
                    retry_hint.append(
                        {
                            "question": q.get("question", ""),
                            "correct_answer": opts[correct_idx].get("text", ""),
                        }
                    )
    except Exception:
        _logger.warning("route_start: failed to load prior session", exc_info=True)
    return {"phase": "reading", "retry_hint": retry_hint}


def reading_session(state: dict) -> dict:
    lesson: GeneralLesson = state["lesson"]
    while True:
        # NOTE (HITL re-execution): on every resume this node re-runs from
        # the top. writer() fires before each interrupt(), so the client
        # receives a "reading" event on the initial start AND on every resume
        # (e.g. after sending {"type": "next"} to advance). Treat as idempotent.
        interrupt_data = {
            "type": "reading",
            "study_guide": lesson.study_guide or "",
            "title": lesson.title,
            "retry_hint": state.get("retry_hint", []),
        }
        writer = get_stream_writer()
        writer(interrupt_data)
        action = interrupt(interrupt_data)
        if action.get("type") == "next":
            break
    return {"phase": "quiz"}


def quiz_session(state: dict) -> dict:
    lesson: GeneralLesson = state["lesson"]
    quiz = lesson.quiz_json or []

    # Reshuffle answerOptions to prevent position-memorisation bias.
    # IMPORTANT (HITL re-execution): this node re-runs from the top on every
    # resume. The shuffle MUST be deterministic — seeded by lesson ID — so
    # the same layout is presented to the user on first run AND used for
    # grading on the resumed run. Non-deterministic shuffles cause
    # answer-index mismatches between the two executions.
    reshuffled = _get_valid_reshuffled_quiz(quiz, lesson.id)
    if len(reshuffled) < len(quiz):
        _logger.warning(
            "quiz_session: dropped %d/%d questions with legacy string-format options",
            len(quiz) - len(reshuffled),
            len(quiz),
        )

    # If ALL questions are in legacy format, skip the quiz phase gracefully
    # rather than presenting 0 questions (which would auto-grade as 100).
    if not reshuffled:
        _logger.warning("quiz_session: no valid questions for lesson %d — skipping quiz", lesson.id)
        writer = get_stream_writer()
        writer({"type": "quiz_skipped", "reason": "content_updating", "lesson_id": lesson.id})
        return {"quiz_answers": [], "quiz_score": 0, "phase": "free_qa", "fsrs_wrong_items": []}

    # answer_format documents the expected shape of the resume payload:
    #   {"type": "answers", "answers": [<int index 0-based>, ...]}
    # Each integer is the index into question["answerOptions"].
    # NOTE (HITL re-execution): writer() is called every time the node
    # re-executes after a resume — the client should treat repeated
    # "quiz" events as idempotent re-renders, not duplicate questions.
    interrupt_data = {"type": "quiz", "questions": reshuffled, "answer_format": "option_index"}
    writer = get_stream_writer()
    writer(interrupt_data)
    action = interrupt(interrupt_data)

    answers = action.get("answers", [])
    # Grade against reshuffled — answers are indices into the per-session layout.
    score = _auto_grade(reshuffled, answers)

    # Push result immediately so the student sees score + per-question feedback.
    # Each detail includes rationale for ALL options so students understand why
    # wrong answers are wrong — not just which answer was correct.
    result_details = []
    for i, q in enumerate(reshuffled):
        opts = q.get("answerOptions", [])
        student_idx = answers[i] if i < len(answers) else None
        correct_idx = next((j for j, o in enumerate(opts) if o.get("isCorrect")), None)
        result_details.append(
            {
                "question": q.get("question", ""),
                "hint": q.get("hint", ""),
                "student_answer_index": student_idx,
                "correct_answer_index": correct_idx,
                "is_correct": student_idx == correct_idx,
                "options": [
                    {
                        "index": j,
                        "text": o.get("text", ""),
                        "is_correct": bool(o.get("isCorrect")),
                        "rationale": o.get("rationale", ""),
                    }
                    for j, o in enumerate(opts)
                ],
            }
        )
    writer = get_stream_writer()
    writer(
        {"type": "quiz_result", "score": score, "total": len(reshuffled), "details": result_details}
    )

    # Track wrong answers for FSRS spaced-repetition.
    fsrs_wrong_items: list = []
    for i, q in enumerate(reshuffled):
        opts = q.get("answerOptions", [])
        student_idx = answers[i] if i < len(answers) else None
        correct_idx = next((j for j, o in enumerate(opts) if o.get("isCorrect")), None)
        if student_idx != correct_idx and correct_idx is not None:
            fsrs_wrong_items.append(
                {
                    "q": q.get("question", ""),
                    "correct": opts[correct_idx].get("text", ""),
                    "fsrs_state": new_card_state(),
                }
            )

    return {
        "quiz_answers": answers,
        "quiz_score": score,
        "phase": "free_qa",
        "fsrs_wrong_items": fsrs_wrong_items,
    }


def _auto_grade(quiz: list[dict], answers: list) -> int:
    """Grade quiz answers. Supports two answer formats:

    - Integer index (0-based): preferred format for UI radio buttons.
      Frontend sends answers=[2, 0, 1, ...] where each value is the
      0-based index of the selected option in answerOptions[].
    - Text string: fallback, compares against the correct option's text.

    Quiz question format expected:
        {"question": "...", "answerOptions": [{"text": "...", "isCorrect": bool}, ...]}
    """
    if not quiz:
        return 100
    correct = 0
    for i, q in enumerate(quiz):
        if i >= len(answers):
            continue
        user_ans = answers[i]
        answer_options: list[dict] = q.get("answerOptions", [])
        if answer_options:
            if isinstance(user_ans, int) and 0 <= user_ans < len(answer_options):
                # Index-based answer (preferred)
                is_correct = bool(answer_options[user_ans].get("isCorrect"))
            else:
                # Text-based fallback
                user_text = str(user_ans).strip().lower()
                is_correct = any(
                    opt.get("isCorrect") and str(opt.get("text", "")).strip().lower() == user_text
                    for opt in answer_options
                )
            if is_correct:
                correct += 1
        else:
            # Legacy format: top-level answer / a field
            expected = str(q.get("answer", q.get("a", ""))).strip().lower()
            if str(user_ans).strip().lower() == expected:
                correct += 1
    return int(correct / len(quiz) * 100)


async def free_qa_session(state: dict) -> dict:
    # IMPORTANT: This node re-runs from the top on every resume (LangGraph HITL rule —
    # all code before an interrupt() call re-executes on each resume). The local variable
    # `qa_history` must therefore be seeded from persisted state, NOT initialised as [].
    nlm = get_nlm_client()
    project = state["project"]
    lesson: GeneralLesson = state["lesson"]
    qa_history: list = list(state.get("qa_history", []))

    while True:
        interrupt_data = {"type": "free_qa", "history": qa_history}
        writer = get_stream_writer()
        writer(interrupt_data)
        action = interrupt(interrupt_data)
        if action.get("type") == "exit":
            break
        question = action.get("question", "")
        if question:
            # Prefix lesson title so NLM answers in the context of the current
            # lesson rather than the entire notebook indiscriminately.
            contextual_q = f"关于「{lesson.title}」，{question}"
            # nlm.ask is placed AFTER interrupt() — executes only once per resume.
            try:
                answer = await nlm.ask(project["notebook_id"], contextual_q)
            except Exception as exc:
                _logger.error("free_qa_session: nlm.ask failed: %s", exc)
                answer = "抱歉，知识库暂时无法响应，请稍后再试。"
            qa_history = [*qa_history, {"q": question, "a": answer}]
            writer = get_stream_writer()
            writer({"type": "free_qa_answer", "answer": answer, "history": qa_history})

    return {"qa_history": qa_history, "phase": "save"}


async def save_results(state: dict) -> dict:
    db = get_db()
    lesson_id = state["lesson"].id
    try:
        db.save_general_session(
            project_id=state["project"]["id"],
            lesson_id=lesson_id,
            quiz_answers=state.get("quiz_answers", []),
            quiz_score=state.get("quiz_score", 0),
            qa_history=state.get("qa_history", []),
        )
    except Exception as exc:
        _logger.error("save_results: failed to save general session: %s", exc)

    # Persist FSRS states for wrong quiz answers.
    wrong = state.get("fsrs_wrong_items", [])
    if wrong:
        try:
            existing = db.get_general_student_model_full(state["project"]["id"])
            if existing:
                by_key = {
                    (item["lesson_id"], item["q"]): item
                    for item in existing.fsrs_due
                    if isinstance(item, dict) and "lesson_id" in item and "q" in item
                }
                for w in wrong:
                    key = (lesson_id, w["q"])
                    if key in by_key:
                        by_key[key] = {
                            **by_key[key],
                            "fsrs_state": update_card(
                                by_key[key]["fsrs_state"],
                                is_correct=False,
                                response_seconds=10.0,
                            ),
                        }
                    else:
                        by_key[key] = {"lesson_id": lesson_id, **w}
                db.save_general_student_model(
                    state["project"]["id"],
                    existing.model_copy(
                        update={
                            "fsrs_due": list(by_key.values()),
                            "updated": date.today().isoformat(),
                        }
                    ),
                )
        except Exception as exc:
            _logger.error("save_results: failed to persist FSRS wrong items: %s", exc)

    writer = get_stream_writer()
    writer({"type": "done", "project_id": state["project"]["id"]})
    return {"phase": "done"}
