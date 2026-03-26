"""Student model: persistent JSON snapshot of the student's learning state.

File: ./student_model.json — overwritten after each session.
JSONL files (tutor-observations.jsonl, teaching-insights.jsonl) remain as raw event logs;
this file is the aggregated current-state snapshot.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import tempfile
import threading
from datetime import date, timedelta
from pathlib import Path

from backend.curriculum import compute_current_task_type, next_logic_type
from backend.models import ReflectHandoff

logger = logging.getLogger(__name__)

STUDENT_MODEL_PATH = Path("./student_model.json")
_model_lock: threading.Lock = threading.Lock()

_DEFAULT_MODEL: dict = {
    "updated": "",
    "levels": {"reading": 5, "writing": 5, "vocab": 5},
    "error_patterns": {},
    "topic_performance": {},
    "writing_task_history": {},
    "curriculum": {
        "phase": 1,
        "session_index": 0,
        "next_logic_type": "argumentation",
        "current_task_type": "argumentation",
    },
    "behavior": {
        "sessions_total": 0,
        "current_streak": 0,
        "completion_rate": 0.0,
    },
}


def read_student_model() -> dict:
    """Read student model from disk. Returns default structure if file not found."""
    if not STUDENT_MODEL_PATH.exists():
        return copy.deepcopy(_DEFAULT_MODEL)
    try:
        return json.loads(STUDENT_MODEL_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("student_model.json read error: %s — using default", e)
        return copy.deepcopy(_DEFAULT_MODEL)


def write_student_model(model: dict) -> None:
    """Atomically overwrite student_model.json (thread-safe, crash-safe)."""
    content = json.dumps(model, ensure_ascii=False, indent=2)
    with _model_lock:
        dir_ = STUDENT_MODEL_PATH.parent
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=dir_, delete=False, suffix=".tmp"
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        os.replace(tmp_path, STUDENT_MODEL_PATH)


def _compute_streak(session_dates: list[str]) -> int:
    """Count consecutive days with sessions, ending today or yesterday."""
    if not session_dates:
        return 0
    date_set = set(session_dates)
    today = date.today()
    # Try streak ending today
    streak = 0
    current = today
    while current.isoformat() in date_set:
        streak += 1
        current -= timedelta(days=1)
    if streak > 0:
        return streak
    # Try streak ending yesterday (gap today)
    current = today - timedelta(days=1)
    while current.isoformat() in date_set:
        streak += 1
        current -= timedelta(days=1)
    return streak


def _update_error_patterns(
    existing: dict, top_weaknesses: list[str], improving_areas: list[str]
) -> dict:
    """Merge Reflect output into error_patterns, updating counts and trends."""
    updated = {k: dict(v) for k, v in existing.items()}
    improving_set = set(improving_areas)

    for weakness in top_weaknesses:
        if weakness not in updated:
            updated[weakness] = {"total": 0, "trend": "stable"}
        entry = updated[weakness]
        entry["total"] = entry.get("total", 0) + 1
        entry["trend"] = "improving" if weakness in improving_set else "stable"

    for area in improving_areas:
        if area in updated and area not in top_weaknesses:
            updated[area]["trend"] = "improving"

    return updated


def update_student_model(reflect_handoff: ReflectHandoff, db) -> dict:
    """Merge Reflect output + DB aggregates → student_model.json. Returns updated model.

    Called by Orchestrator after run_reflect() completes. Zero new LLM calls.
    """
    model = read_student_model()

    # --- Levels ---
    levels = dict(model.get("levels", {"reading": 5, "writing": 5, "vocab": 5}))
    levels["writing"] = reflect_handoff.level_suggestion
    model["levels"] = levels

    # --- Error patterns (from Reflect qualitative output) ---
    model["error_patterns"] = _update_error_patterns(
        model.get("error_patterns", {}),
        reflect_handoff.top_weaknesses,
        reflect_handoff.improving_areas,
    )

    # --- Topic performance (SQL aggregation) ---
    try:
        model["topic_performance"] = db.query_topic_performance()
    except Exception as e:
        logger.warning("Failed to query topic_performance: %s", e)

    # --- Writing task history (SQL aggregation by article logic type) ---
    try:
        writing_task_history = db.query_writing_task_history()
        model["writing_task_history"] = writing_task_history
    except Exception as e:
        logger.warning("Failed to query writing_task_history: %s", e)
        writing_task_history = model.get("writing_task_history") or {}

    # --- Curriculum: session_index, next_logic_type, current_task_type ---
    sessions_total = 0
    try:
        sessions_total = db.count_sessions()
    except Exception as e:
        logger.warning("Failed to count sessions: %s", e)

    curriculum = dict(model.get("curriculum", {}))
    curriculum["session_index"] = sessions_total
    curriculum["next_logic_type"] = next_logic_type(sessions_total)
    curriculum["current_task_type"] = compute_current_task_type(writing_task_history)
    model["curriculum"] = curriculum

    # --- Behavior ---
    behavior = dict(model.get("behavior", {}))
    behavior["sessions_total"] = sessions_total
    try:
        session_dates = db.query_session_dates()
        behavior["current_streak"] = _compute_streak(session_dates)
        articles_total = db.count_articles()
        behavior["completion_rate"] = (
            round(min(1.0, sessions_total / articles_total), 2) if articles_total > 0 else 0.0
        )
    except Exception as e:
        logger.warning("Failed to compute behavior stats: %s", e)
    model["behavior"] = behavior

    model["updated"] = date.today().isoformat()
    write_student_model(model)
    logger.info(
        "student_model.json updated: levels=%s, session_index=%d, next_logic=%s",
        levels,
        sessions_total,
        curriculum["next_logic_type"],
    )
    return model
