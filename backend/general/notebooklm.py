import asyncio
import json
import logging
import os
import tempfile

from notebooklm import NotebookLMClient as _NLMClient

_logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 3
RETRY_DELAY_S = 10
RESEARCH_TIMEOUT_S = 1800
RESEARCH_POLL_INTERVAL_S = 15


def _client():
    """Return the coroutine from from_storage(). Await it to get an async context manager.

    Usage: ``async with (await _client()) as c:``
    """
    return _NLMClient.from_storage()


class NotebookLMWrapper:
    """Async wrapper around the notebooklm Python API."""

    async def create_notebook(self, title: str) -> str:
        async with await _client() as c:
            nb = await c.notebooks.create(title)
            return nb.id

    async def add_research(self, notebook_id: str, query: str, mode: str = "deep") -> int:
        """Start research, wait for completion, import all sources. Returns count added."""
        async with await _client() as c:
            task = await c.research.start(notebook_id, query, source="web", mode=mode)
            if not task:
                _logger.warning("Research start returned no task for notebook %s", notebook_id)
                return 0

            task_id = task["task_id"]
            loop = asyncio.get_running_loop()
            deadline = loop.time() + RESEARCH_TIMEOUT_S

            while loop.time() < deadline:
                result = await c.research.poll(notebook_id)
                status = result["status"]
                if status == "completed":
                    sources = result.get("sources", [])
                    if sources:
                        await c.research.import_sources(notebook_id, task_id, sources)
                    return len(sources)
                if status not in ("in_progress", "pending"):
                    _logger.warning(
                        "Research for notebook %s ended with terminal status %r",
                        notebook_id,
                        status,
                    )
                    return 0
                await asyncio.sleep(RESEARCH_POLL_INTERVAL_S)

            _logger.warning("Research timed out for notebook %s", notebook_id)
            return 0

    async def ask(self, notebook_id: str, question: str, save_as_note: bool = False) -> str:
        if save_as_note:
            _logger.warning(
                "ask(save_as_note=True) is not yet implemented with the Python API client; "
                "the answer will not be persisted as a notebook note."
            )
        for attempt in range(RETRY_ATTEMPTS):
            try:
                async with await _client() as c:
                    result = await c.chat.ask(notebook_id, question)
                    return result.answer
            except Exception as e:
                if attempt == RETRY_ATTEMPTS - 1:
                    raise
                _logger.warning("ask attempt %d failed: %s", attempt + 1, e)
                await asyncio.sleep(RETRY_DELAY_S)
        return ""

    async def generate_mind_map(self, notebook_id: str) -> dict:
        async with await _client() as c:
            result = await c.artifacts.generate_mind_map(notebook_id)
            return result.get("mind_map") or {}

    async def generate_study_guide(self, notebook_id: str, append: str = "") -> str:
        async with await _client() as c:
            status = await c.artifacts.generate_study_guide(
                notebook_id, extra_instructions=append or None
            )
            await c.artifacts.wait_for_completion(notebook_id, status.task_id)
            with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
                tmp_path = f.name
            try:
                await c.artifacts.download_report(notebook_id, tmp_path, artifact_id=status.task_id)
                with open(tmp_path, encoding="utf-8") as f:
                    return f.read()
            finally:
                os.unlink(tmp_path)

    async def generate_quiz(self, notebook_id: str) -> list[dict]:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                async with await _client() as c:
                    status = await c.artifacts.generate_quiz(notebook_id)
                    await c.artifacts.wait_for_completion(notebook_id, status.task_id)
                    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                        tmp_path = f.name
                    try:
                        await c.artifacts.download_quiz(
                            notebook_id, tmp_path, artifact_id=status.task_id
                        )
                        with open(tmp_path, encoding="utf-8") as f:
                            return json.load(f)
                    finally:
                        os.unlink(tmp_path)
            except Exception as e:
                if attempt == RETRY_ATTEMPTS - 1:
                    _logger.warning("quiz generation failed after retries: %s", e)
                    return []
                await asyncio.sleep(RETRY_DELAY_S)
        return []

    async def generate_flashcards(self, notebook_id: str) -> list[dict]:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                async with await _client() as c:
                    status = await c.artifacts.generate_flashcards(notebook_id)
                    await c.artifacts.wait_for_completion(notebook_id, status.task_id)
                    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                        tmp_path = f.name
                    try:
                        await c.artifacts.download_flashcards(
                            notebook_id, tmp_path, artifact_id=status.task_id
                        )
                        with open(tmp_path, encoding="utf-8") as f:
                            return json.load(f)
                    finally:
                        os.unlink(tmp_path)
            except Exception as e:
                if attempt == RETRY_ATTEMPTS - 1:
                    _logger.warning("flashcards generation failed after retries: %s", e)
                    return []
                await asyncio.sleep(RETRY_DELAY_S)
        return []


_nlm_client: NotebookLMWrapper | None = None


def get_nlm_client() -> NotebookLMWrapper:
    global _nlm_client
    if _nlm_client is None:
        _nlm_client = NotebookLMWrapper()
    return _nlm_client
