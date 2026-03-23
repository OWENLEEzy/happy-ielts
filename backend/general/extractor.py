import asyncio
import logging

from backend.database import get_db
from backend.general.notebooklm import get_nlm_client

_logger = logging.getLogger(__name__)


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

            await nlm.ask(
                notebook_id,
                f"请详细解释「{lesson.title}」，结合具体例子，面向目标：{goal_outcome}",
                save_as_note=True,
            )

            study_guide, quiz, flashcards = await asyncio.gather(
                nlm.generate_study_guide(
                    notebook_id,
                    append=f"只聚焦「{lesson.title}」，面向目标：{goal_outcome}",
                ),
                nlm.generate_quiz(notebook_id),
                nlm.generate_flashcards(notebook_id),
                return_exceptions=True,
            )

            if isinstance(study_guide, Exception):
                study_guide = f"# {lesson.title}\n\n请向 AI 老师提问了解详情。"
            if isinstance(quiz, Exception):
                quiz = []
            if isinstance(flashcards, Exception):
                flashcards = []

            db.upsert_general_lesson(
                project_id=project_id,
                chapter=ch_idx,
                lesson=ls_idx,
                title=lesson.title,
                study_guide=study_guide,
                quiz_json=quiz,
                flashcards=flashcards,
            )

    db.update_general_project_status(project_id, "active")
    _logger.info("Extractor complete for project %d", project_id)
