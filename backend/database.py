import json
import os
import threading
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Any, Protocol

import psycopg2
import psycopg2.extensions
import psycopg2.extras
import psycopg2.pool
from pydantic import ValidationError

from backend.models import (
    Article,
    ArticleCreate,
    GeneralLesson,
    GeneralProject,
    GeneralStudentModel,
    LearningMap,
    UserGoalProfile,
    UserProfile,
    VocabItem,
    VocabItemCreate,
    WritingSubmissionCreate,
    WritingTask,
    WritingTaskCreate,
)


def _safe_json(raw: "str | bytes | bytearray | None", fallback: Any = None) -> Any:
    """Decode a JSON string; return *fallback* on any parse error or empty input."""
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return fallback


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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL,
    mode TEXT NOT NULL,
    instruction TEXT NOT NULL,
    min_words INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS writing_submissions (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL,
    user_text TEXT NOT NULL,
    overall_score INTEGER NOT NULL,
    grammar_errors TEXT NOT NULL,
    chinglish_flags TEXT NOT NULL,
    rewrite_suggestions TEXT NOT NULL,
    submitted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vocab_items (
    id SERIAL PRIMARY KEY,
    word TEXT NOT NULL UNIQUE,
    context_sentence TEXT NOT NULL,
    source TEXT NOT NULL,
    next_review TEXT NOT NULL,
    fsrs_state TEXT NOT NULL,
    article_id INTEGER
);

CREATE TABLE IF NOT EXISTS learning_projects (
    id           SERIAL PRIMARY KEY,
    user_topic   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'onboarding',
    goal_profile TEXT,
    learning_map TEXT,
    notebook_id  TEXT,
    tier         TEXT NOT NULL DEFAULT 'free',
    budget_used  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_lessons (
    id           SERIAL PRIMARY KEY,
    project_id   INTEGER NOT NULL REFERENCES learning_projects(id),
    chapter      INTEGER NOT NULL,
    lesson       INTEGER NOT NULL,
    title        TEXT NOT NULL,
    study_guide  TEXT,
    quiz_json    TEXT,
    flashcards   TEXT,
    status       TEXT NOT NULL DEFAULT 'pending',
    UNIQUE(project_id, chapter, lesson)
);

CREATE TABLE IF NOT EXISTS project_sessions (
    id           SERIAL PRIMARY KEY,
    project_id   INTEGER NOT NULL REFERENCES learning_projects(id),
    lesson_id    INTEGER NOT NULL REFERENCES project_lessons(id),
    quiz_answers TEXT,
    quiz_score   INTEGER,
    qa_history   TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS general_student_models (
    project_id   INTEGER PRIMARY KEY REFERENCES learning_projects(id),
    goal_outcome TEXT NOT NULL,
    goal_progress REAL NOT NULL DEFAULT 0.0,
    dimensions   TEXT NOT NULL DEFAULT '{}',
    fsrs_due     TEXT NOT NULL DEFAULT '[]',
    updated      TEXT NOT NULL
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

    def upsert_reading_start(self, _today: date) -> None: ...

    def create_general_project(
        self, topic: str, profile: UserGoalProfile | None, tier: str
    ) -> int: ...

    def list_general_projects(self) -> list[GeneralProject]: ...

    def get_general_project(self, project_id: int) -> GeneralProject | None: ...

    def update_general_project_status(self, project_id: int, status: str) -> None: ...

    def update_general_project_notebook(self, project_id: int, notebook_id: str) -> None: ...

    def update_general_project_goal_profile(
        self, project_id: int, profile: UserGoalProfile
    ) -> None: ...

    def update_general_project_map(
        self, project_id: int, learning_map: LearningMap, budget_used: int
    ) -> None: ...

    def update_general_project_profile_and_map(
        self, project_id: int, profile: UserGoalProfile, learning_map: LearningMap
    ) -> None: ...

    def upsert_general_lesson(
        self,
        project_id: int,
        chapter: int,
        lesson: int,
        title: str,
        study_guide: str,
        quiz_json: list,
        flashcards: list,
    ) -> None: ...

    def get_project_lessons(self, project_id: int) -> list[GeneralLesson]: ...

    def get_general_lesson(self, lesson_id: int) -> GeneralLesson | None: ...

    def save_general_session(
        self, project_id: int, lesson_id: int, quiz_answers: list, quiz_score: int, qa_history: list
    ) -> int: ...

    def get_project_sessions_recent(self, project_id: int, n: int) -> list[dict]: ...

    def save_general_student_model(self, project_id: int, model: GeneralStudentModel) -> None: ...

    def get_general_project_dashboard(self, project_id: int) -> dict: ...

    def get_last_session_for_lesson(self, project_id: int, lesson_id: int) -> dict | None: ...

    def get_general_student_model_full(self, project_id: int) -> GeneralStudentModel | None: ...


_instance: "Database | None" = None
_instance_lock = threading.Lock()


def get_db() -> "Database":
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:  # Double-checked locking
                _instance = Database()
    return _instance


def reset_db() -> None:
    """Reset the singleton. For use in tests only."""
    global _instance
    _instance = None


class Database:
    def __init__(self) -> None:
        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url:
            raise RuntimeError("DATABASE_URL environment variable is required")
        self._pool = psycopg2.pool.ThreadedConnectionPool(1, 5, dsn=database_url)
        self._init_tables()

    def _cur(self, conn: psycopg2.extensions.connection) -> psycopg2.extras.RealDictCursor:
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)  # type: ignore[return-value]

    @contextmanager
    def _conn(self):
        conn = self._pool.getconn()
        returned = False
        try:
            yield conn
            conn.commit()
        except psycopg2.OperationalError:
            # Stale connection — discard so the pool creates a fresh one next time
            try:
                conn.rollback()
            except Exception:
                pass
            self._pool.putconn(conn, close=True)
            returned = True
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            if not returned:
                self._pool.putconn(conn)

    def _init_tables(self):
        with self._conn() as conn:
            cur = self._cur(conn)
            for stmt in CREATE_TABLES.split(";"):
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)

    def upsert_user_profile(self, profile: UserProfile) -> None:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                """
                INSERT INTO user_profile
                    (id, goal, interests, level, bandwidth_minutes, writing_mode)
                VALUES (1, %s, %s, %s, %s, %s)
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
            cur = self._cur(conn)
            cur.execute("SELECT * FROM user_profile WHERE id=1")
            row = cur.fetchone()
            if row is None:
                return None
            return UserProfile(
                goal=row["goal"],
                interests=_safe_json(row["interests"], []),
                level=row["level"],
                bandwidth_minutes=row["bandwidth_minutes"],
                writing_mode=row["writing_mode"],
            )

    def upsert_article(self, article: ArticleCreate) -> int:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                """
                INSERT INTO articles (date, source_url, original_title, full_text,
                                      highlight_indices, article_logic, topic_tags)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
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
            row = cur.fetchone()
            return row["id"] if row else 0

    def get_today_article(self) -> Article | None:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute("SELECT * FROM articles WHERE date=%s", (date.today().isoformat(),))
            row = cur.fetchone()
            if row is None:
                return None
            return Article(
                id=row["id"],
                date=row["date"],
                source_url=row["source_url"],
                original_title=row["original_title"],
                full_text=row["full_text"],
                highlight_indices=_safe_json(row["highlight_indices"], []),
                article_logic=row["article_logic"],
                topic_tags=_safe_json(row["topic_tags"], []),
            )

    def upsert_writing_task(self, task: WritingTaskCreate) -> int:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute("SELECT id FROM writing_tasks WHERE article_id=%s", (task.article_id,))
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    """
                    UPDATE writing_tasks SET mode=%s, instruction=%s, min_words=%s
                    WHERE article_id=%s
                """,
                    (task.mode, task.instruction, task.min_words, task.article_id),
                )
                return existing["id"]
            cur.execute(
                """
                INSERT INTO writing_tasks (article_id, mode, instruction, min_words)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """,
                (task.article_id, task.mode, task.instruction, task.min_words),
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("INSERT into writing_tasks returned no id")
            return row["id"]

    def get_today_writing_task(self) -> WritingTask | None:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                """
                SELECT wt.* FROM writing_tasks wt
                JOIN articles a ON wt.article_id = a.id
                WHERE a.date=%s
            """,
                (date.today().isoformat(),),
            )
            row = cur.fetchone()
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
            cur = self._cur(conn)
            cur.execute(
                """
                INSERT INTO vocab_items (word, context_sentence, source, next_review,
                                         fsrs_state, article_id)
                VALUES (%s, %s, %s, %s, %s, %s)
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
            cur = self._cur(conn)
            cur.execute(
                "SELECT * FROM vocab_items WHERE next_review <= %s ORDER BY next_review",
                (today.isoformat(),),
            )
            rows = cur.fetchall()
            return [
                VocabItem(
                    id=r["id"],
                    word=r["word"],
                    context_sentence=r["context_sentence"],
                    source=r["source"],
                    next_review=r["next_review"],
                    fsrs_state=_safe_json(r["fsrs_state"], {}),
                    article_id=r["article_id"],
                )
                for r in rows
            ]

    def get_all_vocab_items(self) -> list[VocabItem]:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute("SELECT * FROM vocab_items ORDER BY next_review")
            rows = cur.fetchall()
            return [
                VocabItem(
                    id=r["id"],
                    word=r["word"],
                    context_sentence=r["context_sentence"],
                    source=r["source"],
                    next_review=r["next_review"],
                    fsrs_state=_safe_json(r["fsrs_state"], {}),
                    article_id=r["article_id"],
                )
                for r in rows
            ]

    def save_writing_submission(self, sub: WritingSubmissionCreate) -> int:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                """
                INSERT INTO writing_submissions
                    (task_id, user_text, overall_score, grammar_errors,
                     chinglish_flags, rewrite_suggestions, submitted_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
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
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("INSERT into writing_submissions returned no id")
            return row["id"]

    def save_daily_lesson(self, article: ArticleCreate, task: WritingTaskCreate) -> tuple[int, int]:
        """Insert/update article and writing task atomically in a single transaction."""
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                """
                INSERT INTO articles (date, source_url, original_title, full_text,
                                      highlight_indices, article_logic, topic_tags)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
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
            row = cur.fetchone()
            article_id: int = row["id"] if row else 0

            cur.execute("SELECT id FROM writing_tasks WHERE article_id=%s", (article_id,))
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    """
                    UPDATE writing_tasks SET mode=%s, instruction=%s, min_words=%s
                    WHERE article_id=%s
                """,
                    (task.mode, task.instruction, task.min_words, article_id),
                )
                task_id: int = existing["id"]
            else:
                cur.execute(
                    """
                    INSERT INTO writing_tasks (article_id, mode, instruction, min_words)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """,
                    (article_id, task.mode, task.instruction, task.min_words),
                )
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError("INSERT into writing_tasks returned no id")
                task_id = row["id"]

            return (article_id, task_id)

    def upsert_reading_start(self, _today: date) -> None:
        """Idempotent marker that reading session started today."""
        # No separate table needed — article existence is the marker
        pass

    def query_weekly_stats(self) -> dict:
        """Returns structured facts for Orchestrator → Reflect/Planner context."""
        with self._conn() as conn:
            cur = self._cur(conn)

            cur.execute(
                """
                SELECT date(submitted_at::timestamp) as d, overall_score
                FROM writing_submissions
                WHERE submitted_at::timestamp > NOW() - INTERVAL '7 days'
                ORDER BY submitted_at DESC
                """
            )
            writing_scores = cur.fetchall()

            cur.execute(
                """
                SELECT elem->>'issue' as issue, COUNT(*) as cnt
                FROM writing_submissions,
                     json_array_elements(chinglish_flags::json) AS elem
                WHERE submitted_at::timestamp > NOW() - INTERVAL '7 days'
                GROUP BY issue ORDER BY cnt DESC
                """
            )
            chinglish_counts = cur.fetchall()

            cur.execute("SELECT COUNT(*) as cnt FROM vocab_items")
            vocab_total = cur.fetchone()["cnt"]  # type: ignore[index]

            cur.execute(
                """
                SELECT elem as topic, COUNT(*) as cnt
                FROM articles,
                     json_array_elements_text(topic_tags::json) AS elem
                WHERE date::date > CURRENT_DATE - INTERVAL '14 days'
                GROUP BY elem ORDER BY cnt DESC
                """
            )
            topic_distribution = cur.fetchall()

            return {
                "writing_scores": [
                    {"date": r["d"], "score": r["overall_score"]} for r in writing_scores
                ],
                "chinglish_counts": [
                    {"issue": r["issue"], "count": r["cnt"]} for r in chinglish_counts
                ],
                "vocab_mastered": vocab_total,
                "topic_distribution": [
                    {"topic": r["topic"], "count": r["cnt"]} for r in topic_distribution
                ],
            }

    def get_article_for_date(self, date_str: str) -> "Article | None":
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute("SELECT * FROM articles WHERE date=%s", (date_str,))
            row = cur.fetchone()
            if row is None:
                return None
            return Article(
                id=row["id"],
                date=row["date"],
                source_url=row["source_url"],
                original_title=row["original_title"],
                full_text=row["full_text"],
                highlight_indices=_safe_json(row["highlight_indices"], []),
                article_logic=row["article_logic"],
                topic_tags=_safe_json(row["topic_tags"], []),
            )

    def query_topic_performance(self) -> dict:
        """Returns per-topic writing performance aggregated from all submissions."""
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                """
                SELECT elem as topic,
                       COUNT(*) as sessions,
                       ROUND(AVG(ws.overall_score)::numeric, 1) as avg_score
                FROM writing_submissions ws
                JOIN writing_tasks wt ON ws.task_id = wt.id
                JOIN articles a ON wt.article_id = a.id,
                     json_array_elements_text(a.topic_tags::json) AS elem
                GROUP BY elem
                ORDER BY sessions DESC
                """
            )
            rows = cur.fetchall()
            return {
                r["topic"]: {
                    "sessions": r["sessions"],
                    "avg_score": float(r["avg_score"]) if r["avg_score"] is not None else 0.0,
                }
                for r in rows
            }

    def query_writing_task_history(self) -> dict:
        """Returns per-article-logic-type writing performance from all submissions."""
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                """
                SELECT a.article_logic as logic_type,
                       COUNT(*) as count,
                       ROUND(AVG(ws.overall_score)::numeric, 1) as avg_score
                FROM writing_submissions ws
                JOIN writing_tasks wt ON ws.task_id = wt.id
                JOIN articles a ON wt.article_id = a.id
                GROUP BY a.article_logic
                """
            )
            rows = cur.fetchall()
            return {
                r["logic_type"]: {
                    "count": r["count"],
                    "avg_score": float(r["avg_score"]) if r["avg_score"] is not None else 0.0,
                }
                for r in rows
            }

    def count_sessions(self) -> int:
        """Total number of completed writing submissions."""
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute("SELECT COUNT(*) as cnt FROM writing_submissions")
            return cur.fetchone()["cnt"]  # type: ignore[index]

    def query_session_dates(self) -> list[str]:
        """Distinct ISO dates where writing was submitted, newest first."""
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                "SELECT DISTINCT date(submitted_at::timestamp) as d "
                "FROM writing_submissions ORDER BY d DESC"
            )
            rows = cur.fetchall()
            return [str(r["d"]) for r in rows]

    def count_articles(self) -> int:
        """Total number of articles stored (includes days without a submission)."""
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute("SELECT COUNT(*) as cnt FROM articles")
            return cur.fetchone()["cnt"]  # type: ignore[index]

    # ── General Learning ──────────────────────────────────────

    def create_general_project(
        self, topic: str, profile: UserGoalProfile | None, tier: str = "free"
    ) -> int:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                "INSERT INTO learning_projects"
                " (user_topic, goal_profile, tier, created_at) VALUES (%s, %s, %s, %s)"
                " RETURNING id",
                (
                    topic,
                    json.dumps(profile.model_dump()) if profile else None,
                    tier,
                    datetime.now(UTC).isoformat(),
                ),
            )
            return cur.fetchone()["id"]  # type: ignore[index]

    def list_general_projects(self) -> list[GeneralProject]:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute("SELECT * FROM learning_projects ORDER BY id DESC")
            rows = cur.fetchall()
        return [p for p in (self._parse_general_project(dict(r)) for r in rows) if p]

    def _parse_general_project(self, d: dict) -> GeneralProject | None:
        try:
            _raw = _safe_json(d["goal_profile"], None)
            d["goal_profile"] = UserGoalProfile(**_raw) if _raw else None
        except (TypeError, KeyError, ValidationError):
            d["goal_profile"] = None
        try:
            _raw = _safe_json(d["learning_map"], None)
            d["learning_map"] = LearningMap(**_raw) if _raw else None
        except (TypeError, KeyError, ValidationError):
            d["learning_map"] = None
        try:
            return GeneralProject(**d)
        except (TypeError, ValidationError):
            return None

    def get_general_project(self, project_id: int) -> GeneralProject | None:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute("SELECT * FROM learning_projects WHERE id = %s", (project_id,))
            row = cur.fetchone()
        if not row:
            return None
        return self._parse_general_project(dict(row))

    def update_general_project_status(self, project_id: int, status: str) -> None:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                "UPDATE learning_projects SET status = %s WHERE id = %s", (status, project_id)
            )

    def update_general_project_notebook(self, project_id: int, notebook_id: str) -> None:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                "UPDATE learning_projects SET notebook_id = %s WHERE id = %s",
                (notebook_id, project_id),
            )

    def update_general_project_goal_profile(
        self, project_id: int, profile: UserGoalProfile
    ) -> None:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                "UPDATE learning_projects SET goal_profile = %s WHERE id = %s",
                (profile.model_dump_json(), project_id),
            )

    def update_general_project_map(
        self, project_id: int, learning_map: LearningMap, budget_used: int
    ) -> None:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                "UPDATE learning_projects SET learning_map = %s, budget_used = %s WHERE id = %s",
                (learning_map.model_dump_json(), budget_used, project_id),
            )

    def update_general_project_profile_and_map(
        self, project_id: int, profile: UserGoalProfile, learning_map: LearningMap
    ) -> None:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                "UPDATE learning_projects SET goal_profile = %s, learning_map = %s WHERE id = %s",
                (profile.model_dump_json(), learning_map.model_dump_json(), project_id),
            )

    def upsert_general_lesson(
        self,
        project_id: int,
        chapter: int,
        lesson: int,
        title: str,
        study_guide: str,
        quiz_json: list,
        flashcards: list,
    ) -> None:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                """
                INSERT INTO project_lessons
                    (project_id, chapter, lesson, title, study_guide, quiz_json, flashcards, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'ready')
                ON CONFLICT(project_id, chapter, lesson) DO UPDATE SET
                    study_guide = excluded.study_guide,
                    quiz_json   = excluded.quiz_json,
                    flashcards  = excluded.flashcards,
                    status      = 'ready'
                """,
                (
                    project_id,
                    chapter,
                    lesson,
                    title,
                    study_guide,
                    json.dumps(quiz_json),
                    json.dumps(flashcards),
                ),
            )

    def get_project_lessons(self, project_id: int) -> list[GeneralLesson]:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                "SELECT * FROM project_lessons WHERE project_id = %s ORDER BY chapter, lesson",
                (project_id,),
            )
            rows = cur.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["quiz_json"] = _safe_json(d["quiz_json"], None)
            d["flashcards"] = _safe_json(d["flashcards"], None)
            result.append(GeneralLesson(**d))
        return result

    def get_general_lesson(self, lesson_id: int) -> GeneralLesson | None:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute("SELECT * FROM project_lessons WHERE id = %s", (lesson_id,))
            row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["quiz_json"] = _safe_json(d["quiz_json"], None)
        d["flashcards"] = _safe_json(d["flashcards"], None)
        return GeneralLesson(**d)

    def save_general_session(
        self, project_id: int, lesson_id: int, quiz_answers: list, quiz_score: int, qa_history: list
    ) -> int:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                "INSERT INTO project_sessions"
                " (project_id, lesson_id, quiz_answers, quiz_score, qa_history, created_at)"
                " VALUES (%s,%s,%s,%s,%s,%s)"
                " RETURNING id",
                (
                    project_id,
                    lesson_id,
                    json.dumps(quiz_answers),
                    quiz_score,
                    json.dumps(qa_history),
                    datetime.now(UTC).isoformat(),
                ),
            )
            return cur.fetchone()["id"]  # type: ignore[index]

    def get_project_sessions_recent(self, project_id: int, n: int) -> list[dict]:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                "SELECT * FROM project_sessions"
                " WHERE project_id = %s ORDER BY created_at DESC LIMIT %s",
                (project_id, n),
            )
            rows = cur.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["quiz_answers"] = _safe_json(d["quiz_answers"], [])
            d["qa_history"] = _safe_json(d["qa_history"], [])
            result.append(d)
        return result

    def save_general_student_model(self, project_id: int, model: GeneralStudentModel) -> None:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                """
                INSERT INTO general_student_models
                    (project_id, goal_outcome, goal_progress, dimensions, fsrs_due, updated)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT(project_id) DO UPDATE SET
                    goal_outcome  = excluded.goal_outcome,
                    goal_progress = excluded.goal_progress,
                    dimensions    = excluded.dimensions,
                    fsrs_due      = excluded.fsrs_due,
                    updated       = excluded.updated
                """,
                (
                    project_id,
                    model.goal_outcome,
                    model.goal_progress,
                    json.dumps({k: v.model_dump() for k, v in model.dimensions.items()}),
                    json.dumps(model.fsrs_due),
                    model.updated,
                ),
            )

    def get_last_session_for_lesson(self, project_id: int, lesson_id: int) -> dict | None:
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                "SELECT * FROM project_sessions"
                " WHERE project_id = %s AND lesson_id = %s"
                " ORDER BY created_at DESC LIMIT 1",
                (project_id, lesson_id),
            )
            row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["quiz_answers"] = _safe_json(d["quiz_answers"], [])
        d["qa_history"] = _safe_json(d["qa_history"], [])
        return d

    def get_general_student_model_full(self, project_id: int) -> GeneralStudentModel | None:
        from backend.models import DimensionState

        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                "SELECT * FROM general_student_models WHERE project_id = %s",
                (project_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        dimensions_raw = _safe_json(row["dimensions"], {})
        dimensions = {}
        for k, v in dimensions_raw.items():
            try:
                dimensions[k] = DimensionState(**v)
            except (TypeError, KeyError, ValidationError):
                pass
        return GeneralStudentModel(
            project_id=row["project_id"],
            goal_outcome=row["goal_outcome"],
            goal_progress=row["goal_progress"],
            dimensions=dimensions,
            fsrs_due=_safe_json(row["fsrs_due"], []),
            updated=row["updated"],
        )

    def get_general_project_dashboard(self, project_id: int) -> dict:
        project = self.get_general_project(project_id)
        if not project:
            return {}
        lessons = self.get_project_lessons(project_id)
        chapters: dict[int, dict] = {}
        for lesson in lessons:
            if lesson.chapter not in chapters:
                title = (
                    project.learning_map.chapters[lesson.chapter].title
                    if project.learning_map
                    else f"Chapter {lesson.chapter}"
                )
                chapters[lesson.chapter] = {"title": title, "lessons": []}
            chapters[lesson.chapter]["lessons"].append(lesson.model_dump())

        goal_progress = 0.0
        dimensions: dict = {}
        with self._conn() as conn:
            cur = self._cur(conn)
            cur.execute(
                "SELECT goal_progress, dimensions"
                " FROM general_student_models WHERE project_id = %s",
                (project_id,),
            )
            row = cur.fetchone()
        if row:
            goal_progress = row["goal_progress"]
            dimensions = _safe_json(row["dimensions"], {})

        return {
            "id": project.id,
            "user_topic": project.user_topic,
            "goal_outcome": project.goal_profile.goal_outcome if project.goal_profile else "",
            "goal_progress": goal_progress,
            "dimensions": dimensions,
            "chapters": list(chapters.values()),
            "tier": project.tier,
            "budget_used": project.budget_used,
        }
