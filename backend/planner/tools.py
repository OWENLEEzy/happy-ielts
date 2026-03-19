import asyncio
import concurrent.futures
import logging
from datetime import date
from typing import Literal

from langchain.tools import tool
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

try:
    from scrapling import Scraper  # type: ignore[attr-defined]
except (ImportError, AttributeError):
    Scraper = None  # type: ignore[assignment,misc]

from backend.database import Database
from backend.models import ArticleCreate, WritingTaskCreate

logger = logging.getLogger(__name__)

_llm = ChatAnthropic(model="claude-haiku-4-5-20251001")  # type: ignore[call-arg]
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
    """Playwright fallback for JS-rendered pages.

    Runs in a separate thread to avoid 'event loop already running' errors
    when called from within an async FastAPI/LangChain context.
    """

    async def _run() -> str:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url)
            content = await page.inner_text("body")
            await browser.close()
            return content

    def run_in_new_loop() -> str:
        return asyncio.run(_run())

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(run_in_new_loop).result()


@tool
def load_user_profile() -> dict[str, object]:
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
    try:
        return _playwright_scrape(url)
    except Exception as e:
        logger.error(f"Playwright fallback failed for {url}: {e}")
        raise RuntimeError(f"Could not scrape article: {url}")


@tool
def highlight_key_paragraphs(
    full_text: str, user_goal: str, interests: list[str]
) -> dict[str, object]:
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
    result: HighlightResult = _llm.with_structured_output(HighlightResult).invoke(  # type: ignore[assignment]
        HIGHLIGHT_PROMPT.format(
            paragraphs=numbered,
            goal=user_goal,
            interests=", ".join(interests),
        )
    )
    valid_indices = [i for i in result.highlight_indices if 0 <= i < len(paragraphs)]
    return {"highlight_indices": valid_indices, "article_logic": result.article_logic}


class ArticleContext(BaseModel):
    """Subset of article data needed to generate a writing task."""

    original_title: str = Field(description="Title of the scraped article")
    article_logic: Literal["compare", "cause_effect", "argumentation"] = Field(
        description="Underlying logical structure of the article"
    )


class ProfileContext(BaseModel):
    """Subset of user profile data needed to generate a writing task."""

    goal: str = Field(description="The user's learning goal")
    level: int = Field(ge=1, le=10, description="Proficiency level 1-10")
    writing_mode: Literal["professional", "ielts_task1", "ielts_task2"] = Field(
        default="professional",
        description="Preferred writing mode",
    )


@tool
def generate_writing_task(article: ArticleContext, profile: ProfileContext) -> dict[str, object]:
    """Generate a writing task based on the article context and user profile."""
    mode: str = profile.writing_mode

    prompt = f"""
Create a writing task for a {profile.level}/10 English learner.
Article logic: {article.article_logic}
User goal: {profile.goal}
Article title: {article.original_title}
Writing mode: {mode}

Fields to produce:
- mode: "{mode}" (or ielts_task1/ielts_task2 as appropriate)
- instruction: full task description referencing article topics (min 50 chars)
- min_words: 50 for professional, 150 for ielts
- article_id: 0  (placeholder, will be overwritten by save_daily_lesson)
"""
    result: WritingTaskCreate = _llm.with_structured_output(WritingTaskCreate).invoke(prompt)  # type: ignore[assignment]
    return result.model_dump()


@tool
def save_daily_lesson(article: ArticleCreate, task: WritingTaskCreate) -> str:
    """Save today's article and writing task to the database. Call as the final step."""
    article = article.model_copy(update={"date": date.today().isoformat()})
    article_id = _db.upsert_article(article)

    task = task.model_copy(update={"article_id": article_id})
    _db.upsert_writing_task(task)

    return f"Saved: '{article.original_title}'"
