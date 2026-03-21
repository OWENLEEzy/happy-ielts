import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date
from typing import Protocol

from backend.models import (
    Article,
    ArticleCreate,
    UserProfile,
    VocabItem,
    VocabItemCreate,
    WritingSubmissionCreate,
    WritingTask,
    WritingTaskCreate,
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


class DatabaseProtocol(Protocol):
    """Public interface for Database. Enables future Supabase swap."""

    def upsert_user_profile(self, profile: UserProfile) -> None: ...

    def get_user_profile(self) -> UserProfile | None: ...

    def upsert_article(self, article: ArticleCreate) -> int: ...

    def get_today_article(self) -> Article | None: ...

    def upsert_writing_task(self, task: WritingTaskCreate) -> int: ...

    def get_today_writing_task(self) -> WritingTask | None: ...

    def save_writing_submission(self, sub: WritingSubmissionCreate) -> int: ...

    def upsert_vocab_item(self, item: VocabItemCreate) -> None: ...

    def get_due_vocab_items(self, today: date) -> list[VocabItem]: ...

    def get_all_vocab_items(self) -> list[VocabItem]: ...

    def save_daily_lesson(
        self, article: ArticleCreate, task: WritingTaskCreate
    ) -> tuple[int, int]: ...

    def query_weekly_stats(self) -> dict: ...

    def get_article_for_date(self, date_str: str) -> "Article | None": ...

    def query_topic_performance(self) -> dict: ...

    def query_writing_task_history(self) -> dict: ...

    def count_sessions(self) -> int: ...

    def query_session_dates(self) -> list[str]: ...

    def count_articles(self) -> int: ...

    def upsert_reading_start(self, today: date) -> None: ...


_instance: "Database | None" = None


def get_db(db_path: str = "./db.sqlite3") -> "Database":
    global _instance
    if _instance is None:
        _instance = Database(db_path)
    return _instance


class Database:
    def __init__(self, db_path: str = "./db.sqlite3"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn_instance = sqlite3.connect(db_path, check_same_thread=False)
        self._conn_instance.row_factory = sqlite3.Row
        self._init_tables()

    @contextmanager
    def _conn(self):
        with self._lock:
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
            conn.execute(
                """
                INSERT INTO user_profile
                    (id, goal, interests, level, bandwidth_minutes, writing_mode)
                VALUES (1, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    goal=excluded.goal,
                    interests=excluded.interests,
                    level=excluded.level,
                    bandwidth_minutes=excluded.bandwidth_minutes,
                    writing_mode=excluded.writing_mode
            """,
                (
                    profile.goal,
                    json.dumps(profile.interests),
                    profile.level,
                    profile.bandwidth_minutes,
                    profile.writing_mode,
                ),
            )

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
            cursor = conn.execute(
                """
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
                RETURNING id
            """,
                (
                    article.date,
                    article.source_url,
                    article.original_title,
                    article.full_text,
                    json.dumps(article.highlight_indices),
                    article.article_logic,
                    json.dumps(article.topic_tags),
                ),
            )
            return cursor.fetchone()[0]

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
                conn.execute(
                    """
                    UPDATE writing_tasks SET mode=?, instruction=?, min_words=?
                    WHERE article_id=?
                """,
                    (task.mode, task.instruction, task.min_words, task.article_id),
                )
                return existing["id"]
            cursor = conn.execute(
                """
                INSERT INTO writing_tasks (article_id, mode, instruction, min_words)
                VALUES (?, ?, ?, ?)
            """,
                (task.article_id, task.mode, task.instruction, task.min_words),
            )
            row_id = cursor.lastrowid
            if row_id is None:
                raise RuntimeError("INSERT into writing_tasks returned no lastrowid")
            return row_id

    def get_today_writing_task(self) -> WritingTask | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT wt.* FROM writing_tasks wt
                JOIN articles a ON wt.article_id = a.id
                WHERE a.date=?
            """,
                (date.today().isoformat(),),
            ).fetchone()
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
            conn.execute(
                """
                INSERT INTO vocab_items (word, context_sentence, source, next_review,
                                         fsrs_state, article_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(word) DO UPDATE SET
                    context_sentence=excluded.context_sentence,
                    source=excluded.source,
                    next_review=excluded.next_review,
                    fsrs_state=excluded.fsrs_state,
                    article_id=excluded.article_id
            """,
                (
                    item.word,
                    item.context_sentence,
                    item.source,
                    item.next_review,
                    json.dumps(item.fsrs_state),
                    item.article_id,
                ),
            )

    def get_due_vocab_items(self, today: date) -> list[VocabItem]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM vocab_items WHERE next_review <= ? ORDER BY next_review",
                (today.isoformat(),),
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
            cursor = conn.execute(
                """
                INSERT INTO writing_submissions
                    (task_id, user_text, overall_score, grammar_errors,
                     chinglish_flags, rewrite_suggestions, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    sub.task_id,
                    sub.user_text,
                    sub.overall_score,
                    json.dumps([e.model_dump() for e in sub.grammar_errors]),
                    json.dumps([f.model_dump() for f in sub.chinglish_flags]),
                    json.dumps(sub.rewrite_suggestions),
                    sub.submitted_at.isoformat(),
                ),
            )
            row_id = cursor.lastrowid
            if row_id is None:
                raise RuntimeError("INSERT into writing_submissions returned no lastrowid")
            return row_id

    def save_daily_lesson(self, article: ArticleCreate, task: WritingTaskCreate) -> tuple[int, int]:
        """Insert/update article and writing task atomically in a single transaction."""
        with self._conn() as conn:
            cursor = conn.execute(
                """
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
                RETURNING id
            """,
                (
                    article.date,
                    article.source_url,
                    article.original_title,
                    article.full_text,
                    json.dumps(article.highlight_indices),
                    article.article_logic,
                    json.dumps(article.topic_tags),
                ),
            )
            article_id: int = cursor.fetchone()[0]

            existing = conn.execute(
                "SELECT id FROM writing_tasks WHERE article_id=?", (article_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE writing_tasks SET mode=?, instruction=?, min_words=?
                    WHERE article_id=?
                """,
                    (task.mode, task.instruction, task.min_words, article_id),
                )
                task_id: int = existing["id"]
            else:
                task_cursor = conn.execute(
                    """
                    INSERT INTO writing_tasks (article_id, mode, instruction, min_words)
                    VALUES (?, ?, ?, ?)
                """,
                    (article_id, task.mode, task.instruction, task.min_words),
                )
                row_id = task_cursor.lastrowid
                if row_id is None:
                    raise RuntimeError("INSERT into writing_tasks returned no lastrowid")
                task_id = row_id

            return (article_id, task_id)

    def upsert_reading_start(self, today: date) -> None:  # noqa: ARG002
        """Idempotent marker that reading session started today."""
        # No separate table needed — article existence is the marker
        pass

    def query_weekly_stats(self) -> dict:
        """Returns structured facts for Orchestrator → Reflect/Planner context."""
        with self._conn() as conn:
            writing_scores = conn.execute(
                "SELECT date(submitted_at) as d, overall_score "
                "FROM writing_submissions ORDER BY submitted_at DESC LIMIT 7"
            ).fetchall()

            chinglish_counts = conn.execute(
                "SELECT json_extract(value, '$.issue') as issue, COUNT(*) as cnt "
                "FROM writing_submissions, json_each(chinglish_flags) "
                "WHERE submitted_at > datetime('now', '-7 days') "
                "GROUP BY issue ORDER BY cnt DESC"
            ).fetchall()

            vocab_total = conn.execute("SELECT COUNT(*) FROM vocab_items").fetchone()[0]

            topic_distribution = conn.execute(
                "SELECT json_each.value as topic, COUNT(*) as cnt "
                "FROM articles, json_each(articles.topic_tags) "
                "WHERE articles.date > date('now', '-14 days') "
                "GROUP BY topic ORDER BY cnt DESC"
            ).fetchall()

            return {
                "writing_scores": [{"date": r[0], "score": r[1]} for r in writing_scores],
                "chinglish_counts": [{"issue": r[0], "count": r[1]} for r in chinglish_counts],
                "vocab_mastered": vocab_total,
                "topic_distribution": [{"topic": r[0], "count": r[1]} for r in topic_distribution],
            }

    def get_article_for_date(self, date_str: str) -> "Article | None":
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM articles WHERE date=?", (date_str,)).fetchone()
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

    def query_topic_performance(self) -> dict:
        """Returns per-topic writing performance aggregated from all submissions."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT json_each.value as topic,
                       COUNT(*) as sessions,
                       ROUND(AVG(ws.overall_score), 1) as avg_score
                FROM writing_submissions ws
                JOIN writing_tasks wt ON ws.task_id = wt.id
                JOIN articles a ON wt.article_id = a.id,
                     json_each(a.topic_tags)
                GROUP BY topic
                ORDER BY sessions DESC
                """
            ).fetchall()
            return {
                r["topic"]: {"sessions": r["sessions"], "avg_score": r["avg_score"]} for r in rows
            }

    def query_writing_task_history(self) -> dict:
        """Returns per-article-logic-type writing performance from all submissions."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT a.article_logic as logic_type,
                       COUNT(*) as count,
                       ROUND(AVG(ws.overall_score), 1) as avg_score
                FROM writing_submissions ws
                JOIN writing_tasks wt ON ws.task_id = wt.id
                JOIN articles a ON wt.article_id = a.id
                GROUP BY a.article_logic
                """
            ).fetchall()
            return {
                r["logic_type"]: {"count": r["count"], "avg_score": r["avg_score"]} for r in rows
            }

    def count_sessions(self) -> int:
        """Total number of completed writing submissions."""
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM writing_submissions").fetchone()[0]

    def query_session_dates(self) -> list[str]:
        """Distinct ISO dates where writing was submitted, newest first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT date(submitted_at) as d "
                "FROM writing_submissions ORDER BY d DESC"
            ).fetchall()
            return [r["d"] for r in rows]

    def count_articles(self) -> int:
        """Total number of articles stored (includes days without a submission)."""
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
