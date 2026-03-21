from langchain_core.messages import HumanMessage, SystemMessage

from backend.llm import get_llm
from backend.models import ReflectHandoff, TutorHandoff

_SYSTEM_PROMPT = """你是一位资深英语教师，专注分析学生的学习模式。
根据今天课堂数据和历史观察，给出深度教学洞察。

规则：
- 不要重复 SQL 数据可以直接得出的结论（比如"分数是7"）
- 专注于数据看不出来的规律：错误背后的认知原因、动机模式、进步趋势
- teaching_insight 必须包含至少一个 SQL 无法得出的定性分析
- level_suggestion 基于近期写作质量，±1 为合理范围"""


async def run_reflect(
    handoff: TutorHandoff,
    weekly_stats: dict,
    observations: list[dict],
    insights_history: list[dict],
) -> ReflectHandoff:
    """Single LangChain call → ReflectHandoff. Uses qwen-plus (offline, no urgency)."""
    llm = get_llm("qwen-plus")
    structured = llm.with_structured_output(ReflectHandoff)

    context = f"""## 今天课堂数据
{handoff.model_dump_json(indent=2)}

## 本周结构化数据（来自 SQLite）
写作分数（近7条）: {weekly_stats['writing_scores']}
Chinglish 问题分布: {weekly_stats['chinglish_counts']}
词汇总量: {weekly_stats['vocab_mastered']}
话题分布（近14天）: {weekly_stats['topic_distribution']}

## Tutor 即时观察（近7天）
{observations if observations else "（暂无观察记录）"}

## 历史教学洞察（近14天）
{insights_history if insights_history else "（暂无历史洞察）"}

请生成 ReflectHandoff。date 字段填 {handoff.date}。
level_suggestion 参考现有 level={handoff.writing_score // 10 + 1}，
写作分 {handoff.writing_score}/10。"""

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=context),
    ]
    return await structured.ainvoke(messages)  # type: ignore[return-value]
