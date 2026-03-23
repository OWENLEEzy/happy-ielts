from unittest.mock import AsyncMock, patch

import pytest

from backend.general.notebooklm import NotebookLMClient


@pytest.mark.asyncio
async def test_create_notebook_parses_id():
    mock_output = '{"id": "abc123-def456", "title": "Test"}\n'
    with patch(
        "backend.general.notebooklm._run_cmd", new_callable=AsyncMock, return_value=mock_output
    ):
        client = NotebookLMClient()
        notebook_id = await client.create_notebook("Test")
    assert notebook_id == "abc123-def456"


@pytest.mark.asyncio
async def test_ask_returns_answer():
    mock_output = (
        '{"answer": "吉他有六根弦", "conversation_id": "x",'
        ' "turn_number": 1, "is_follow_up": false, "references": []}\n'
    )
    with patch(
        "backend.general.notebooklm._run_cmd", new_callable=AsyncMock, return_value=mock_output
    ):
        client = NotebookLMClient()
        answer = await client.ask("nb123", "吉他有几根弦？")
    assert "六根弦" in answer
