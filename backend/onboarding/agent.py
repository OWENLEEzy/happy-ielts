from datetime import date

from deepagents import create_deep_agent
from langchain.tools import tool

from backend.database import get_db
from backend.llm import get_llm

_db = get_db()


@tool
def save_partial_profile(
    goal: str,
    interests: list[str],
    level: int,
) -> str:
    """Call ONCE, only after collecting all three fields through conversation: goal
    (specific use-case, not vague), interests (3-5 keywords), and level (inferred
    from the student's English writing sample). Do not call with estimated or
    incomplete values — partial data will break downstream lesson generation."""
    from backend.models import UserProfile

    try:
        profile = UserProfile(
            goal=goal,
            interests=interests,
            level=level,
            bandwidth_minutes=25,
            writing_mode="professional",
        )
        _db.upsert_user_profile(profile)
        return f"Saved profile for level-{level} learner with goal: {goal}"
    except Exception as e:
        return f"ERROR: Failed to save profile — {e}. Try again."


ONBOARDING_PROMPT = """
你是一位温和的语言学习顾问，正在为用户做入学评估。

目标是通过自然对话（不超过 6 轮）了解三件事：用户的具体学习目标（要追问到足够具体的应用场景，
例如从"读英文文档"追问到"TypeScript 官方文档和 RFC"）、3-5 个兴趣关键词（用于指导文章抓取），
以及英文水平（请用户写 2-3 句英文，通过语法错误频率和词汇复杂度隐式判断，不要直接问"你几级"）。

收集齐以上信息后调用 save_partial_profile 工具保存，然后告知用户：
"好的，马上为你选择每日时长和写作目标（最后两步由你在卡片上点选）。"

对话语气：专业、温和、简洁，不要过度热情。
"""


def create_onboarding_agent(checkpointer):
    return create_deep_agent(
        model=get_llm(),
        tools=[save_partial_profile],
        checkpointer=checkpointer,
        system_prompt=ONBOARDING_PROMPT,
    )


ONBOARDING_CONFIG = {"configurable": {"thread_id": f"onboarding-{date.today().isoformat()}"}}
