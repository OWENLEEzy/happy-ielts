"""
向「学习的本质」notebook 提问，获取 AI 学习 Agent 设计 insights。

用法：
    uv run python backend/scripts/ask_learning_science.py
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

NOTEBOOK1_ID = "a408b722-5221-434c-b180-48686749662b"

QUESTIONS = [
    (
        "原则总结",
        "基于间隔重复、认知负荷、交错效应和元认知的研究证据，"
        "为 AI 语言学习 Agent 提炼 6 条最核心的课程设计原则，"
        "每条原则给出 1-2 句话的实践指导。",
    ),
    (
        "间隔复习节奏",
        "间隔重复（Spaced Repetition）的最优时间间隔研究结论是什么？"
        "AI Agent 应该如何根据学生表现动态调整复习频率和难度？",
    ),
    (
        "认知负荷控制",
        "认知负荷理论对 AI 学习 Agent 的内容量、题目难度设计有什么具体指导？"
        "一次学习单元应该包含多少新概念？如何设计「工作样例」(worked examples) 效果最好？",
    ),
    (
        "测验与反馈设计",
        "检索练习（Retrieval Practice）作为学习手段比重读效果好多少？"
        "测验后的反馈应该立即给出还是延迟给出？AI Agent 的 quiz 模块应该如何设计？",
    ),
    (
        "元认知激活",
        "元认知训练在 AI 辅导场景中如何实现？"
        "Agent 应该问学生哪类问题来激活元认知、促进自我调节学习？"
        "给出 3-5 个具体的提问模板。",
    ),
    (
        "交错与困难",
        "交错效应（Interleaving）和可取困难（Desirable Difficulties）理论，"
        "对 AI Agent 的题目排序、主题切换频率有什么实践建议？"
        "学生觉得难的时候应该降低难度还是坚持？",
    ),
]


async def main() -> None:
    nlm = NotebookLMWrapper()
    notebook_id = NOTEBOOK1_ID

    print(f"Notebook: {notebook_id}")
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
        # 避免过快触发 rate limit
        await asyncio.sleep(5)

    print("\n\n===== 完成 =====")


if __name__ == "__main__":
    asyncio.run(main())
