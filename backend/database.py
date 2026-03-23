import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date
from typing import Protocol

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

CREATE TABLE IF NOT EXISTS learning_projects (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
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

    def upsert_reading_start(self, today: date) -> None: ...

    def create_general_project(
        self, topic: str, profile: UserGoalProfile | None, tier: str
    ) -> int: ...

    def get_general_project(self, project_id: int) -> GeneralProject | None: ...

    def update_general_project_status(self, project_id: int, status: str) -> None: ...

    def update_general_project_notebook(self, project_id: int, notebook_id: str) -> None: ...

    def update_general_project_goal_profile(
        self, project_id: int, profile: UserGoalProfile
    ) -> None: ...

    def update_general_project_map(
        self, project_id: int, learning_map: LearningMap, budget_used: int
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

    # ── General Learning ──────────────────────────────────────

    def create_general_project(
        self, topic: str, profile: UserGoalProfile | None, tier: str = "free"
    ) -> int:
        from datetime import datetime

        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO learning_projects"
                " (user_topic, goal_profile, tier, created_at) VALUES (?, ?, ?, ?)",
                (
                    topic,
                    json.dumps(profile.model_dump()) if profile else None,
                    tier,
                    datetime.utcnow().isoformat(),
                ),
            )
            return cur.lastrowid  # type: ignore

    def get_general_project(self, project_id: int) -> GeneralProject | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM learning_projects WHERE id = ?", (project_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["goal_profile"] = (
            UserGoalProfile(**json.loads(d["goal_profile"])) if d["goal_profile"] else None
        )
        d["learning_map"] = (
            LearningMap(**json.loads(d["learning_map"])) if d["learning_map"] else None
        )
        return GeneralProject(**d)

    def update_general_project_status(self, project_id: int, status: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE learning_projects SET status = ? WHERE id = ?", (status, project_id)
            )

    def update_general_project_notebook(self, project_id: int, notebook_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE learning_projects SET notebook_id = ? WHERE id = ?",
                (notebook_id, project_id),
            )

    def update_general_project_goal_profile(
        self, project_id: int, profile: UserGoalProfile
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE learning_projects SET goal_profile = ? WHERE id = ?",
                (profile.model_dump_json(), project_id),
            )

    def update_general_project_map(
        self, project_id: int, learning_map: LearningMap, budget_used: int
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE learning_projects SET learning_map = ?, budget_used = ? WHERE id = ?",
                (learning_map.model_dump_json(), budget_used, project_id),
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
            conn.execute(
                """
                INSERT INTO project_lessons
                    (project_id, chapter, lesson, title, study_guide, quiz_json, flashcards, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'ready')
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
            rows = conn.execute(
                "SELECT * FROM project_lessons WHERE project_id = ? ORDER BY chapter, lesson",
                (project_id,),
            ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["quiz_json"] = json.loads(d["quiz_json"]) if d["quiz_json"] else None
            d["flashcards"] = json.loads(d["flashcards"]) if d["flashcards"] else None
            result.append(GeneralLesson(**d))
        return result

    def get_general_lesson(self, lesson_id: int) -> GeneralLesson | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM project_lessons WHERE id = ?", (lesson_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["quiz_json"] = json.loads(d["quiz_json"]) if d["quiz_json"] else None
        d["flashcards"] = json.loads(d["flashcards"]) if d["flashcards"] else None
        return GeneralLesson(**d)

    def save_general_session(
        self, project_id: int, lesson_id: int, quiz_answers: list, quiz_score: int, qa_history: list
    ) -> int:
        from datetime import datetime

        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO project_sessions"
                " (project_id, lesson_id, quiz_answers, quiz_score, qa_history, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (
                    project_id,
                    lesson_id,
                    json.dumps(quiz_answers),
                    quiz_score,
                    json.dumps(qa_history),
                    datetime.utcnow().isoformat(),
                ),
            )
            return cur.lastrowid  # type: ignore

    def get_project_sessions_recent(self, project_id: int, n: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM project_sessions"
                " WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                (project_id, n),
            ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["quiz_answers"] = json.loads(d["quiz_answers"]) if d["quiz_answers"] else []
            d["qa_history"] = json.loads(d["qa_history"]) if d["qa_history"] else []
            result.append(d)
        return result

    def save_general_student_model(self, project_id: int, model: GeneralStudentModel) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO general_student_models
                    (project_id, goal_outcome, goal_progress, dimensions, fsrs_due, updated)
                VALUES (?, ?, ?, ?, ?, ?)
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
        return {
            "id": project.id,
            "user_topic": project.user_topic,
            "goal_outcome": project.goal_profile.goal_outcome if project.goal_profile else "",
            "goal_progress": 0.0,
            "dimensions": {},
            "chapters": list(chapters.values()),
            "tier": project.tier,
            "budget_used": project.budget_used,
        }
