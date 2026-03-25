"""
创建「学习的本质」NotebookLM 研究笔记本。

用法：
    uv run python backend/scripts/setup_learning_science_notebook.py
"""

import asyncio
import os
import sys
from pathlib import Path

# 将 backend 目录加入 sys.path，以便直接复用 general/notebooklm.py
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))

# 加载 .env 文件（项目根目录）
_env_path = _REPO_ROOT / ".env"
if _env_path.exists():
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

# 代理设置：复用 notebooklm.py 中的逻辑（已在模块 import 时自动处理）
from general.notebooklm import NotebookLMWrapper  # noqa: E402

NOTEBOOK_TITLE = "学习的本质 — AI Agent 设计参考"

RESEARCH_QUERIES: list[tuple[str, str]] = [
    ("间隔重复与检索练习", "spaced repetition retrieval practice learning science evidence"),
    ("认知负荷理论", "cognitive load theory worked examples learning efficiency"),
    ("交错效应与可取困难", "interleaving effect desirable difficulties Bjork learning"),
    ("元认知与自主学习", "metacognition self-regulated learning strategies"),
    ("刻意练习与专家表现", "deliberate practice expert performance Ericsson"),
    ("反馈时机与形成性评估", "feedback timing formative assessment learning"),
    ("主动回忆与遗忘曲线", "active recall vs passive review forgetting curve Ebbinghaus"),
    ("成长型思维与学习坚持", "growth mindset motivation learning persistence Dweck"),
]

DOCS_DIR = _REPO_ROOT / "docs"
OUTPUT_FILE = DOCS_DIR / "learning_science_notebook.txt"


async def main() -> None:
    nlm = NotebookLMWrapper()

    print(f"正在创建 notebook：{NOTEBOOK_TITLE!r} …")
    notebook_id = await nlm.create_notebook(NOTEBOOK_TITLE)
    print(f"Notebook 创建成功：{notebook_id}\n")

    results: list[dict] = []

    for label, query in RESEARCH_QUERIES:
        print(f"[{label}] 开始 deep research …")
        print(f"  query: {query!r}")
        try:
            count = await nlm.add_research(notebook_id, query, mode="deep")
            status = "ok" if count > 0 else "0 sources"
        except Exception as exc:
            count = 0
            status = f"error: {exc}"
        results.append({"label": label, "query": query, "sources": count, "status": status})
        print(f"  => sources added: {count}  [{status}]\n")

    # 保存 notebook_id 到文件
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
    print(f"notebook_id 已保存至：{OUTPUT_FILE}")

    # 最终汇总
    total_sources = sum(r["sources"] for r in results)
    successful = sum(1 for r in results if r["sources"] > 0)
    print("\n========== 最终汇总 ==========")
    print(f"notebook_id : {notebook_id}")
    print(f"notebook 标题: {NOTEBOOK_TITLE}")
    print(f"研究方向总数  : {len(RESEARCH_QUERIES)}")
    print(f"成功添加 sources 的方向: {successful}/{len(RESEARCH_QUERIES)}")
    print(f"合计 sources  : {total_sources}")
    print("------------------------------")
    for r in results:
        mark = "✓" if r["sources"] > 0 else "✗"
        print(f"  {mark} [{r['label']}]  sources={r['sources']}  {r['status']}")
    print("==============================")

    if successful < 4:
        print("\n警告：成功方向不足 4 个，请检查网络/代理设置后重试。")
        sys.exit(1)
    else:
        print("\n完成。")


if __name__ == "__main__":
    asyncio.run(main())
