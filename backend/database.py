import json
import sqlite3
from datetime import date
from contextlib import contextmanager
from backend.models import (
    UserProfile, ArticleCreate, Article,
    WritingTaskCreate, WritingTask,
    VocabItemCreate, VocabItem,
    WritingSubmissionCreate,
)

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS user_profile (
    id INTEGER PRIMARY KEY DEFAULT 1,
    goal TEXT NOT NULL,
    interests TEXT NOT NULL,
    level INTEGER NOT NULL,
    bandwidth_minutes INTEGER NOT NULL,
    writing_mode TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    source_url TEXT NOT NULL,
    original_title TEXT NOT NULL,
    full_text TEXT NOT NULL,
    highlight_indices TEXT NOT NULL,
    article_logic TEXT NOT NULL,
    topic_tags TEXT NOT NULL,
    UNIQUE(date)
);

CREATE TABLE IF NOT EXISTS writing_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    mode TEXT NOT NULL,
    instruction TEXT NOT NULL,
    min_words INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS writing_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    user_text TEXT NOT NULL,
    overall_score INTEGER NOT NULL,
    grammar_errors TEXT NOT NULL,
    chinglish_flags TEXT NOT NULL,
    rewrite_suggestions TEXT NOT NULL,
    submitted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vocab_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL UNIQUE,
    context_sentence TEXT NOT NULL,
    source TEXT NOT NULL,
    next_review TEXT NOT NULL,
    fsrs_state TEXT NOT NULL,
    article_id INTEGER
);
"""


class Database:
    def __init__(self, db_path: str = "./db.sqlite3"):
        self.db_path = db_path
        self._conn_instance = sqlite3.connect(db_path, check_same_thread=False)
        self._conn_instance.row_factory = sqlite3.Row
        self._init_tables()

    @contextmanager
    def _conn(self):
        try:
            yield self._conn_instance
            self._conn_instance.commit()
        except Exception:
            self._conn_instance.rollback()
            raise

    def _init_tables(self):
        with self._conn() as conn:
            conn.executescript(CREATE_TABLES)

    def upsert_user_profile(self, profile: UserProfile) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO user_profile (id, goal, interests, level, bandwidth_minutes, writing_mode)
                VALUES (1, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    goal=excluded.goal,
                    interests=excluded.interests,
                    level=excluded.level,
                    bandwidth_minutes=excluded.bandwidth_minutes,
                    writing_mode=excluded.writing_mode
            """, (
                profile.goal,
                json.dumps(profile.interests),
                profile.level,
                profile.bandwidth_minutes,
                profile.writing_mode,
            ))

    def get_user_profile(self) -> UserProfile | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM user_profile WHERE id=1").fetchone()
            if row is None:
                return None
            return UserProfile(
                goal=row["goal"],
                interests=json.loads(row["interests"]),
                level=row["level"],
                bandwidth_minutes=row["bandwidth_minutes"],
                writing_mode=row["writing_mode"],
            )

    def upsert_article(self, article: ArticleCreate) -> int:
        with self._conn() as conn:
            cursor = conn.execute("""
                INSERT INTO articles (date, source_url, original_title, full_text,
                                      highlight_indices, article_logic, topic_tags)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    source_url=excluded.source_url,
                    original_title=excluded.original_title,
                    full_text=excluded.full_text,
                    highlight_indices=excluded.highlight_indices,
                    article_logic=excluded.article_logic,
                    topic_tags=excluded.topic_tags
            """, (
                article.date,
                article.source_url,
                article.original_title,
                article.full_text,
                json.dumps(article.highlight_indices),
                article.article_logic,
                json.dumps(article.topic_tags),
            ))
            return cursor.lastrowid or conn.execute(
                "SELECT id FROM articles WHERE date=?", (article.date,)
            ).fetchone()["id"]

    def get_today_article(self) -> Article | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM articles WHERE date=?", (date.today().isoformat(),)
            ).fetchone()
            if row is None:
                return None
            return Article(
                id=row["id"],
                date=row["date"],
                source_url=row["source_url"],
                original_title=row["original_title"],
                full_text=row["full_text"],
                highlight_indices=json.loads(row["highlight_indices"]),
                article_logic=row["article_logic"],
                topic_tags=json.loads(row["topic_tags"]),
            )

    def upsert_writing_task(self, task: WritingTaskCreate) -> int:
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT id FROM writing_tasks WHERE article_id=?", (task.article_id,)
            ).fetchone()
            if existing:
                conn.execute("""
                    UPDATE writing_tasks SET mode=?, instruction=?, min_words=?
                    WHERE article_id=?
                """, (task.mode, task.instruction, task.min_words, task.article_id))
                return existing["id"]
            cursor = conn.execute("""
                INSERT INTO writing_tasks (article_id, mode, instruction, min_words)
                VALUES (?, ?, ?, ?)
            """, (task.article_id, task.mode, task.instruction, task.min_words))
            return cursor.lastrowid

    def get_today_writing_task(self) -> WritingTask | None:
        with self._conn() as conn:
            row = conn.execute("""
                SELECT wt.* FROM writing_tasks wt
                JOIN articles a ON wt.article_id = a.id
                WHERE a.date=?
            """, (date.today().isoformat(),)).fetchone()
            if row is None:
                return None
            return WritingTask(
                id=row["id"],
                article_id=row["article_id"],
                mode=row["mode"],
                instruction=row["instruction"],
                min_words=row["min_words"],
            )

    def upsert_vocab_item(self, item: VocabItemCreate) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO vocab_items (word, context_sentence, source, next_review,
                                         fsrs_state, article_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(word) DO UPDATE SET
                    context_sentence=excluded.context_sentence,
                    source=excluded.source,
                    next_review=excluded.next_review,
                    fsrs_state=excluded.fsrs_state,
                    article_id=excluded.article_id
            """, (
                item.word,
                item.context_sentence,
                item.source,
                item.next_review,
                json.dumps(item.fsrs_state),
                item.article_id,
            ))

    def get_due_vocab_items(self, today: date) -> list[VocabItem]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM vocab_items WHERE next_review <= ? ORDER BY next_review",
                (today.isoformat(),)
            ).fetchall()
            return [
                VocabItem(
                    id=r["id"],
                    word=r["word"],
                    context_sentence=r["context_sentence"],
                    source=r["source"],
                    next_review=r["next_review"],
                    fsrs_state=json.loads(r["fsrs_state"]),
                    article_id=r["article_id"],
                )
                for r in rows
            ]

    def get_all_vocab_items(self) -> list[VocabItem]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM vocab_items ORDER BY next_review").fetchall()
            return [
                VocabItem(
                    id=r["id"],
                    word=r["word"],
                    context_sentence=r["context_sentence"],
                    source=r["source"],
                    next_review=r["next_review"],
                    fsrs_state=json.loads(r["fsrs_state"]),
                    article_id=r["article_id"],
                )
                for r in rows
            ]

    def save_writing_submission(self, sub: WritingSubmissionCreate) -> int:
        with self._conn() as conn:
            cursor = conn.execute("""
                INSERT INTO writing_submissions
                    (task_id, user_text, overall_score, grammar_errors,
                     chinglish_flags, rewrite_suggestions, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                sub.task_id,
                sub.user_text,
                sub.overall_score,
                json.dumps([e.model_dump() for e in sub.grammar_errors]),
                json.dumps([f.model_dump() for f in sub.chinglish_flags]),
                json.dumps(sub.rewrite_suggestions),
                sub.submitted_at.isoformat(),
            ))
            return cursor.lastrowid

    def upsert_reading_start(self, today: date) -> None:
        """Idempotent marker that reading session started today."""
        # No separate table needed — article existence is the marker
        pass
