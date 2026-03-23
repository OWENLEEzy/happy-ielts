from deepagents import create_deep_agent
from langchain.tools import tool

from backend.database import get_db
from backend.llm import get_llm
from backend.models import LearningMap, UserGoalProfile

SKILL_ONBOARDING_PROMPT = """
你是一位学习顾问，正在帮用户规划一门关于 {topic} 的学习课程。

通过自然对话（不超过 8 轮）深入了解以下信息：
- 具体的学习目的（goal_outcome）：学完之后想能做什么？追问到足够具体的应用场景。
  例如从「想学吉他」追问到「想在朋友婚礼上弹一首《小幸运》」。
- 使用场景（context）：在什么情境下用到这个技能？
- 当前水平：通过对话自然判断，不要直接问「你几级」。
- 时间投入：每周能花多少小时？希望几周完成？
- 限制条件：有没有特别的约束（设备、预算、身体状况）？

收集完成后调用 save_goal_profile 工具保存，然后告知用户：
「好的，我已经了解你的目标了，我会帮你准备一份学习计划供你确认。」

语气：专业、温和、简洁。不要一次问太多问题，每次只问一个。
"""

ENGLISH_ONBOARDING_PROMPT = """
你是一位英语学习顾问，正在为用户做学习规划。

通过自然对话（不超过 6 轮）了解：
- 具体学习目标（goal_outcome）：英语学好后要做什么？追问到足够具体的场景。
  例如从「读英文文档」追问到「阅读 TypeScript 官方文档和技术 RFC」。
- 当前薄弱项：写作、阅读、词汇、还是全面提升？
- 请用户写 2-3 句英文（隐式判断水平，不要直接问级别）。
- 每周学习时长和希望多久见效。

收集完成后调用 save_goal_profile 工具保存。
"""


def make_save_goal_profile_tool(project_id: int):
    """Factory: returns a save_goal_profile tool that closes over project_id."""

    @tool
    def save_goal_profile(
        topic: str,
        motivation: str,
        goal_outcome: str,
        context: str,
        current_level: str,
        time_per_week: int,
        duration_weeks: int,
        constraints: list[str],
    ) -> str:
        """Save the user's learning goal profile to the database after the interview."""
        db = get_db()
        profile = UserGoalProfile(
            mode="skill",
            topic=topic,
            motivation=motivation,
            goal_outcome=goal_outcome,
            context=context,
            current_level=current_level,
            time_per_week=time_per_week,
            duration_weeks=duration_weeks,
            constraints=constraints,
        )
        db.update_general_project_goal_profile(project_id, profile)
        return f"Goal profile saved for project {project_id}: {goal_outcome}"

    return save_goal_profile


_onboarding_agents: dict[int, object] = {}


def get_onboarding_agent(checkpointer, project_id: int, topic: str, mode: str = "skill"):
    """Singleton per project_id."""
    if project_id not in _onboarding_agents:
        prompt = SKILL_ONBOARDING_PROMPT if mode == "skill" else ENGLISH_ONBOARDING_PROMPT
        _onboarding_agents[project_id] = create_deep_agent(
            model=get_llm(),
            tools=[make_save_goal_profile_tool(project_id)],
            checkpointer=checkpointer,
            system_prompt=prompt.format(topic=topic),
        )
    return _onboarding_agents[project_id]


def generate_draft_learning_map(profile: UserGoalProfile) -> LearningMap:
    """Use LLM to generate an initial learning map draft (no NLM, instant)."""
    llm = get_llm()
    chain = llm.with_structured_output(LearningMap)
    prompt = (
        f"为以下学习目标生成一份结构化学习地图：\n\n"
        f"目标：{profile.goal_outcome}\n"
        f"主题：{profile.topic}\n"
        f"场景：{profile.context}\n"
        f"当前水平：{profile.current_level}\n"
        f"每周时间：{profile.time_per_week} 小时\n"
        f"总周数：{profile.duration_weeks} 周\n\n"
        f"请生成 3-6 个章节，每章节 2-4 节课，每节课有明确的学习目标。"
    )
    return chain.invoke(prompt)  # type: ignore[return-value]
