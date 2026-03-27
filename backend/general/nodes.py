import logging
import random
from datetime import date
from typing import Literal

from langgraph.config import get_stream_writer
from langgraph.types import Command, interrupt

from backend.database import Database, get_db
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


def _get_review_questions(fsrs_due: list[dict], db: Database, max_count: int = 3) -> list[dict]:
    """Load FSRS-due items and reconstruct full MCQ question dicts.

    Returns questions with _is_review=True and _fsrs_item=<original item>
    so challenge_quiz can track FSRS state updates after grading.
    """
    from backend.fsrs_engine import is_due

    due_items = [
        item for item in fsrs_due if isinstance(item, dict) and is_due(item.get("fsrs_state", {}))
    ]

    result: list[dict] = []
    for item in due_items[:max_count]:
        lesson_id = item.get("lesson_id")
        question_text = item.get("q", "")
        if not lesson_id or not question_text:
            continue
        lesson = db.get_general_lesson(lesson_id)
        if not lesson or not lesson.quiz_json:
            continue
        for q in lesson.quiz_json:
            if q.get("question") == question_text:
                result.append({**q, "_is_review": True, "_fsrs_item": item})
                break
    return result


def _grade_and_build_details(
    reshuffled: list[dict], answers: list
) -> tuple[int, int, list[dict], list[dict], list[tuple[dict, bool]]]:
    """Shared quiz grading logic. [P2#10] Eliminates code duplication across quiz variants.

    Returns:
        lesson_score: Percentage excluding review questions (for session_mode routing).
        display_score: Percentage including all questions (for student display).
        result_details: Per-question breakdown for SSE quiz_result event.
        fsrs_wrong_items: New wrong items for FSRS tracking (non-review only).
        fsrs_review_updates: (fsrs_item, is_correct) pairs for deferred FSRS update.
    """
    lesson_correct = lesson_total = all_correct = 0
    result_details: list[dict] = []
    fsrs_wrong_items: list[dict] = []
    fsrs_review_updates: list[tuple[dict, bool]] = []

    for i, q in enumerate(reshuffled):
        opts = q.get("answerOptions", [])
        student_idx = answers[i] if i < len(answers) else None
        correct_idx = next((j for j, o in enumerate(opts) if o.get("isCorrect")), None)
        is_correct = student_idx == correct_idx
        is_review = bool(q.get("_is_review"))

        all_correct += int(is_correct)
        if not is_review:
            lesson_total += 1
            lesson_correct += int(is_correct)

        result_details.append(
            {
                "question": q.get("question", ""),
                "hint": q.get("hint", ""),
                "student_answer_index": student_idx,
                "correct_answer_index": correct_idx,
                "is_correct": is_correct,
                "is_review": is_review,
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

        # [P2#11] Track FSRS review updates (deferred to save_results)
        if is_review and q.get("_fsrs_item"):
            fsrs_review_updates.append((q["_fsrs_item"], is_correct))
        # Track new wrong items (non-review only, avoids lesson_id misattribution)
        elif not is_correct and correct_idx is not None:
            fsrs_wrong_items.append(
                {
                    "q": q.get("question", ""),
                    "correct": opts[correct_idx].get("text", ""),
                    "fsrs_state": new_card_state(),
                }
            )

    lesson_score = round(lesson_correct / lesson_total * 100) if lesson_total else 0
    display_score = round(all_correct / len(reshuffled) * 100) if reshuffled else 0
    return lesson_score, display_score, result_details, fsrs_wrong_items, fsrs_review_updates


def route_start(state: dict) -> Command[Literal["reading", "challenge_quiz"]]:
    """Score-gated session routing: scaffold (<46%) / normal (46-81%) / challenge (>81%)."""
    lesson: GeneralLesson = state["lesson"]
    retry_hint: list = []
    session_mode = "normal"

    try:
        prior = get_db().get_last_session_for_lesson(state["project"]["id"], lesson.id)
        if prior:
            score = prior.get("quiz_score", 50)
            if score < 46:
                session_mode = "scaffold"
            elif score > 81:
                session_mode = "challenge"
            else:
                session_mode = "normal"

            # Compute retry_hint for scaffold/normal modes
            if session_mode != "challenge" and score < 60:
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

    goto: Literal["reading", "challenge_quiz"] = (
        "challenge_quiz" if session_mode == "challenge" else "reading"
    )
    return Command(
        goto=goto,
        update={
            "phase": "reading",
            "session_mode": session_mode,
            "retry_hint": retry_hint,
            # [P1#4] Initialize ALL new state fields
            "metacog_question": None,
            "metacog_feedback": "",
            "review_questions_cache": [],
            "fsrs_review_updates": [],
        },
    )


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


# ---------------------------------------------------------------------------
# Adaptive nodes (stubs — implemented in Tasks 6-8)
# ---------------------------------------------------------------------------


def scaffold_quiz(state: dict) -> dict:
    """Quiz for scaffold mode — stub, replaced in Task 6."""
    raise NotImplementedError("scaffold_quiz not yet implemented")


def challenge_quiz(state: dict) -> dict:
    """Quiz for challenge mode — stub, replaced in Task 7."""
    raise NotImplementedError("challenge_quiz not yet implemented")


async def metacog_session(state: dict) -> dict:
    """Metacognitive follow-up — stub, replaced in Task 8."""
    raise NotImplementedError("metacog_session not yet implemented")
