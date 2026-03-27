"""
创建「学习的本质 Part 2」NotebookLM 研究笔记本（第二个，覆盖剩余 4 个方向）。

用法：
    uv run python backend/scripts/setup_learning_science_notebook2.py
"""

import asyncio
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))

_env_path = _REPO_ROOT / ".env"
if _env_path.exists():
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

from general.notebooklm import NotebookLMWrapper  # noqa: E402

NOTEBOOK_TITLE = "学习的本质 Part 2 — AI Agent 设计参考"
DOCS_DIR = _REPO_ROOT / "docs"
OUTPUT_FILE = DOCS_DIR / "learning_science_notebook2.txt"

INTER_QUERY_DELAY = 90
RETRY_DELAY = 180

RESEARCH_QUERIES: list[tuple[str, str]] = [
    ("刻意练习与专家表现", "deliberate practice expert performance Ericsson"),
    ("反馈时机与形成性评估", "feedback timing formative assessment learning"),
    ("主动回忆与遗忘曲线", "active recall vs passive review forgetting curve Ebbinghaus"),
    ("成长型思维与学习坚持", "growth mindset motivation learning persistence Dweck"),
]


def _load_existing() -> tuple[str | None, dict[str, int]]:
    if not OUTPUT_FILE.exists():
        return None, {}
    notebook_id = None
    done: dict[str, int] = {}
    current_label = None
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("notebook_id:"):
                notebook_id = line.split(":", 1)[1].strip()
            elif line.startswith("- label:"):
                current_label = line.split(":", 1)[1].strip()
            elif line.startswith("sources_added:") and current_label:
                count = int(line.split(":", 1)[1].strip())
                if count > 0:
                    done[current_label] = count
    return notebook_id, done


def _save_results(notebook_id: str, results: list[dict]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"notebook_id: {notebook_id}\n")
        f.write(f"title: {NOTEBOOK_TITLE}\n\n")
        f.write("research_results:\n")
        for r in results:
            f.write(f"  - label: {r['label']}\n")
            f.write(f"    query: {r['query']}\n")
            f.write(f"    sources_added: {r['sources']}\n")
            f.write(f"    status: {r['status']}\n")


async def _add_with_retry(nlm: NotebookLMWrapper, notebook_id: str, query: str) -> tuple[int, str]:
    for attempt, mode in enumerate(["deep", "fast"], 1):
        try:
            print(f"  attempt {attempt} (mode={mode}) …")
            count = await nlm.add_research(notebook_id, query, mode=mode)
            if count > 0:
                return count, "ok"
            print(f"  attempt {attempt} returned 0 sources, trying next mode…")
        except Exception as exc:
            print(f"  attempt {attempt} failed: {exc}")
            if attempt < 2:
                print(f"  waiting {RETRY_DELAY}s before retry…")
                await asyncio.sleep(RETRY_DELAY)
    return 0, "failed after 2 attempts"


async def main() -> None:
    nlm = NotebookLMWrapper()

    existing_id, already_done = _load_existing()

    if existing_id:
        notebook_id = existing_id
        print(f"断点续传：复用已有 notebook {notebook_id}")
        print(f"已完成方向：{list(already_done.keys()) or '无'}\n")
    else:
        print(f"创建新 notebook：{NOTEBOOK_TITLE!r} …")
        notebook_id = await nlm.create_notebook(NOTEBOOK_TITLE)
        print(f"创建成功：{notebook_id}\n")
        already_done = {}

    results: list[dict] = []
    for label, query in RESEARCH_QUERIES:
        if label in already_done:
            results.append(
                {
                    "label": label,
                    "query": query,
                    "sources": already_done[label],
                    "status": "ok (已有)",
                }
            )

    pending = [(label, query) for label, query in RESEARCH_QUERIES if label not in already_done]
    print(f"待处理方向：{len(pending)}/{len(RESEARCH_QUERIES)}\n")

    for idx, (label, query) in enumerate(pending):
        print(f"[{label}]")
        print(f"  query: {query!r}")
        count, status = await _add_with_retry(nlm, notebook_id, query)
        results.append({"label": label, "query": query, "sources": count, "status": status})
        print(f"  => sources: {count}  [{status}]")

        _save_results(notebook_id, results)

        if idx < len(pending) - 1:
            print(f"  降速等待 {INTER_QUERY_DELAY}s …\n")
            await asyncio.sleep(INTER_QUERY_DELAY)

    total = sum(r["sources"] for r in results)
    successful = sum(1 for r in results if r["sources"] > 0)
    print("\n========== 最终汇总 ==========")
    print(f"notebook_id : {notebook_id}")
    print(f"成功方向    : {successful}/{len(RESEARCH_QUERIES)}")
    print(f"合计 sources: {total}")
    for r in results:
        mark = "✓" if r["sources"] > 0 else "✗"
        print(f"  {mark} [{r['label']}] sources={r['sources']}  {r['status']}")
    print("==============================")
    print(f"\n完成。notebook_id 已保存至 {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
