"""Curriculum engine: article logic type sequencing and writing task promotion rules."""

from __future__ import annotations

LOGIC_SEQUENCE: list[str] = [
    "argumentation",
    "argumentation",
    "compare",
    "narrative",
    "argumentation",
    "problem_solution",
    "compare",
]


def next_logic_type(session_index: int) -> str:
    """Return the article logic type required for the given session index."""
    return LOGIC_SEQUENCE[session_index % len(LOGIC_SEQUENCE)]


def compute_current_task_type(writing_task_history: dict) -> str:
    """Determine appropriate writing task type based on performance history.

    Promotion chain: argumentation → compare
    Promotion rule: avg_score >= 7.5 with >= 3 submissions
    Demotion rule: avg_score < 6.0 with >= 2 submissions
    """
    arg_stats = writing_task_history.get("argumentation", {})
    cmp_stats = writing_task_history.get("compare", {})

    arg_count = arg_stats.get("count", 0)
    arg_avg = arg_stats.get("avg_score", 0.0)
    promoted = arg_count >= 3 and arg_avg >= 7.5

    if not promoted:
        return "argumentation"

    cmp_count = cmp_stats.get("count", 0)
    cmp_avg = cmp_stats.get("avg_score", 0.0)
    if cmp_count >= 2 and cmp_avg < 6.0:
        return "argumentation"

    return "compare"
