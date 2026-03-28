"""Tests for NotebookLMWrapper (Python API client, not CLI)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.general.notebooklm import NotebookLMWrapper


def _make_client_ctx(
    *,
    notebook_id: str = "nb-abc",
    research_statuses: list[str] | None = None,
    sources: list[dict] | None = None,
    chat_answer: str = "test answer",
) -> MagicMock:
    """Build a mock async context-manager client."""
    c = MagicMock()

    # notebooks.create → object with .id
    nb = MagicMock()
    nb.id = notebook_id
    c.notebooks.create = AsyncMock(return_value=nb)

    # research.start → task dict
    c.research.start = AsyncMock(return_value={"task_id": "t1"})

    # research.poll → cycle through statuses
    statuses = research_statuses or ["completed"]
    srcs = sources or [{"title": "Example", "url": "http://example.com"}]
    poll_results = [{"status": s, "sources": srcs if s == "completed" else []} for s in statuses]
    c.research.poll = AsyncMock(side_effect=poll_results)
    c.research.import_sources = AsyncMock(return_value=None)

    # sources.list → empty list by default (no pre-existing sources)
    c.sources.list = AsyncMock(return_value=[])

    # chat.ask → object with .answer
    ans = MagicMock()
    ans.answer = chat_answer
    c.chat.ask = AsyncMock(return_value=ans)

    return c


def _patch_client(c: MagicMock):
    """Patch _NLMClient.from_storage to return an async CM that yields c."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=c)
    cm.__aexit__ = AsyncMock(return_value=False)
    return patch(
        "backend.general.notebooklm._NLMClient.from_storage",
        return_value=cm,
    )


@pytest.mark.asyncio
async def test_create_notebook_returns_id():
    c = _make_client_ctx(notebook_id="abc123")
    with _patch_client(c):
        wrapper = NotebookLMWrapper()
        result = await wrapper.create_notebook("Test")
    assert result == "abc123"
    c.notebooks.create.assert_awaited_once_with("Test")


@pytest.mark.asyncio
async def test_ask_returns_answer():
    c = _make_client_ctx(chat_answer="吉他有六根弦")
    with _patch_client(c):
        wrapper = NotebookLMWrapper()
        answer = await wrapper.ask("nb123", "吉他有几根弦？")
    assert "六根弦" in answer


@pytest.mark.asyncio
async def test_ask_save_as_note_logs_warning(caplog):
    import logging

    c = _make_client_ctx(chat_answer="some answer")
    with _patch_client(c):
        wrapper = NotebookLMWrapper()
        with caplog.at_level(logging.WARNING, logger="backend.general.notebooklm"):
            await wrapper.ask("nb123", "question", save_as_note=True)
    assert "save_as_note=True" in caplog.text
    assert "not yet implemented" in caplog.text


@pytest.mark.asyncio
async def test_add_research_completed_imports_sources():
    c = _make_client_ctx(
        research_statuses=["completed"],
        sources=[{"title": "A", "url": "http://a.com"}, {"title": "B", "url": "http://b.com"}],
    )
    with _patch_client(c):
        wrapper = NotebookLMWrapper()
        count = await wrapper.add_research("nb1", "吉他学习路径")
    assert count == 2
    c.research.import_sources.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_research_terminal_status_exits_early():
    c = _make_client_ctx(research_statuses=["no_research"])
    with _patch_client(c):
        wrapper = NotebookLMWrapper()
        count = await wrapper.add_research("nb1", "query")
    # Should return 0 immediately on terminal non-completed status
    assert count == 0
    c.research.import_sources.assert_not_awaited()
