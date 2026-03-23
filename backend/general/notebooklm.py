import asyncio
import json
import logging

_logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 3
RETRY_DELAY_S = 10


async def _run_cmd(args: list[str]) -> str:
    """Run a notebooklm CLI command, return stdout."""
    proc = await asyncio.create_subprocess_exec(
        "notebooklm",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"notebooklm {' '.join(args)} failed: {stderr.decode()}")
    return stdout.decode()


class NotebookLMClient:
    """Thin async wrapper around the notebooklm-py CLI."""

    async def create_notebook(self, title: str) -> str:
        out = await _run_cmd(["create", title, "--json"])
        return json.loads(out)["id"]

    async def add_research(self, notebook_id: str, query: str, mode: str = "deep") -> int:
        """Start deep research; wait and import all sources. Returns count added."""
        await _run_cmd(
            [
                "source",
                "add-research",
                query,
                "--notebook",
                notebook_id,
                "--mode",
                mode,
                "--no-wait",
            ]
        )
        out = await _run_cmd(
            ["research", "wait", "-n", notebook_id, "--import-all", "--timeout", "1800"]
        )
        try:
            data = json.loads(out)
            return data.get("imported", 0)
        except Exception:
            return 0

    async def ask(self, notebook_id: str, question: str, save_as_note: bool = False) -> str:
        args = ["ask", question, "--notebook", notebook_id, "--json"]
        if save_as_note:
            args.append("--save-as-note")
        for attempt in range(RETRY_ATTEMPTS):
            try:
                out = await _run_cmd(args)
                return json.loads(out)["answer"]
            except Exception as e:
                if attempt == RETRY_ATTEMPTS - 1:
                    raise
                _logger.warning("notebooklm ask attempt %d failed: %s", attempt + 1, e)
                await asyncio.sleep(RETRY_DELAY_S)
        return ""

    async def generate_mind_map(self, notebook_id: str) -> dict:
        await _run_cmd(["generate", "mind-map", "--notebook", notebook_id])
        await _run_cmd(["download", "mind-map", "/tmp/mindmap.json", "--notebook", notebook_id])
        with open("/tmp/mindmap.json") as f:
            return json.load(f)

    async def generate_study_guide(self, notebook_id: str, append: str = "") -> str:
        args = ["generate", "report", "--format", "study-guide", "--notebook", notebook_id]
        if append:
            args += ["--append", append]
        await _run_cmd(args)
        await _run_cmd(["download", "report", "/tmp/guide.md", "--notebook", notebook_id])
        with open("/tmp/guide.md") as f:
            return f.read()

    async def generate_quiz(self, notebook_id: str) -> list[dict]:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                await _run_cmd(["generate", "quiz", "--notebook", notebook_id])
                await _run_cmd(
                    [
                        "download",
                        "quiz",
                        "/tmp/quiz.json",
                        "--notebook",
                        notebook_id,
                        "--format",
                        "json",
                    ]
                )
                with open("/tmp/quiz.json") as f:
                    return json.load(f)
            except Exception as e:
                if attempt == RETRY_ATTEMPTS - 1:
                    _logger.warning("quiz generation failed after retries: %s", e)
                    return []
                await asyncio.sleep(RETRY_DELAY_S)
        return []

    async def generate_flashcards(self, notebook_id: str) -> list[dict]:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                await _run_cmd(["generate", "flashcards", "--notebook", notebook_id])
                await _run_cmd(
                    [
                        "download",
                        "flashcards",
                        "/tmp/flashcards.json",
                        "--notebook",
                        notebook_id,
                        "--format",
                        "json",
                    ]
                )
                with open("/tmp/flashcards.json") as f:
                    return json.load(f)
            except Exception as e:
                if attempt == RETRY_ATTEMPTS - 1:
                    _logger.warning("flashcards generation failed after retries: %s", e)
                    return []
                await asyncio.sleep(RETRY_DELAY_S)
        return []


_nlm_client: NotebookLMClient | None = None


def get_nlm_client() -> NotebookLMClient:
    global _nlm_client
    if _nlm_client is None:
        _nlm_client = NotebookLMClient()
    return _nlm_client
