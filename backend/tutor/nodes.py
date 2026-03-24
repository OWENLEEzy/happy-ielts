from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from langgraph.types import Command, interrupt

from backend import memory
from backend.database import get_db
from backend.fsrs_engine import new_card_state, update_card
from backend.llm import get_llm
from backend.models import VocabItem, VocabItemCreate
from backend.student_model import read_student_model
from backend.tutor.tools import analyze_sentence, explain_word, run_feedback, signal_done_reading

logger = logging.getLogger(__name__)
_db = get_db()


@lru_cache(maxsize=1)
def _get_reading_llm():
    return get_llm().bind_tools([explain_word, analyze_sentence, signal_done_reading])


def route_start(_state: dict) -> Command[Literal["spaced_review", "reading"]]:
    """Load profile + article + task, then route based on due vocab."""
    profile = _db.get_user_profile()
    article = _db.get_today_article()
    task = _db.get_today_writing_task()
    due_items = _db.get_due_vocab_items(date.today())

    updates: dict[str, Any] = {
        "user_profile": profile,
        "today_article": article,
        "today_task": task,
    }

    if due_items:
        updates["review_queue"] = due_items
        updates["review_index"] = 0
        return Command(update=updates, goto="spaced_review")

    return Command(update=updates, goto="reading")


def _extract_sentence(text: str, phrase: str) -> str:
    """Return the sentence in text that contains phrase, or a short fallback clause."""
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if phrase.lower() in sent.lower():
            return sent.strip()[:400]
    # Build a minimal context clause so it's never a bare word
    return f"{phrase} is used in this context."[:400]


def _find_valid_item(queue: list, start: int) -> tuple[int, VocabItem | None]:
    """Return the first index >= start with a usable context sentence, or (len, None)."""
    for i in range(start, len(queue)):
        raw = queue[i]
        item = raw if isinstance(raw, VocabItem) else VocabItem(**raw)
        ctx = item.context_sentence or ""
        if ctx and ctx != item.word and item.word.lower() in ctx.lower() and len(ctx) <= 400:
            return i, item
        logger.warning(
            "spaced_review: skipping %r — unusable context (len=%d)", item.word, len(ctx)
        )
    return len(queue), None


def spaced_review(state: dict) -> Command[Literal["spaced_review", "reading"]]:
    """Present one fill-blank card; loop until all done."""
    queue: list = state["review_queue"]
    index, item = _find_valid_item(queue, state["review_index"])

    if item is None:
        return Command(update={"review_index": index}, goto="reading")

    event = {
        "type": "fill_blank",
        "question": f"Fill in the blank: {item.context_sentence.replace(item.word, '______')}",
        "word": item.word,
    }
    get_stream_writer()(event)
    user_answer = interrupt(event)

    is_correct = user_answer.get("answer", "").strip().lower() == item.word.lower()
    correct_delta = 1 if is_correct else 0
    current_correct = state.get("vocab_correct", 0)
    response_seconds = user_answer.get("response_seconds", 10.0)

    new_state = update_card(item.fsrs_state, is_correct, response_seconds)
    new_next_review = new_state["due"][:10]

    updated_item = VocabItemCreate(
        word=item.word,
        context_sentence=item.context_sentence,
        source=item.source,
        next_review=new_next_review,
        fsrs_state=new_state,
        article_id=item.article_id,
    )
    _db.upsert_vocab_item(updated_item)

    next_index = index + 1
    if next_index < len(queue):
        return Command(
            update={"review_index": next_index, "vocab_correct": current_correct + correct_delta},
            goto="spaced_review",
        )
    return Command(update={"vocab_correct": current_correct + correct_delta}, goto="reading")


def _handle_explain_word(user_action: dict, state: dict, writer: Any) -> None:
    """Handle explain_word action (structured or LLM-extracted args)."""
    word = user_action.get("word", "")
    if not word:
        writer({"type": "error", "message": "explain_word requires a 'word' field"})
        return
    level = state["user_profile"].level if state["user_profile"] else 5
    result = explain_word.invoke(
        {"word": word, "context": user_action.get("context", ""), "level": level}
    )
    if state["today_article"]:
        _db.upsert_vocab_item(
            VocabItemCreate(
                word=word,
                context_sentence=_extract_sentence(user_action.get("context", ""), word),
                source="reading_click",
                next_review=date.today().isoformat(),
                fsrs_state=new_card_state(),
                article_id=state["today_article"].id,
            )
        )
    writer({"type": "word_explanation", "result": result})


