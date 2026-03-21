from datetime import date

from deepagents import create_deep_agent
from langchain_tavily import TavilySearch

from backend.llm import get_llm
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

_planner: object | None = None  # Singleton to avoid leaking SQLite connections


def create_deep_agent_planner(checkpointer) -> object:
    """Create a fresh planner agent (for thread-isolated runs)."""
    return create_deep_agent(
        model=get_llm(),
        tools=[
            load_user_profile,
            search_articles,
            scrape_article,
            highlight_key_paragraphs,
            generate_writing_task,
            save_daily_lesson,
        ],
        system_prompt=PLANNER_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )


def get_planner(checkpointer):
    global _planner
    if _planner is None:
        _planner = create_deep_agent_planner(checkpointer)
    return _planner


def get_planner_config(suffix: str = "") -> dict:
    return {
        "configurable": {"thread_id": f"planner-{date.today().isoformat()}{suffix}"},
        "recursion_limit": 40,
    }
