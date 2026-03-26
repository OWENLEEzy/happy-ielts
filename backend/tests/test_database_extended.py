"""Extended database tests — covers all Database methods against a real Postgres DB."""

from datetime import date, datetime, timedelta

from backend.database import DatabaseProtocol
from backend.models import (
    ArticleCreate,
    ChinglishFlag,
    GrammarError,
    UserProfile,
    VocabItemCreate,
    WritingSubmissionCreate,
    WritingTaskCreate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LONG_TEXT = (
    "Para one is a long paragraph with enough text to pass validation requirements. "
    "\n\nPara two contains more content for the article body text. "
    "\n\nPara three concludes the article with additional prose to exceed the minimum."
)

LONG_INSTRUCTION = (
    "Write a professional email addressing the key points of the article above, "
    "demonstrating clear argumentation and structured reasoning in your response."
)

TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


def make_article(day: str = TODAY, title: str = "Test Article") -> ArticleCreate:
    return ArticleCreate(
        date=day,
        source_url="https://example.com/article",
        original_title=title,
        full_text=LONG_TEXT,
        highlight_indices=[0, 1, 2],
        article_logic="compare",
        topic_tags=["tech"],
    )


def make_task(article_id: int, mode: str = "professional") -> WritingTaskCreate:
    return WritingTaskCreate(
        article_id=article_id,
        mode=mode,  # type: ignore[arg-type]
        instruction=LONG_INSTRUCTION,
        min_words=100,
    )


def make_vocab(word: str = "leverage", next_review: str = TODAY) -> VocabItemCreate:
    return VocabItemCreate(
        word=word,
        context_sentence=f"We can {word} this library.",
        source="reading_click",
        next_review=next_review,
        fsrs_state={
            "due": next_review,
            "stability": 1.0,
            "difficulty": 5.0,
            "step": 0,
            "state": 0,
            "last_review": None,
        },
        article_id=None,
    )


# ---------------------------------------------------------------------------
# upsert_user_profile / get_user_profile
# ---------------------------------------------------------------------------


def test_get_user_profile_returns_none_when_empty(db):
    assert db.get_user_profile() is None


def test_upsert_user_profile_roundtrip(db):
    profile = UserProfile(
        goal="Read AI papers",
        interests=["AI", "ML"],
        level=7,
        bandwidth_minutes=30,
        writing_mode="professional",
    )
    db.upsert_user_profile(profile)
    result = db.get_user_profile()
    assert result is not None
    assert result.goal == "Read AI papers"
    assert result.interests == ["AI", "ML"]
    assert result.level == 7
    assert result.writing_mode == "professional"


def test_upsert_user_profile_overwrites(db):
    """Second upsert overwrites the first — only one row ever."""
    p1 = UserProfile(
        goal="First goal",
        interests=["tech"],
        level=4,
        bandwidth_minutes=20,
        writing_mode="ielts_task1",
    )
    p2 = UserProfile(
        goal="Updated goal",
        interests=["science", "writing"],
        level=8,
        bandwidth_minutes=45,
        writing_mode="ielts_task2",
    )
    db.upsert_user_profile(p1)
    db.upsert_user_profile(p2)
    result = db.get_user_profile()
    assert result is not None
    assert result.goal == "Updated goal"
    assert result.level == 8
    assert result.writing_mode == "ielts_task2"


# ---------------------------------------------------------------------------
# upsert_article / get_today_article
# ---------------------------------------------------------------------------


def test_upsert_article_returns_id(db):
    article_id = db.upsert_article(make_article())
    assert isinstance(article_id, int)
    assert article_id >= 1


def test_upsert_article_conflict_updates_and_returns_same_id(db):
    """Upserting same date twice returns the same id and updates fields."""
    first_id = db.upsert_article(make_article(title="First"))
    second_id = db.upsert_article(make_article(title="Updated"))
    assert first_id == second_id
    result = db.get_today_article()
    assert result is not None
    assert result.original_title == "Updated"


def test_get_today_article_returns_none_when_no_today_article(db):
    db.upsert_article(make_article(day=YESTERDAY))
    result = db.get_today_article()
    assert result is None


def test_get_today_article_returns_correct_article(db):
    db.upsert_article(make_article(day=YESTERDAY, title="Old"))
    db.upsert_article(make_article(day=TODAY, title="Today's Article"))
    result = db.get_today_article()
    assert result is not None
    assert result.original_title == "Today's Article"
    assert result.highlight_indices == [0, 1, 2]
    assert result.topic_tags == ["tech"]


# ---------------------------------------------------------------------------
# upsert_writing_task / get_today_writing_task
# ---------------------------------------------------------------------------


def test_upsert_writing_task_returns_id(db):
    article_id = db.upsert_article(make_article())
    task_id = db.upsert_writing_task(make_task(article_id))
    assert isinstance(task_id, int)
    assert task_id >= 1


def test_upsert_writing_task_conflict_updates(db):
    """Second upsert for same article_id updates fields and returns same id."""
    article_id = db.upsert_article(make_article())
    first_id = db.upsert_writing_task(make_task(article_id, mode="professional"))
    second_id = db.upsert_writing_task(make_task(article_id, mode="ielts_task2"))
    assert first_id == second_id
    task = db.get_today_writing_task()
    assert task is not None
    assert task.mode == "ielts_task2"


def test_get_today_writing_task_returns_none_when_no_today_article(db):
    assert db.get_today_writing_task() is None


def test_get_today_writing_task_roundtrip(db):
    article_id = db.upsert_article(make_article())
    db.upsert_writing_task(make_task(article_id))
    task = db.get_today_writing_task()
    assert task is not None
    assert task.article_id == article_id
    assert task.mode == "professional"
    assert task.min_words == 100


# ---------------------------------------------------------------------------
# save_daily_lesson
# ---------------------------------------------------------------------------


def test_save_daily_lesson_returns_tuple_of_ids(db):
    article = make_article()
    task_template = WritingTaskCreate(
        article_id=0,
        mode="professional",
        instruction=LONG_INSTRUCTION,
        min_words=100,
    )
    article_id, task_id = db.save_daily_lesson(article, task_template)
    assert isinstance(article_id, int)
    assert isinstance(task_id, int)
    assert article_id >= 1
    assert task_id >= 1


def test_save_daily_lesson_idempotent(db):
    """Calling save_daily_lesson twice for the same date returns same ids."""
    article = make_article()
    task_template = WritingTaskCreate(
        article_id=0,
        mode="professional",
        instruction=LONG_INSTRUCTION,
        min_words=100,
    )
    a1, t1 = db.save_daily_lesson(article, task_template)
    a2, t2 = db.save_daily_lesson(article, task_template)
    assert a1 == a2
    assert t1 == t2


def test_save_daily_lesson_article_readable_afterwards(db):
    article = make_article()
    task_template = WritingTaskCreate(
        article_id=0,
        mode="ielts_task1",
        instruction=LONG_INSTRUCTION,
        min_words=120,
    )
    db.save_daily_lesson(article, task_template)
    retrieved = db.get_today_article()
    assert retrieved is not None
    assert retrieved.original_title == "Test Article"
    task = db.get_today_writing_task()
    assert task is not None
    assert task.mode == "ielts_task1"


# ---------------------------------------------------------------------------
# upsert_vocab_item / get_due_vocab_items / get_all_vocab_items
# ---------------------------------------------------------------------------


def test_upsert_vocab_item_conflict_updates(db):
    """Upserting the same word twice updates context_sentence and next_review."""
    db.upsert_vocab_item(make_vocab("fluent", TODAY))
    updated = VocabItemCreate(
        word="fluent",
        context_sentence="She speaks fluent Spanish.",
        source="writing_error",
        next_review=TOMORROW,
        fsrs_state={"due": TOMORROW, "stability": 2.0},
        article_id=None,
    )
    db.upsert_vocab_item(updated)
    all_items = db.get_all_vocab_items()
    assert len(all_items) == 1
    assert all_items[0].context_sentence == "She speaks fluent Spanish."
    assert all_items[0].next_review == TOMORROW


def test_get_due_vocab_items_excludes_future(db):
    db.upsert_vocab_item(make_vocab("now", TODAY))
    db.upsert_vocab_item(make_vocab("soon", TOMORROW))
    db.upsert_vocab_item(make_vocab("past", YESTERDAY))
    due = db.get_due_vocab_items(date.today())
    words = {item.word for item in due}
    assert "now" in words
    assert "past" in words
    assert "soon" not in words


def test_get_due_vocab_items_empty_when_all_future(db):
    db.upsert_vocab_item(make_vocab("future", TOMORROW))
    due = db.get_due_vocab_items(date.today())
    assert due == []


def test_get_all_vocab_items_returns_everything(db):
    db.upsert_vocab_item(make_vocab("alpha", TODAY))
    db.upsert_vocab_item(make_vocab("beta", TOMORROW))
    all_items = db.get_all_vocab_items()
    assert len(all_items) == 2
    assert {item.word for item in all_items} == {"alpha", "beta"}


def test_get_all_vocab_items_empty(db):
    assert db.get_all_vocab_items() == []


# ---------------------------------------------------------------------------
# save_writing_submission
# ---------------------------------------------------------------------------


def test_save_writing_submission_returns_id(db):
    sub = WritingSubmissionCreate(
        task_id=1,
        user_text="This is my essay text.",
        overall_score=7,
        grammar_errors=[
            GrammarError(
                original="He go home",
                correction="He goes home",
                explanation_zh="第三人称单数",
            )
        ],
        chinglish_flags=[
            ChinglishFlag(
                original="do a contribution",
                issue="word_choice",
                explanation_zh="应用 make a contribution",
                native_alternative="make a contribution",
            )
        ],
        rewrite_suggestions=["Better version of the essay."],
        submitted_at=datetime(2026, 3, 19, 12, 0, 0),
    )
    sub_id = db.save_writing_submission(sub)
    assert isinstance(sub_id, int)
    assert sub_id >= 1


def test_save_writing_submission_multiple_increments_id(db):
    """Each submission gets a unique, incrementing id."""

    def make_sub(score: int) -> WritingSubmissionCreate:
        return WritingSubmissionCreate(
            task_id=1,
            user_text="Essay text.",
            overall_score=score,
            grammar_errors=[],
            chinglish_flags=[],
            rewrite_suggestions=[],
            submitted_at=datetime.now(),
        )

    id1 = db.save_writing_submission(make_sub(6))
    id2 = db.save_writing_submission(make_sub(8))
    assert id2 > id1


# ---------------------------------------------------------------------------
# DatabaseProtocol structural compatibility
# ---------------------------------------------------------------------------


def test_database_has_all_protocol_methods(db):
    """Database must implement every method declared on DatabaseProtocol."""
    protocol_methods = [attr for attr in dir(DatabaseProtocol) if not attr.startswith("_")]
    for method in protocol_methods:
        assert hasattr(db, method), f"Database is missing protocol method: {method}"


def test_database_protocol_is_a_protocol():
    """DatabaseProtocol is a proper Protocol class."""
    assert getattr(DatabaseProtocol, "_is_protocol", False) is True


# ---------------------------------------------------------------------------
# upsert_reading_start (no-op but should not raise)
# ---------------------------------------------------------------------------


def test_upsert_reading_start_is_noop(db):
    db.upsert_reading_start(date.today())
