import logging
from datetime import date
from statistics import mean
from typing import Literal

from backend.database import get_db
from backend.models import DimensionState, GeneralStudentModel  # noqa: F401

_logger = logging.getLogger(__name__)


async def run_reflect(project_id: int) -> None:
    db = get_db()
    project = db.get_general_project(project_id)
    if not project or not project.learning_map:
        return

    sessions = db.get_project_sessions_recent(project_id, n=5)
    if not sessions:
        return

    chapter_scores: dict[str, list[float]] = {}
    for session in sessions:
        lesson = db.get_general_lesson(session["lesson_id"])
        if not lesson:
            continue
        if lesson.chapter >= len(project.learning_map.chapters):
            _logger.warning(
                "reflect: lesson %d chapter index %d out of range (map has %d chapters)",
                lesson.id,
                lesson.chapter,
                len(project.learning_map.chapters),
            )
            continue
        chapter_title = project.learning_map.chapters[lesson.chapter].title
        score = session.get("quiz_score", 0) / 100
        chapter_scores.setdefault(chapter_title, []).append(score)

    dimensions = {}
    for ch_title, scores in chapter_scores.items():
        # sessions are returned most-recent-first (DESC), so scores[0] is newest.
        if len(scores) > 1 and scores[0] > scores[-1]:
            trend: Literal["improving", "stable", "worsening"] = "improving"
        elif len(scores) > 1 and scores[0] < scores[-1]:
            trend = "worsening"
        else:
            trend = "stable"
        dimensions[ch_title] = DimensionState(
            mastery=mean(scores),
            sessions=len(scores),
            last_reviewed=date.today().isoformat(),
            trend=trend,
        )

    all_lessons = db.get_project_lessons(project_id)
    total_titles = {
        project.learning_map.chapters[ls.chapter].title
        for ls in all_lessons
        if ls.chapter < len(project.learning_map.chapters)
    }
    mastered = sum(1 for t in total_titles if dimensions.get(t) and dimensions[t].mastery >= 0.5)
    goal_progress = mastered / len(total_titles) if total_titles else 0.0

    existing = db.get_general_student_model_full(project_id)
    model = GeneralStudentModel(
        project_id=project_id,
        goal_outcome=project.goal_profile.goal_outcome if project.goal_profile else "",
        goal_progress=round(goal_progress, 3),
        dimensions=dimensions,
        fsrs_due=existing.fsrs_due if existing else [],
        updated=date.today().isoformat(),
    )
    db.save_general_student_model(project_id, model)

    weak = [name for name, d in dimensions.items() if d.mastery < 0.5]
    if weak:
        _logger.info("Reflect: weak dimensions for project %d: %s", project_id, weak)
        from backend.general.researcher import run_targeted_research

        for dim in weak:
            await run_targeted_research(project_id, dim)
