import logging
import random
from datetime import date
from typing import Literal

from langgraph.config import get_stream_writer
from langgraph.types import Command, interrupt

from backend.database import Database, get_db
from backend.fsrs_engine import new_card_state, update_card
from backend.general.notebooklm import get_nlm_client
from backend.llm import get_llm  # noqa: F401 — used in metacog_session
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


def reading_session(state: dict) -> Command[Literal["scaffold_quiz", "quiz"]]:
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
    mode = state.get("session_mode", "normal")
    goto: Literal["scaffold_quiz", "quiz"] = "scaffold_quiz" if mode == "scaffold" else "quiz"
    return Command(goto=goto, update={"phase": "quiz"})


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
# scaffold_quiz (Task 6)
# ---------------------------------------------------------------------------

# [P2#14] 10 growth mindset messages for variety
_GROWTH_MINDSET_MESSAGES = [
    "感到困难是正常的——你的大脑正在建立新的神经连接，下次一定比这次强！",
    "每道答错的题都告诉你下次该加强哪里，这是最有价值的信息。",
    "你只是还没掌握这部分内容。我们来看看哪里可以突破。",
    "挣扎感说明你在真正学习，而不只是复习已知的东西。坚持住！",
    "学习就像锻炼肌肉——感到吃力恰恰意味着你在变强。",
    "犯错是大脑构建新连接的方式。每一次错误都让你离掌握更近一步。",
    "进步不总是线性的。今天的困难是明天突破的基础。",
    "最优秀的学习者不是不犯错的人，而是从错误中学到最多的人。",
    "你选择了挑战自己，这本身就值得肯定。让我们一起找到突破口。",
    "研究表明：感到「刚好有点难」的学习效果最好。你正在最佳学习区间里。",
]


def scaffold_quiz(state: dict) -> dict:
    """Quiz for scaffold mode (score < 46%): hints visible + growth mindset on low score."""
    import random as _rnd

    lesson: GeneralLesson = state["lesson"]
    quiz = lesson.quiz_json or []
    reshuffled = _get_valid_reshuffled_quiz(quiz, lesson.id)

    if not reshuffled:
        _logger.warning("scaffold_quiz: no valid questions for lesson %d", lesson.id)
        writer = get_stream_writer()
        writer({"type": "quiz_skipped", "reason": "content_updating", "lesson_id": lesson.id})
        return {"quiz_answers": [], "quiz_score": 0, "phase": "free_qa", "fsrs_wrong_items": []}

    # -- interrupt: all code above is idempotent --
    interrupt_data = {
        "type": "quiz",
        "questions": reshuffled,
        "answer_format": "option_index",
        "hints_visible": True,  # scaffold: show hints
    }
    writer = get_stream_writer()
    writer(interrupt_data)
    action = interrupt(interrupt_data)

    answers = action.get("answers", [])
    lesson_score, display_score, result_details, fsrs_wrong_items, _ = _grade_and_build_details(
        reshuffled, answers
    )

    growth_message = _rnd.choice(_GROWTH_MINDSET_MESSAGES) if lesson_score < 46 else None

    writer = get_stream_writer()
    writer(
        {
            "type": "quiz_result",
            "lesson_score": lesson_score,
            "display_score": display_score,
            "total": len(reshuffled),
            "details": result_details,
            "growth_mindset_message": growth_message,
        }
    )

    return {
        "quiz_answers": answers,
        "quiz_score": lesson_score,  # [P0#3] lesson-only score for routing
        "phase": "free_qa",
        "fsrs_wrong_items": fsrs_wrong_items,
    }


# ---------------------------------------------------------------------------
# challenge_quiz (Task 7)
# ---------------------------------------------------------------------------


