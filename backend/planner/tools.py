import asyncio
import json
import logging
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field
from langchain.tools import tool
from langchain_anthropic import ChatAnthropic
try:
    from scrapling import Scraper  # type: ignore[attr-defined]
except (ImportError, AttributeError):
    Scraper = None  # type: ignore[assignment,misc]

from backend.database import Database
from backend.models import ArticleCreate, WritingTaskCreate

logger = logging.getLogger(__name__)

_llm = ChatAnthropic(model="claude-haiku-4-5-20251001")
_db = Database()

HIGHLIGHT_PROMPT = """
You are a language learning content curator for professional English learners.

Given an article split into numbered paragraphs, identify:
1. The 3-5 most valuable paragraphs for deep reading (highlight_indices)
2. The article's underlying logical structure (article_logic)

PARAGRAPHS:
{paragraphs}

LEARNER PROFILE:
- Goal: {goal}
- Interests: {interests}

SELECTION CRITERIA for highlight_indices:
- Paragraphs that directly serve the learner's goal
- Paragraphs with the highest density of professional vocabulary or advanced sentence structures
- The paragraph that contains the core argument or key insight
- Paragraphs with strong collocations worth learning
- Avoid: introductory boilerplate, conclusion summaries, promotional content

ARTICLE LOGIC DEFINITIONS:
- compare: article compares two or more approaches, technologies, or viewpoints
- cause_effect: article explains why something happened or what results from an action
- argumentation: article makes a claim and defends it with evidence

Return ONLY the structured output. Do not explain your choices.
"""


def _playwright_scrape(url: str) -> str:
    """Playwright fallback for JS-rendered pages."""
    async def _run():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url)
            content = await page.inner_text("body")
            await browser.close()
            return content
    return asyncio.run(_run())


@tool
def load_user_profile() -> dict:
    """Load the user's profile from the database."""
    profile = _db.get_user_profile()
    if profile is None:
        return {"error": "No user profile found. Run onboarding first."}
    return profile.model_dump()


@tool
def scrape_article(url: str) -> str:
    """Scrape the full text of an article. Falls back to Playwright if Scrapling fails."""
    try:
        if Scraper is None:
            raise ImportError("Scraper not available in this scrapling version")
        scraper = Scraper(auto_match=True)
        page = scraper.get(url)
        return page.get_best_text(auto_filter=True)
    except Exception as e:
        logger.warning(f"Scrapling failed for {url}: {e}. Trying Playwright.")
        return _playwright_scrape(url)


@tool
def highlight_key_paragraphs(full_text: str, user_goal: str, interests: list[str]) -> dict:
    """Identify 3-5 core paragraphs and article logic type for a language learner."""
    class HighlightResult(BaseModel):
        highlight_indices: list[int] = Field(
            description="0-based indices of 3-5 core paragraphs",
            min_length=3,
            max_length=5,
        )
        article_logic: Literal["compare", "cause_effect", "argumentation"] = Field(
            description="Underlying logical structure of the article"
        )

    paragraphs = full_text.split("\n\n")
    numbered = "\n\n".join(f"[{i}] {p}" for i, p in enumerate(paragraphs))
    result = (
        _llm.with_structured_output(HighlightResult)
        .invoke(HIGHLIGHT_PROMPT.format(
            paragraphs=numbered,
            goal=user_goal,
            interests=", ".join(interests),
        ))
    )
    valid_indices = [i for i in result.highlight_indices if 0 <= i < len(paragraphs)]
    return {"highlight_indices": valid_indices, "article_logic": result.article_logic}


@tool
def generate_writing_task(article_json: str, profile_json: str) -> dict:
    """Generate a writing task based on the article and user profile."""
    article = json.loads(article_json)
    profile = json.loads(profile_json)

    mode = profile.get("writing_mode", "professional")
    if mode == "both":
        import random
        mode = random.choice(["professional", "ielts_task2"])

    prompt = f"""
Create a writing task for a {profile['level']}/10 English learner.
Article logic: {article['article_logic']}
User goal: {profile['goal']}
Article title: {article['original_title']}
Writing mode: {mode}

Fields to produce:
- mode: "{mode}" (or ielts_task1/ielts_task2 as appropriate)
- instruction: full task description referencing article topics (min 50 chars)
- min_words: 50 for professional, 150 for ielts
- article_id: 0  (placeholder, will be overwritten by save_daily_lesson)
"""
    result = _llm.with_structured_output(WritingTaskCreate).invoke(prompt)
    return result.model_dump()


@tool
def save_daily_lesson(article: ArticleCreate, task: WritingTaskCreate) -> str:
    """Save today's article and writing task to the database. Call as the final step."""
    article = article.model_copy(update={"date": date.today().isoformat()})
    article_id = _db.upsert_article(article)

    task = task.model_copy(update={"article_id": article_id})
    _db.upsert_writing_task(task)

    return f"Saved: '{article.original_title}'"
