import asyncio
import logging
import random

from backend.database import get_db
from backend.general.notebooklm import get_nlm_client

_logger = logging.getLogger(__name__)


def _shuffle_quiz_options(quiz: list[dict]) -> list[dict]:
    """Randomize the position of answerOptions so the correct answer
    is not always at a fixed index (NLM tends to emit it first)."""
    result = []
    for q in quiz:
        opts = list(q.get("answerOptions", []))
        random.shuffle(opts)
        result.append({**q, "answerOptions": opts})
    return result


async def run_extractor(project_id: int) -> None:
    db = get_db()
    nlm = get_nlm_client()

    project = db.get_general_project(project_id)
    if not project or not project.learning_map or not project.notebook_id:
        _logger.error("Extractor: project %d missing map or notebook", project_id)
        return

    notebook_id = project.notebook_id
    goal_outcome = project.goal_profile.goal_outcome if project.goal_profile else ""

    for ch_idx, chapter in enumerate(project.learning_map.chapters):
        for ls_idx, lesson in enumerate(chapter.lessons):
            _logger.info("Extracting chapter=%d lesson=%d: %s", ch_idx, ls_idx, lesson.title)
            try:
                await nlm.ask(
                    notebook_id,
                    f"请详细解释「{lesson.title}」，结合具体例子，面向目标：{goal_outcome}",
                    save_as_note=True,
                )

                # Fix 1: Retry study_guide generation (max 2 retries, 5s delay)
                study_guide: str | None = None
                for attempt in range(3):
                    result = await nlm.generate_study_guide(
                        notebook_id,
                        append=f"只聚焦「{lesson.title}」，面向目标：{goal_outcome}。请用中文撰写完整的学习指南，包括概念解释、代码示例和实践要点。",
                    )
                    if isinstance(result, Exception):
                        if attempt < 2:
                            _logger.warning(
                                "Extractor: study_guide attempt %d failed: %s",
                                attempt + 1,
                                result,
                            )
                            await asyncio.sleep(5)
                        else:
                            study_guide = f"# {lesson.title}\n\n请向 AI 老师提问了解详情。"
                    else:
                        study_guide = result
                        break

                results = await asyncio.gather(
                    nlm.generate_quiz(notebook_id),
                    nlm.generate_flashcards(notebook_id),
                    return_exceptions=True,
                )
                quiz_r = results[0]
                quiz: list[dict] = quiz_r if not isinstance(quiz_r, Exception) else []  # type: ignore
                fc_r = results[1]
                flashcards: list[dict] = fc_r if not isinstance(fc_r, Exception) else []  # type: ignore

                db.upsert_general_lesson(
                    project_id=project_id,
                    chapter=ch_idx,
                    lesson=ls_idx,
                    title=lesson.title,
                    study_guide=study_guide or "",
                    quiz_json=_shuffle_quiz_options(quiz),
                    flashcards=flashcards,
                )

                # Fix 2: Warn when study_guide is degraded fallback content
                if study_guide and study_guide.startswith(f"# {lesson.title}\n\n请向"):
                    _logger.warning(
                        "Extractor: degraded study_guide (fallback) for project_id=%d ch=%d ls=%d",
                        project_id,
                        ch_idx,
                        ls_idx,
                    )
            except Exception as exc:
                _logger.error(
                    "Extractor: failed chapter=%d lesson=%d (%s): %s — continuing",
                    ch_idx,
                    ls_idx,
                    lesson.title,
                    exc,
                )

    db.update_general_project_status(project_id, "active")
    _logger.info("Extractor complete for project %d", project_id)


async def reextract_lesson(project_id: int, lesson_id: int) -> bool:
    """Re-extract study guide, quiz, and flashcards for a single lesson.

    Returns True on success, False if project/lesson not found.
    Used by the admin reextract endpoint to fix degraded (fallback) lessons.
    """
    db = get_db()
    nlm = get_nlm_client()

    project = db.get_general_project(project_id)
    if not project or not project.learning_map or not project.notebook_id:
        _logger.error("Reextract: project %d missing map or notebook", project_id)
        return False

    notebook_id = project.notebook_id
    goal_outcome = project.goal_profile.goal_outcome if project.goal_profile else ""

    # Find the lesson in the learning map by matching lesson_id
    lessons_flat = db.get_project_lessons(project_id)
    target = next((ls for ls in lessons_flat if ls.id == lesson_id), None)
    if not target:
        _logger.error("Reextract: lesson_id=%d not found in project %d", lesson_id, project_id)
        return False

    ch_idx = target.chapter
    ls_idx = target.lesson
    lesson_title = target.title

    _logger.info("Reextracting project=%d lesson_id=%d (%s)", project_id, lesson_id, lesson_title)

    await nlm.ask(
        notebook_id,
        f"请详细解释「{lesson_title}」，结合具体例子，面向目标：{goal_outcome}",
        save_as_note=True,
    )

    study_guide: str | None = None
    for attempt in range(3):
        result = await nlm.generate_study_guide(
            notebook_id,
            append=f"只聚焦「{lesson_title}」，面向目标：{goal_outcome}。请用中文撰写完整的学习指南，包括概念解释、代码示例和实践要点。",
        )
        if isinstance(result, Exception):
            if attempt < 2:
                _logger.warning("Reextract: study_guide attempt %d failed: %s", attempt + 1, result)
                await asyncio.sleep(5)
            else:
                study_guide = f"# {lesson_title}\n\n请向 AI 老师提问了解详情。"
        else:
            study_guide = result
            break

    reextract_results = await asyncio.gather(
        nlm.generate_quiz(notebook_id),
        nlm.generate_flashcards(notebook_id),
        return_exceptions=True,
    )
    quiz_r = reextract_results[0]
    quiz: list[dict] = quiz_r if not isinstance(quiz_r, Exception) else []  # type: ignore
    fc_r = reextract_results[1]
    flashcards: list[dict] = fc_r if not isinstance(fc_r, Exception) else []  # type: ignore

    db.upsert_general_lesson(
        project_id=project_id,
        chapter=ch_idx,
        lesson=ls_idx,
        title=lesson_title,
        study_guide=study_guide or "",
        quiz_json=quiz,
        flashcards=flashcards,
    )

    is_degraded = study_guide and study_guide.startswith(f"# {lesson_title}\n\n请向")
    if is_degraded:
        _logger.warning(
            "Reextract: study_guide still degraded after retries for lesson_id=%d", lesson_id
        )
    else:
        _logger.info("Reextract complete for lesson_id=%d", lesson_id)
    return not is_degraded