def reading_session(state: dict) -> Command[Literal["writing_task"]]:
    """Loop: wait for user messages, route via LLM or handle structured actions."""
    _db.upsert_reading_start(date.today())

    article = state["today_article"]
    profile = state["user_profile"]
    student_model = read_student_model()
    writing_level = student_model.get("levels", {}).get("writing", profile.level if profile else 5)

    system_prompt = (
        "你是一位英语教师，正在帮助学生阅读以下文章。"
        f"学生写作水平：{writing_level}/10。\n\n"
        f"文章全文：\n{article.full_text if article else '（无文章）'}\n\n"
        "职责：\n"
        "- 解释词汇 → 调用 explain_word\n"
        "- 分析句子结构 → 调用 analyze_sentence\n"
        "- 判断学生已读完时 → 调用 signal_done_reading\n"
        "- 其他问题 → 直接用中文回答（不超过150字）"
    )

    while True:
        writer = get_stream_writer()
        awaiting_event = {
            "type": "awaiting_action",
            "article_full_text": article.full_text if article else "",
            "highlight_indices": article.highlight_indices if article else [],
            "user_level": profile.level if profile else 5,
        }
        writer(awaiting_event)
        user_action = interrupt(awaiting_event)
        action_type = user_action.get("type")

        # --- Backward-compatible structured actions ---
        if action_type == "done_reading":
            break
        elif action_type == "explain_word":
            _handle_explain_word(user_action, state, writer)
            continue
        elif action_type == "analyze_sentence":
            sentence = user_action.get("sentence", "")
            if not sentence:
                writer({"type": "error", "message": "analyze_sentence requires a 'sentence' field"})
            else:
                result = analyze_sentence.invoke({"sentence": sentence})
                writer({"type": "sentence_analysis", "result": result})
            continue

        # --- LLM routing for free-form messages ---
        user_message = user_action.get("message", "")
        if not user_message:
            continue

        response = _get_reading_llm().invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
        )

        done = False
        for tool_call in response.tool_calls:  # type: ignore[union-attr]
            name = tool_call["name"]
            args = tool_call.get("args", {})
            if name == "signal_done_reading":
                done = True
            elif name == "explain_word":
                _handle_explain_word(args, state, writer)
            elif name == "analyze_sentence":
                if args.get("sentence"):
                    result = analyze_sentence.invoke(args)
                    writer({"type": "sentence_analysis", "result": result})
        if done:
            break

        if response.content and not response.tool_calls:  # type: ignore[union-attr]
            writer({"type": "tutor_message", "result": str(response.content)})

    return Command(goto="writing_task")


def writing_task(state: dict) -> dict:
    """Present writing task and wait for submission."""
    task = state["today_task"]
    event = {
        "type": "writing_task",
        "instruction": task.instruction if task else "",
        "min_words": task.min_words if task else 50,
    }
    get_stream_writer()(event)
    user_action = interrupt(event)
    return {"user_writing": user_action.get("text", "")}


def evaluate_writing(state: dict) -> dict:
    """Run AI feedback on the user's writing, depth-adapted to student model level."""
    writer = get_stream_writer()
    profile = state["user_profile"]
    task = state["today_task"]
    user_text = state.get("user_writing", "")

    if not user_text or not task or not profile:
        writer({"type": "error", "message": "Missing writing or task context"})
        return {}

    # Determine feedback depth from student model (falls back to profile.level)
    student_model = read_student_model()
    writing_level = student_model.get("levels", {}).get("writing", profile.level)
    if writing_level <= 4:
        depth = "basic"
    elif writing_level <= 7:
        depth = "intermediate"
    else:
        depth = "advanced"

    try:
        feedback = run_feedback(
            user_text=user_text,
            task=task,
            user_goal=profile.goal,
            level=writing_level,
            depth=depth,
        )
    except Exception as exc:
        logger.error("evaluate_writing: feedback generation failed: %s", exc)
        writer({"type": "error", "message": "写作批改暂时失败，请稍后重试。"})
        return {}
    writer({"type": "feedback", "result": feedback.model_dump()})
    return {
        "writing_feedback": feedback,
        "messages": [{"role": "assistant", "content": f"Score: {feedback.overall_score}/10"}],
    }


def save_results(state: dict) -> dict:
    """Persist submission, update vocab, write Tutor observations to memory."""
    from backend.models import WritingSubmissionCreate

    feedback = state.get("writing_feedback")
    task = state.get("today_task")
    user_text = state.get("user_writing", "")
    article = state.get("today_article")

    if feedback and task and user_text:
        sub = WritingSubmissionCreate(
            task_id=task.id,
            user_text=user_text,
            overall_score=feedback.overall_score,
            grammar_errors=feedback.grammar_errors,
            chinglish_flags=feedback.chinglish_flags,
            rewrite_suggestions=feedback.rewrite_suggestions,
            submitted_at=datetime.now(UTC),
        )
        _db.save_writing_submission(sub)
        article_id = article.id if article else None
        for flag in feedback.chinglish_flags:
            _db.upsert_vocab_item(
                VocabItemCreate(
                    word=flag.original,
                    context_sentence=_extract_sentence(user_text, flag.original),
                    source="writing_error",
                    next_review=date.today().isoformat(),
                    fsrs_state=new_card_state(),
                    article_id=article_id,
                )
            )

        # Write Tutor observation to memory (sync file I/O, safe in sync node)
        chinglish_issues = [f.issue for f in feedback.chinglish_flags]
        obs_text = (
            f"写作分数: {feedback.overall_score}/10, "
            f"chinglish 问题: {chinglish_issues}, "
            f"文章逻辑: {article.article_logic if article else 'unknown'}, "
            f"话题: {article.topic_tags[0] if article and article.topic_tags else 'unknown'}"
        )
        memory.append_observation(
            {
                "date": date.today().isoformat(),
                "observation": obs_text,
            }
        )

    # Compute completed phases authoritatively before clearing state
    phases: list[str] = []
    if state.get("review_queue"):
        phases.append("review")
    phases.append("reading")  # save_results only executes after reading completed
    if state.get("user_writing") is not None or feedback is not None:
        phases.append("writing")
    if feedback is not None:
        phases.append("feedback")

    return {"user_writing": None, "writing_feedback": None, "phases_completed": phases}