def challenge_quiz(state: dict) -> dict:
    """Quiz for challenge mode (score > 81%): no hints, FSRS interleaving, metacog follow-up.

    [P0#1] Uses review_questions_cache for HITL idempotency. On first run, loads
    review questions from DB and returns them in state for checkpoint persistence.
    On resume (re-execution), reads from cache instead of re-querying.
    """
    lesson: GeneralLesson = state["lesson"]
    quiz = lesson.quiz_json or []
    reshuffled = _get_valid_reshuffled_quiz(quiz, lesson.id)

    # [P0#1] HITL-safe: use cached review questions if available
    review_qs: list[dict] = state.get("review_questions_cache") or []
    if not review_qs:
        try:
            db = get_db()  # [P2#17] single db reference
            existing = db.get_general_student_model_full(state["project"]["id"])
            fsrs_due = existing.fsrs_due if existing else []
            review_qs = _get_review_questions(fsrs_due, db, max_count=3)
        except Exception:
            _logger.warning("challenge_quiz: failed to load FSRS review questions", exc_info=True)

    # Interleave review questions evenly (every 3rd question)
    combined: list[dict] = []
    review_iter = iter(review_qs)
    for i, q in enumerate(reshuffled):
        combined.append(q)
        if (i + 1) % 3 == 0:
            review_q = next(review_iter, None)
            if review_q:
                combined.append(review_q)
    for review_q in review_iter:
        combined.append(review_q)
    reshuffled = combined

    if not reshuffled:
        _logger.warning("challenge_quiz: no questions for lesson %d", lesson.id)
        writer = get_stream_writer()
        writer({"type": "quiz_skipped", "reason": "content_updating", "lesson_id": lesson.id})
        return {
            "quiz_answers": [],
            "quiz_score": 0,
            "phase": "metacog",
            "fsrs_wrong_items": [],
            "metacog_question": None,
            "review_questions_cache": [],
            "fsrs_review_updates": [],
        }

    # [P0#2] Strip internal fields before sending to frontend
    clean_questions = [{k: v for k, v in q.items() if not k.startswith("_")} for q in reshuffled]

    # -- interrupt: deterministic shuffle + cached review Qs = idempotent --
    interrupt_data = {
        "type": "quiz",
        "questions": clean_questions,  # [P0#2] no _is_review/_fsrs_item leak
        "answer_format": "option_index",
        "hints_visible": False,  # challenge: hide hints
    }
    writer = get_stream_writer()
    writer(interrupt_data)
    action = interrupt(interrupt_data)

    answers = action.get("answers", [])
    lesson_score, display_score, result_details, fsrs_wrong_items, fsrs_review_updates = (
        _grade_and_build_details(reshuffled, answers)
    )

    # Pick first correct non-review answer for metacog follow-up
    metacog_question: dict | None = None
    for i, q in enumerate(reshuffled):
        if not q.get("_is_review"):
            opts = q.get("answerOptions", [])
            student_idx = answers[i] if i < len(answers) else None
            correct_idx = next((j for j, o in enumerate(opts) if o.get("isCorrect")), None)
            if student_idx == correct_idx and correct_idx is not None:
                metacog_question = {
                    "question": q.get("question", ""),
                    "correct_answer": opts[correct_idx].get("text", ""),
                }
                break

    writer = get_stream_writer()
    writer(
        {
            "type": "quiz_result",
            "lesson_score": lesson_score,
            "display_score": display_score,
            "total": len(reshuffled),
            "details": result_details,
        }
    )

    return {
        "quiz_answers": answers,
        "quiz_score": lesson_score,  # [P0#3] lesson-only for routing
        "phase": "metacog",
        "fsrs_wrong_items": fsrs_wrong_items,
        "metacog_question": metacog_question,
        "metacog_feedback": "",  # reset for metacog_session
        "review_questions_cache": review_qs,  # [P0#1] persist for HITL checkpoint
        "fsrs_review_updates": fsrs_review_updates,  # [P2#11] deferred to save_results
    }


# ---------------------------------------------------------------------------
# metacog_session (Task 8)
# ---------------------------------------------------------------------------


async def metacog_session(state: dict) -> dict:
    """Challenge mode metacognitive follow-up: ask student to explain a correct answer.

    [P1#6] Uses metacog_feedback (not metacog_answered) as idempotency guard.
    If metacog_feedback already has a value, the node was already completed in a
    prior execution and we skip. This works because the feedback string is persisted
    in the checkpoint after the node returns.

    Note: uses raw llm.ainvoke() intentionally — output is free-form feedback text,
    not structured data. with_structured_output() would add unnecessary constraint.
    """
    # [P1#6] Real idempotency guard: skip if feedback already generated
    existing_feedback = state.get("metacog_feedback", "")
    if existing_feedback:
        return {"metacog_feedback": existing_feedback}

    metacog_question = state.get("metacog_question")
    if not metacog_question:
        return {"metacog_feedback": ""}

    writer = get_stream_writer()
    writer(
        {
            "type": "metacog_prompt",
            "question": metacog_question["question"],
            "correct_answer": metacog_question["correct_answer"],
            "prompt": (
                f"你刚才正确回答了这道题：「{metacog_question['question']}」\n"
                f"正确答案是：「{metacog_question['correct_answer']}」\n"
                "请用自己的话解释一下，为什么这个答案是正确的？"
            ),
        }
    )

    action = interrupt({"type": "metacog_prompt"})
    explanation = action.get("explanation", "")

    feedback = ""
    if explanation:
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = get_llm()
        messages = [
            SystemMessage(
                content=(
                    "你是一位鼓励型学习教练。学生刚答对了一道测验题，"
                    "现在解释了为什么答案正确。"
                    "给出2-3句话的反馈：确认理解正确的部分，补充他们可能遗漏的关键点。"
                    "语气积极温暖，使用中文。不要超过3句话。"
                )
            ),
            HumanMessage(
                content=(
                    f"题目：{metacog_question['question']}\n"
                    f"正确答案：{metacog_question['correct_answer']}\n"
                    f"学生的解释：{explanation}"
                )
            ),
        ]
        try:
            response = await llm.ainvoke(messages)
            feedback = str(response.content)
        except Exception as exc:
            _logger.warning("metacog_session: LLM call failed: %s", exc)
            # [P2#15] Neutral fallback — don't give false positive when LLM unavailable
            feedback = "反馈生成暂时不可用，你的解释已记录。继续加油！"

    writer = get_stream_writer()
    writer({"type": "metacog_feedback", "feedback": feedback, "explanation": explanation})

    return {"metacog_feedback": feedback}
