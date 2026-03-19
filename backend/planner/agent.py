from datetime import date

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain_tavily import TavilySearch

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
"""

_planner: object | None = None  # Singleton to avoid leaking SQLite connections


def get_planner(checkpointer):
    global _planner
    if _planner is None:
        _planner = create_deep_agent(
            model=init_chat_model("anthropic:claude-haiku-4-5-20251001"),
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
    return _planner


def get_planner_config():
    return {"configurable": {"thread_id": f"planner-{date.today().isoformat()}"}}
