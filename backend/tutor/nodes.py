from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Literal

from langgraph.config import get_stream_writer
from langgraph.types import Command, interrupt

from backend import memory
from backend.database import get_db
from backend.fsrs_engine import new_card_state, update_card
from backend.models import VocabItem, VocabItemCreate
from backend.tutor.tools import analyze_sentence, explain_word, run_feedback

logger = logging.getLogger(__name__)
_db = get_db()


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


def spaced_review(state: dict) -> Command[Literal["spaced_review", "reading"]]:
    """Present one fill-blank card; loop until all done."""
    item_data = state["review_queue"][state["review_index"]]
    item = item_data if isinstance(item_data, VocabItem) else VocabItem(**item_data)

    event = {
        "type": "fill_blank",
        "question": f"Fill in the blank: {item.context_sentence.replace(item.word, '______')}",
        "word": item.word,
    }
    get_stream_writer()(event)
    user_answer = interrupt(event)

    is_correct = user_answer.get("answer", "").strip().lower() == item.word.lower()
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

    next_index = state["review_index"] + 1
    if next_index < len(state["review_queue"]):
        return Command(update={"review_index": next_index}, goto="spaced_review")
    return Command(goto="reading")


def reading_session(state: dict) -> Command[Literal["writing_task"]]:
    """Loop: wait for user actions (explain_word, analyze_sentence, done_reading)."""
    _db.upsert_reading_start(date.today())

    while True:
        writer = get_stream_writer()
        awaiting_event = {
            "type": "awaiting_action",
            "article_full_text": state["today_article"].full_text if state["today_article"] else "",
            "highlight_indices": (
                state["today_article"].highlight_indices if state["today_article"] else []
            ),
            "user_level": state["user_profile"].level if state["user_profile"] else 5,
        }
        writer(awaiting_event)
        user_action = interrupt(awaiting_event)
        action_type = user_action.get("type")

        if action_type == "explain_word":
            word = user_action.get("word", "")
            if not word:
                writer({"type": "error", "message": "explain_word requires a 'word' field"})
                continue
            result = explain_word.invoke(
                {
                    "word": word,
                    "context": user_action.get("context", ""),
                    "level": state["user_profile"].level if state["user_profile"] else 5,
                }
            )
            if state["today_article"]:
                _db.upsert_vocab_item(
                    VocabItemCreate(
                        word=word,
                        context_sentence=user_action.get("context", ""),
                        source="reading_click",
                        next_review=date.today().isoformat(),
                        fsrs_state=new_card_state(),
                        article_id=state["today_article"].id,
                    )
                )
            writer({"type": "word_explanation", "result": result})

        elif action_type == "analyze_sentence":
            sentence = user_action.get("sentence", "")
            if not sentence:
                writer({"type": "error", "message": "analyze_sentence requires a 'sentence' field"})
                continue
            result = analyze_sentence.invoke({"sentence": sentence})
            writer({"type": "sentence_analysis", "result": result})

        elif action_type == "done_reading":
            break

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
    """Run AI feedback on the user's writing."""
    writer = get_stream_writer()
    profile = state["user_profile"]
    task = state["today_task"]
    user_text = state.get("user_writing", "")

    if not user_text or not task or not profile:
        writer({"type": "error", "message": "Missing writing or task context"})
        return {}

    feedback = run_feedback(
        user_text=user_text,
        task=task,
        user_goal=profile.goal,
        level=profile.level,
    )
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
            submitted_at=datetime.now(),
        )
        _db.save_writing_submission(sub)
        article_id = article.id if article else None
        for flag in feedback.chinglish_flags:
            _db.upsert_vocab_item(
                VocabItemCreate(
                    word=flag.original,
                    context_sentence=flag.original,
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

    return {"user_writing": None, "writing_feedback": None}
