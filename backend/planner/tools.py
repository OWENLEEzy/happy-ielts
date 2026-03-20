import logging
from datetime import date
from functools import lru_cache
from typing import Literal

from langchain.tools import tool
from pydantic import BaseModel, Field

try:
    from scrapling import Scraper  # type: ignore[attr-defined]
except (ImportError, AttributeError):
    Scraper = None  # type: ignore[assignment,misc]

from backend.database import get_db
from backend.llm import get_llm
from backend.models import ArticleCreate, WritingTaskCreate
from backend.utils import parse_json

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_llm():
    return get_llm()


_db = get_db()


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

Return ONLY a JSON object with no prose, no markdown fences. Schema:
{{"highlight_indices": [<0-based int>, <0-based int>, <0-based int>],
"article_logic": "<compare|cause_effect|argumentation>"}}
"""


def _trafilatura_scrape(url: str) -> str:
    """Scrape article text using httpx + trafilatura (controlled 20s timeout, no system proxy)."""
    import httpx
    import trafilatura

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
    }
    # trust_env=False bypasses system proxy (all_proxy / HTTPS_PROXY) that can hang
    with httpx.Client(trust_env=False, follow_redirects=True, timeout=20) as client:
        response = client.get(url, headers=headers)
    response.raise_for_status()
    text = trafilatura.extract(response.text, include_comments=False, include_tables=False)
    if not text:
        raise RuntimeError(f"trafilatura: no extractable text from {url}")
    return text


@tool
def load_user_profile() -> dict[str, object]:
    """Load the user's profile from the database."""
    profile = _db.get_user_profile()
    if profile is None:
        return {"error": "No user profile found. Run onboarding first."}
    return profile.model_dump()


@tool
def scrape_article(url: str) -> str:
    """Scrape the full text of an article. Falls back to trafilatura if Scrapling fails."""
    try:
        if Scraper is None:
            raise ImportError("Scraper not available in this scrapling version")
        scraper = Scraper(auto_match=True)
        page = scraper.get(url)
        return page.get_best_text(auto_filter=True)
    except Exception as e:
        logger.warning(f"Scrapling failed for {url}: {e}. Trying trafilatura.")
    try:
        return _trafilatura_scrape(url)
    except Exception as e:
        logger.error(f"trafilatura fallback failed for {url}: {e}")
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
    prompt = HIGHLIGHT_PROMPT.format(
        paragraphs=numbered,
        goal=user_goal,
        interests=", ".join(interests),
    )
    for attempt in range(3):
        try:
            response = _get_llm().invoke(prompt)
            content = str(response.content).strip()
            if not content:
                raise ValueError("Empty response from model")
            result: HighlightResult = parse_json(content, HighlightResult)  # type: ignore[assignment]
            valid_indices = [i for i in result.highlight_indices if 0 <= i < len(paragraphs)]
            return {"highlight_indices": valid_indices, "article_logic": result.article_logic}
        except Exception as e:
            logger.warning(f"highlight_key_paragraphs attempt {attempt + 1} failed: {e}")
    raise ValueError("highlight_key_paragraphs failed after 3 attempts")


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

Return ONLY a JSON object with no prose, no markdown fences. Schema:
{{"mode": "{mode}",
"instruction": "<full task description referencing article topics, min 50 chars>",
"min_words": <50 for professional or 150 for ielts>,
"article_id": 0}}
"""
    for attempt in range(3):
        try:
            response = _get_llm().invoke(prompt)
            content = str(response.content).strip()
            if not content:
                raise ValueError("Empty response from model")
            result: WritingTaskCreate = parse_json(content, WritingTaskCreate)  # type: ignore[assignment]
            return result.model_dump()
        except Exception as e:
            logger.warning(f"generate_writing_task attempt {attempt + 1} failed: {e}")
    raise ValueError("generate_writing_task failed after 3 attempts")


@tool
def save_daily_lesson(article: ArticleCreate, task: WritingTaskCreate) -> str:
    """Save today's article and writing task to the database. Call as the final step."""
    article = article.model_copy(update={"date": date.today().isoformat()})
    _db.save_daily_lesson(article, task)
    return f"Saved: '{article.original_title}'"
