"""
向「学习的本质 Part 2」notebook 提问，获取 AI 学习 Agent 设计 insights。

用法：
    uv run python backend/scripts/ask_learning_science2.py
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

NOTEBOOK2_ID = "c55513e3-24f0-4656-b640-b00e38f46bf7"

QUESTIONS = [
    (
        "刻意练习 → Agent 设计",
        "根据刻意练习（Deliberate Practice）和专家表现研究，"
        "AI 语言学习 Agent 应该如何设计练习任务？"
        "刻意练习的关键要素是什么（专注度、即时反馈、走出舒适区）？"
        "Agent 应该如何判断学生什么时候需要更难的挑战？",
    ),
    (
        "主动回忆 vs 被动复习",
        "主动回忆（Active Recall）和遗忘曲线（Forgetting Curve）研究的核心结论是什么？"
        "Ebbinghaus 的研究如何指导 AI Agent 安排复习节奏？"
        "AI Agent 如何设计练习来最大化主动回忆效果？",
    ),
    (
        "成长型思维 → 挫折处理",
        "成长型思维（Growth Mindset）研究对 AI 学习 Agent 的对话设计有什么启示？"
        "当学生连续答错、想放弃时，Agent 应该说什么、做什么？"
        "给出 3-5 个具体的反馈话术模板，帮助学生建立成长型思维而不是固定型思维。",
    ),
    (
        "反馈时机的精细规则",
        "形成性评估（Formative Assessment）和反馈时机研究，"
        "对 AI Agent 的具体反馈设计有什么精细指导？"
        "什么情况下用即时反馈，什么情况下用延迟反馈？"
        "反馈的内容应该包含哪些要素才能促进深度学习而不只是纠错？",
    ),
]


async def main() -> None:
    nlm = NotebookLMWrapper()
    notebook_id = NOTEBOOK2_ID

    print(f"Notebook 2: {notebook_id}")
    print("=" * 60)

    for label, question in QUESTIONS:
        print(f"\n【{label}】")
        print(f"Q: {question}\n")
        try:
            answer = await nlm.ask(notebook_id, question)
            print(f"A: {answer}")
        except Exception as e:
            print(f"ERROR: {e}")
        print("-" * 60)
        await asyncio.sleep(5)

    print("\n\n===== 完成 =====")


if __name__ == "__main__":
    asyncio.run(main())
