import logging

from backend.database import get_db
from backend.general.notebooklm import get_nlm_client
from backend.llm import get_llm
from backend.models import LearningChapter, LearningLesson, LearningMap, UserGoalProfile

_logger = logging.getLogger(__name__)

BUDGET = {"free": 50, "paid": 300}
MAX_ROUNDS = 7


async def run_researcher(project_id: int, profile: UserGoalProfile, draft_map: LearningMap) -> None:
    db = get_db()
    nlm = get_nlm_client()

    _project = db.get_general_project(project_id)
    if _project and _project.notebook_id:
        notebook_id = _project.notebook_id
        _logger.info(
            "Researcher: reusing existing notebook %s for project %d", notebook_id, project_id
        )
    else:
        notebook_id = await nlm.create_notebook(f"Learning: {profile.topic}")
        db.update_general_project_notebook(project_id, notebook_id)
    budget = BUDGET.get(_project.tier, 50) if _project else 50
    used = 0
    rounds = 0

    _logger.info("Researcher round 1: broad sweep for %s", profile.topic)
    added = await nlm.add_research(
        notebook_id,
        f"{profile.topic} 完整体系 核心概念 学习路径 for {profile.goal_outcome}",
        mode="deep",
    )
    used += added
    db.update_general_project_status(project_id, "researching")

    while rounds < MAX_ROUNDS:
        rounds += 1

        verdict = await nlm.ask(
            notebook_id,
            f"基于现有来源，关于「{profile.topic}」的学习地图（目标：{profile.goal_outcome}）"
            f"还缺哪些重要内容？如果已经完整，请回答 COMPLETE。否则列出具体缺失主题。",
        )
        _logger.info("Researcher round %d verdict: %s", rounds, verdict[:120])

        if "COMPLETE" in verdict:
            _logger.info("Researcher: COMPLETE after %d rounds", rounds)
            break

        if used >= budget:
            _logger.info("Researcher: budget exhausted (%d/%d)", used, budget)
            await nlm.ask(
                notebook_id, "已达来源上限，基于现有材料生成最佳学习地图", save_as_note=True
            )
            break

        gap_query = _extract_gap_query(verdict, profile)
        added = await nlm.add_research(notebook_id, gap_query, mode="deep")
        used += added
        _logger.info("Researcher: added %d sources for gap query", added)

    mind_map_raw = await nlm.generate_mind_map(notebook_id)
    final_map = _adapt_mind_map_to_profile(mind_map_raw, profile, draft_map)
    db.update_general_project_map(project_id, final_map, used)
    db.update_general_project_status(project_id, "extracting")
    _logger.info("Researcher complete. project=%d used=%d/%d", project_id, used, budget)


def _extract_gap_query(verdict: str, profile: UserGoalProfile) -> str:
    return f"{profile.topic} {verdict[:200]} 详细教程 实例"


def _adapt_mind_map_to_profile(
    mind_map_raw: dict, profile: UserGoalProfile, draft_map: LearningMap
) -> LearningMap:
    """Use LLM to convert NLM mind map JSON into our LearningMap schema."""
    llm = get_llm()
    chain = llm.with_structured_output(LearningMap)
    example = LearningMap(
        topic="示例主题",
        total_weeks=profile.duration_weeks,
        chapters=[
            LearningChapter(
                title="示例章节",
                lessons=[LearningLesson(title="示例课", objectives=["目标1"])],
            )
        ],
    )
    result = chain.invoke(
        f"将以下知识地图转换为学习路径（JSON 格式），字段名必须与示例完全一致。\n"
        f"字段示例（必须使用这些字段名）：{example.model_dump_json()}\n"
        f"目标是：{profile.goal_outcome}\n"
        f"每周 {profile.time_per_week} 小时，共 {profile.duration_weeks} 周。\n"
        f"知识地图：{str(mind_map_raw)[:2000]}\n"
        f"参考草稿：{draft_map.model_dump_json()}"
    )
    return result  # type: ignore[return-value]


async def run_targeted_research(project_id: int, chapter_title: str) -> None:
    """Add targeted deep research for a weak chapter."""
    db = get_db()
    nlm = get_nlm_client()
    project = db.get_general_project(project_id)
    if not project or not project.notebook_id:
        return
    query = f"{project.user_topic} {chapter_title} 进阶练习 常见问题 详细教程"
    added = await nlm.add_research(project.notebook_id, query, mode="deep")
    _logger.info("Targeted research: added %d sources for '%s'", added, chapter_title)
