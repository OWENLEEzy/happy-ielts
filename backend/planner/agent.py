from datetime import date

from deepagents import create_deep_agent
from langchain_tavily import TavilySearch

from backend.llm import get_llm
from backend.models import ReflectHandoff
from backend.planner.tools import (
    generate_writing_task,
    highlight_key_paragraphs,
    load_user_profile,
    save_daily_lesson,
    scrape_article,
)

search_articles = TavilySearch(max_results=3)

PLANNER_SYSTEM_PROMPT = """
你是一个语言学习内容策划师。
根据用户的兴趣和职业目标，每天为他选择一篇真实的英文文章，
标注最核心的 3-5 个段落（用于前端高亮深读），识别文章底层逻辑类型，
并生成一个针对其目标的微型写作任务。
优先选择时效性强、与用户当前项目直接相关的内容。

完成目标：读取用户画像 → 搜索并抓取相关文章 → 标注核心段落和逻辑类型 →
生成写作任务 → 调用 save_daily_lesson 存库（必须最后调用）。

搜索时优先选择以下可抓取的来源：arxiv.org、hacker news（news.ycombinator.com）、dev.to、
blog.openai.com、anthropic.com/research、simonwillison.net、eugeneyan.com。
严格避免：medium.com（反爬）、substack.com（JS渲染）、technologyreview.com、wsj.com（付费墙）。
如果 scrape_article 返回错误，换一篇不同来源的文章重试，最多重试 2 次。
如果 3 篇文章都抓取失败，使用搜索结果的摘要作为文章内容继续后续步骤。
"""

_REFLECT_CONTEXT_TEMPLATE = """

## 教研反思结果（来自 Reflect Agent）
本次备课请结合以下教学分析：

**学生当前水平推荐：** Level {level}
**主要弱点（优先出针对性题目）：** {weaknesses}
**进步中的领域（可适当强化）：** {improving}
**话题方向推荐：** {topic}
**写作任务风格推荐：** {task_style}
**教学洞察（参考，不必逐字体现）：** {insight}
"""


def create_deep_agent_planner(
    checkpointer, reflect_handoff: ReflectHandoff | None = None
) -> object:
    """Create a fresh planner agent. Optionally inject ReflectHandoff context."""
    system_prompt = PLANNER_SYSTEM_PROMPT

    if reflect_handoff is not None:
        context = _REFLECT_CONTEXT_TEMPLATE.format(
            level=reflect_handoff.level_suggestion,
            weaknesses=", ".join(reflect_handoff.top_weaknesses) or "暂无",
            improving=", ".join(reflect_handoff.improving_areas) or "暂无",
            topic=reflect_handoff.topic_recommendation,
            task_style=reflect_handoff.task_recommendation,
            insight=reflect_handoff.teaching_insight,
        )
        system_prompt = PLANNER_SYSTEM_PROMPT + context

    return create_deep_agent(
        model=get_llm("qwen-max"),  # Offline pre-generation: use best model
        tools=[
            load_user_profile,
            search_articles,
            scrape_article,
            highlight_key_paragraphs,
            generate_writing_task,
            save_daily_lesson,
        ],
        system_prompt=system_prompt,
        checkpointer=checkpointer,
    )


def get_planner_config(suffix: str = "") -> dict:
    return {
        "configurable": {"thread_id": f"planner-{date.today().isoformat()}{suffix}"},
        "recursion_limit": 40,
    }
