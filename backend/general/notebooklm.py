import asyncio
import json
import logging
import os
import tempfile

import httpx as _httpx
import notebooklm._core as _nlm_core
from langchain.tools import tool
from notebooklm import NotebookLMClient as _NLMClient

# httpx + anyio 走 HTTP CONNECT 代理时 TLS 握手会失败，socks5 没有这个问题。
# 如果 all_proxy 是 socks5，强制覆盖 https_proxy。
_socks5: str = os.environ.get("all_proxy") or os.environ.get("ALL_PROXY") or ""
_http_proxy: str = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY") or ""
if _socks5.startswith("socks5://") and _http_proxy.startswith("http://"):
    os.environ["https_proxy"] = _socks5
    os.environ["HTTPS_PROXY"] = _socks5

# IMPORT_RESEARCH 是批量导入操作，默认 30s 超时不够。
# Python 函数默认参数在定义时固定，直接 patch Core.open() 让 AsyncClient 用 120s。
_original_core_open = _nlm_core.ClientCore.open


async def _patched_core_open(self: _nlm_core.ClientCore) -> None:
    await _original_core_open(self)
    if self._http_client:
        self._http_client.timeout = _httpx.Timeout(120.0)


_nlm_core.ClientCore.open = _patched_core_open  # type: ignore[method-assign]

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
                result = None
                for poll_attempt in range(3):
                    try:
                        result = await c.research.poll(notebook_id)
                        break
                    except Exception as poll_exc:
                        if poll_attempt == 2:
                            raise
                        _logger.warning(
                            "poll attempt %d failed: %s — retrying", poll_attempt + 1, poll_exc
                        )
                        await asyncio.sleep(RETRY_DELAY_S)
                if result is None:
                    await asyncio.sleep(RESEARCH_POLL_INTERVAL_S)
                    continue
                status = result["status"]
                if status == "completed":
                    sources = result.get("sources", [])
                    if sources:
                        existing = await c.sources.list(notebook_id)
                        existing_titles = {getattr(s, "title", "") or "" for s in existing}
                        new_sources = [
                            s for s in sources if (s.get("title") or "") not in existing_titles
                        ]
                        skipped = len(sources) - len(new_sources)
                        if skipped:
                            _logger.info(
                                "add_research: skipped %d already-present sources", skipped
                            )
                        if new_sources:
                            # Batch import to avoid RPC timeout on large source lists
                            _BATCH = 5
                            imported = 0
                            for i in range(0, len(new_sources), _BATCH):
                                batch = new_sources[i : i + _BATCH]
                                try:
                                    await c.research.import_sources(notebook_id, task_id, batch)
                                    imported += len(batch)
                                except Exception as imp_exc:
                                    _logger.warning(
                                        "add_research: batch %d import failed: %s",
                                        i // _BATCH,
                                        imp_exc,
                                    )
                                if i + _BATCH < len(new_sources):
                                    await asyncio.sleep(3)
                            return imported
                    return 0
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
                            data = json.load(f)
                        return data.get("questions", data) if isinstance(data, dict) else data
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
                            data = json.load(f)
                        return data.get("cards", data) if isinstance(data, dict) else data
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


def make_ask_notebook_tool(notebook_id: str):
    """Factory: returns an ask_notebook tool that closes over notebook_id.

    Usage (in a DeepAgent):
        agent = create_deep_agent(tools=[make_ask_notebook_tool(project["notebook_id"]), ...])
    """
    nlm = get_nlm_client()

    @tool
    async def ask_notebook(question: str) -> str:
        """ALWAYS use this tool when the user asks ANY question about the learning topic —
        concept explanations, "why does X work", "what is Y", factual lookups, or anything
        that requires accurate domain knowledge. Returns answers grounded in the notebook's
        curated sources. Never answer topic questions from memory alone; use this tool to
        avoid hallucination."""
        try:
            return await nlm.ask(notebook_id, question)
        except Exception as e:
            return (
                f"ERROR: Failed to query notebook — {e}. Try rephrasing the question or try again."
            )

    return ask_notebook
