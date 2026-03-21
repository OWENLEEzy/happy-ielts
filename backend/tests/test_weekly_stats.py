from datetime import date, datetime

from backend.database import Database
from backend.models import ArticleCreate, UserProfile, WritingSubmissionCreate, WritingTaskCreate


def _seed_db(db: Database):
    """Seed minimal data for stats queries."""
    db.upsert_user_profile(
        UserProfile(
            goal="test",
            interests=["tech"],
            level=5,
            bandwidth_minutes=25,
            writing_mode="professional",
        )
    )
    article_id = db.upsert_article(
        ArticleCreate(
            date=date.today().isoformat(),
            source_url="http://test.com",
            original_title="Test Article",
            full_text="x" * 200,
            highlight_indices=[0, 1, 2],
            article_logic="argumentation",
            topic_tags=["tech"],
        )
    )
    task_id = db.upsert_writing_task(
        WritingTaskCreate(
            article_id=article_id,
            mode="professional",
            instruction="Write a 100-word summary about the argument." * 2,
            min_words=50,
        )
    )
    db.save_writing_submission(
        WritingSubmissionCreate(
            task_id=task_id,
            user_text="test text",
            overall_score=7,
            grammar_errors=[],
            chinglish_flags=[],
            rewrite_suggestions=[],
            submitted_at=datetime.now(),
        )
    )
    return article_id


def test_query_weekly_stats_returns_expected_keys(tmp_path):
    db = Database(str(tmp_path / "test.sqlite3"))
    _seed_db(db)
    stats = db.query_weekly_stats()
    assert "writing_scores" in stats
    assert "chinglish_counts" in stats
    assert "vocab_mastered" in stats
    assert "topic_distribution" in stats
    assert len(stats["writing_scores"]) == 1
    assert stats["writing_scores"][0]["score"] == 7


def test_get_article_for_date(tmp_path):
    db = Database(str(tmp_path / "test.sqlite3"))
    db.upsert_user_profile(
        UserProfile(
            goal="test",
            interests=["tech"],
            level=5,
            bandwidth_minutes=25,
            writing_mode="professional",
        )
    )
    db.upsert_article(
        ArticleCreate(
            date="2026-03-22",
            source_url="http://test.com",
            original_title="Tomorrow's Article",
            full_text="x" * 200,
            highlight_indices=[0, 1, 2],
            article_logic="compare",
            topic_tags=["policy"],
        )
    )
    article = db.get_article_for_date("2026-03-22")
    assert article is not None
    assert article.original_title == "Tomorrow's Article"
    assert db.get_article_for_date("2099-01-01") is None
