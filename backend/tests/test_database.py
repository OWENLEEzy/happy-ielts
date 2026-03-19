from datetime import date

from backend.database import Database
from backend.models import ArticleCreate, UserProfile, VocabItemCreate


def test_upsert_and_get_user_profile():
    db = Database(":memory:")
    profile = UserProfile(
        goal="Read TypeScript docs",
        interests=["TypeScript", "LangGraph"],
        level=6,
        bandwidth_minutes=25,
        writing_mode="professional",
    )
    db.upsert_user_profile(profile)
    result = db.get_user_profile()
    assert result is not None
    assert result.goal == "Read TypeScript docs"
    assert result.level == 6


def test_upsert_article_and_get_today():
    db = Database(":memory:")
    article = ArticleCreate(
        date=date.today().isoformat(),
        source_url="https://example.com/article",
        original_title="Test Article",
        full_text=(
            "Para one is a long paragraph with enough text to pass validation requirements."
            "\n\nPara two contains more content for the article body text."
            "\n\nPara three concludes the article."
        ),
        highlight_indices=[0, 2],
        article_logic="compare",
        topic_tags=["TypeScript"],
    )
    db.upsert_article(article)
    result = db.get_today_article()
    assert result is not None
    assert result.original_title == "Test Article"
    assert result.highlight_indices == [0, 2]


def test_vocab_due_query():
    db = Database(":memory:")
    item = VocabItemCreate(
        word="leverage",
        context_sentence="We can leverage this library.",
        source="reading_click",
        next_review=date.today().isoformat(),
        fsrs_state={
            "card_id": 1,
            "due": date.today().isoformat(),
            "stability": 1.0,
            "difficulty": 5.0,
            "step": 0,
            "state": 0,
            "last_review": None,
        },
        article_id=None,
    )
    db.upsert_vocab_item(item)
    due = db.get_due_vocab_items(date.today())
    assert len(due) == 1
    assert due[0].word == "leverage"
