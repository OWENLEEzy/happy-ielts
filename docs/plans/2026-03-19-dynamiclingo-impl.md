# DynamicLingo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local AI read-write flywheel for English learning: daily article scraping → full-text immersive reading with AI highlights → writing task → spaced-repetition vocab review.

**Architecture:** Two decoupled loops share a SQLite database. Slow loop (DeepAgent Planner) runs in background to scrape + annotate articles. Fast loop (LangGraph Tutor) handles real-time SSE interactions with the user. Frontend is Next.js proxying to FastAPI.

**Tech Stack:** Python 3.12 / uv / FastAPI / LangGraph / DeepAgents / LangChain-Anthropic / py-fsrs / Scrapling / Playwright / SQLite / Next.js 14 / TypeScript / shadcn/ui / SWR

---

## Task 1: Python Backend Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `Taskfile.yml`
- Create: `.env.example`
- Create: `backend/__init__.py`
- Create: `backend/main.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "dynamiclingo-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "langchain>=1.0,<2.0",
    "langchain-core>=1.0,<2.0",
    "langsmith>=0.3.4",
    "langgraph>=1.0,<2.0",
    "langgraph-checkpoint-sqlite",
    "deepagents",
    "langchain-anthropic",
    "langchain-tavily",
    "fastapi[standard]",
    "uvicorn[standard]",
    "scrapling",
    "playwright",
    "py-fsrs",
    "python-dotenv",
]

[project.optional-dependencies]
dev = [
    "langsmith[pytest]",
    "pytest",
    "pytest-asyncio",
    "pre-commit",
    "mypy",
    "ruff",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true
disallow_untyped_defs = false
warn_return_any = false
check_untyped_defs = true
exclude = ["frontend/", ".venv/"]

[[tool.mypy.overrides]]
module = "backend.models"
disallow_untyped_defs = true
```

**Step 2: Create Taskfile.yml**

```yaml
version: '3'

tasks:
  dev:backend:
    cmd: uv run uvicorn backend.main:app --reload --port 8000

  dev:frontend:
    cmd: cd frontend && npm run dev

  generate-types:
    desc: "Run after models.py changes to sync TS types"
    cmds:
      - uv run uvicorn backend.main:app --port 8001 &
      - sleep 2
      - npx openapi-typescript http://localhost:8001/openapi.json -o frontend/types/api.ts
      - kill %1

  check:python:
    cmds:
      - uv run ruff check backend/
      - uv run ruff format --check backend/
      - uv run mypy backend/

  check:frontend:
    cmds:
      - cd frontend && npx eslint .
      - cd frontend && npx tsc --noEmit

  check:
    cmds: [task: check:python, task: check:frontend]

  fix:
    cmds:
      - uv run ruff check --fix backend/
      - uv run ruff format backend/
      - cd frontend && npx eslint . --fix
      - cd frontend && npx prettier --write .

  install-hooks:
    cmds:
      - uv run pre-commit install
      - uv run pre-commit install --hook-type commit-msg
      - cd frontend && npx husky init
      - echo "npx lint-staged" > frontend/.husky/pre-commit

  test:
    cmd: uv run pytest backend/tests/ -v
```

**Step 3: Create .env.example**

```bash
# Copy to .env and fill in real values
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=ls-...
LANGSMITH_PROJECT=dynamiclingo
```

**Step 4: Create backend/main.py (bare app + lifespan)**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # H3 fix: 创建全局共享 checkpointer 单例，setup() 只调用一次
    from langgraph.checkpoint.sqlite import SqliteSaver
    with SqliteSaver.from_conn_string("./db.sqlite3") as cp:
        cp.setup()
        app.state.checkpointer = cp
        yield
    # with 块退出时自动关闭连接


app = FastAPI(title="DynamicLingo API", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 5: Install deps and verify**

```bash
uv sync
uv run uvicorn backend.main:app --port 8000
# Visit http://localhost:8000/health — expect {"status": "ok"}
```

**Step 6: Commit**

```bash
git add pyproject.toml Taskfile.yml .env.example backend/
git commit -m "chore: scaffold Python backend with FastAPI and uv"
```

---

## Task 2: Frontend Scaffold

**Files:**
- Create: `frontend/` (Next.js project)
- Create: `frontend/.env.local`
- Create: `frontend/.prettierrc`

**Step 1: Initialize Next.js**

```bash
cd /path/to/language-teacher
npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --no-src-dir \
  --import-alias "@/*"
```

**Step 2: Install frontend dependencies**

```bash
cd frontend
npm install swr framer-motion react-hook-form zod date-fns
npx shadcn@latest init
# Choose: Default style, slate base color, CSS variables: yes
npm install -D @typescript-eslint/parser eslint-plugin-react-hooks \
  openapi-typescript lint-staged husky commitizen
```

**Step 3: Create frontend/.env.local**

```bash
BACKEND_URL=http://localhost:8000
```

**Step 4: Create frontend/.prettierrc**

```json
{ "semi": false, "singleQuote": true, "trailingComma": "all", "printWidth": 100 }
```

**Step 5: Create Next.js API proxy — `frontend/app/api/[...proxy]/route.ts`**

```typescript
import { NextRequest } from 'next/server'

const BACKEND = process.env.BACKEND_URL ?? 'http://localhost:8000'

export async function GET(req: NextRequest, { params }: { params: { proxy: string[] } }) {
  const path = params.proxy.join('/')
  return fetch(`${BACKEND}/api/${path}`)
}

export async function POST(req: NextRequest, { params }: { params: { proxy: string[] } }) {
  const path = params.proxy.join('/')
  return fetch(`${BACKEND}/api/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: await req.text(),
  })
}

export async function PATCH(req: NextRequest, { params }: { params: { proxy: string[] } }) {
  const path = params.proxy.join('/')
  return fetch(`${BACKEND}/api/${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: await req.text(),
  })
}
```

**Step 6: Verify frontend starts**

```bash
cd frontend && npm run dev
# Visit http://localhost:3000 — expect Next.js default page
```

**Step 7: Commit**

```bash
git add frontend/
git commit -m "chore: scaffold Next.js frontend with proxy and shadcn"
```

---

## Task 3: Pydantic Models + SQLite Schema

**Files:**
- Create: `backend/models.py`
- Create: `backend/database.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_database.py`

**Step 1: Write failing test first**

```python
# backend/tests/test_database.py
import pytest
from datetime import date
from backend.database import Database
from backend.models import UserProfile, ArticleCreate, WritingTaskCreate, VocabItemCreate


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
        full_text="Para one.\n\nPara two.\n\nPara three.",
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
        fsrs_state={"due": date.today().isoformat(), "stability": 1.0,
                    "difficulty": 5.0, "reps": 0, "lapses": 0, "state": 0,
                    "last_review": None},
        article_id=None,
    )
    db.upsert_vocab_item(item)
    due = db.get_due_vocab_items(date.today())
    assert len(due) == 1
    assert due[0].word == "leverage"
```

**Step 2: Run test — expect FAIL (ModuleNotFoundError)**

```bash
uv run pytest backend/tests/test_database.py -v
# Expected: FAILED — backend.database not found
```

**Step 3: Create backend/models.py**

```python
from __future__ import annotations
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl


class UserProfile(BaseModel):
    goal: str
    interests: list[str]
    level: int = Field(ge=1, le=10)
    bandwidth_minutes: int
    writing_mode: Literal["professional", "ielts", "both"]


class ArticleCreate(BaseModel):
    date: str
    source_url: str
    original_title: str
    full_text: str = Field(min_length=100)
    highlight_indices: list[int] = Field(min_length=2, max_length=5)
    article_logic: Literal["compare", "cause_effect", "argumentation"]
    topic_tags: list[str] = Field(min_length=1, max_length=5)


class Article(ArticleCreate):
    id: int


class WritingTaskCreate(BaseModel):
    article_id: int
    mode: Literal["professional", "ielts_task1", "ielts_task2"]
    instruction: str = Field(min_length=50)
    min_words: int = Field(ge=50, le=250)


class WritingTask(WritingTaskCreate):
    id: int


class ChinglishFlag(BaseModel):
    original: str
    issue: Literal["word_choice", "sentence_structure", "logic_connector"]
    explanation_zh: str
    native_alternative: str


class GrammarError(BaseModel):
    original: str
    correction: str
    explanation_zh: str


class WritingFeedback(BaseModel):
    overall_score: int = Field(ge=1, le=10)
    grammar_errors: list[GrammarError]
    chinglish_flags: list[ChinglishFlag]
    rewrite_suggestions: list[str]


class WritingSubmissionCreate(BaseModel):
    task_id: int
    user_text: str
    overall_score: int
    grammar_errors: list[GrammarError]
    chinglish_flags: list[ChinglishFlag]
    rewrite_suggestions: list[str]
    submitted_at: datetime


class VocabItemCreate(BaseModel):
    word: str
    context_sentence: str
    source: Literal["reading_click", "writing_error"]
    next_review: str  # ISO date string
    fsrs_state: dict
    article_id: int | None


class VocabItem(VocabItemCreate):
    id: int
```

**Step 4: Create backend/database.py**

```python
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
        self._init_tables()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

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
```

**Step 5: Run tests — expect PASS**

```bash
uv run pytest backend/tests/test_database.py -v
# Expected: 3 PASSED
```

**Step 6: Commit**

```bash
git add backend/models.py backend/database.py backend/tests/
git commit -m "feat: add Pydantic models and SQLite database layer"
```

---

## Task 4: FSRS Engine

**Files:**
- Create: `backend/fsrs_engine.py`
- Create: `backend/tests/test_fsrs_engine.py`

**Step 1: Write failing tests**

```python
# backend/tests/test_fsrs_engine.py
import pytest
from datetime import date, timedelta
from backend.fsrs_engine import (
    new_card_state,
    update_card,
    map_answer_to_rating,
    serialize_card,
    deserialize_card,
)


def test_new_card_state_is_valid_dict():
    state = new_card_state()
    assert "due" in state
    assert "stability" in state
    assert "state" in state  # 0 = New


def test_correct_fast_answer_gives_easy_rating():
    state = new_card_state()
    new_state = update_card(state, is_correct=True, response_seconds=2.0)
    # After Easy on new card, next review should be > today
    next_review = date.fromisoformat(new_state["due"][:10])
    assert next_review > date.today()


def test_wrong_answer_gives_again_rating():
    state = new_card_state()
    new_state = update_card(state, is_correct=False, response_seconds=5.0)
    # After Again, card goes back to Learning — due date is very soon
    next_review = date.fromisoformat(new_state["due"][:10])
    assert next_review <= date.today() + timedelta(days=1)


def test_serialize_deserialize_roundtrip():
    state = new_card_state()
    updated = update_card(state, is_correct=True, response_seconds=3.0)
    assert isinstance(updated, dict)
    assert isinstance(updated["due"], str)
    assert isinstance(updated["stability"], float)


def test_map_answer_to_rating():
    from fsrs import Rating
    assert map_answer_to_rating(False, 5.0) == Rating.Again
    assert map_answer_to_rating(True, 20.0) == Rating.Hard
    assert map_answer_to_rating(True, 10.0) == Rating.Good
    assert map_answer_to_rating(True, 2.0) == Rating.Easy
```

**Step 2: Run test — expect FAIL**

```bash
uv run pytest backend/tests/test_fsrs_engine.py -v
# Expected: FAILED — backend.fsrs_engine not found
```

**Step 3: Implement backend/fsrs_engine.py**

```python
from datetime import datetime, timezone
from fsrs import FSRS, Card, Rating


_scheduler = FSRS()


def new_card_state() -> dict:
    """Create a serialized state for a brand-new vocab card."""
    card = Card()
    return serialize_card(card)


def map_answer_to_rating(is_correct: bool, response_seconds: float) -> Rating:
    if not is_correct:
        return Rating.Again
    if response_seconds > 15:
        return Rating.Hard
    elif response_seconds > 5:
        return Rating.Good
    else:
        return Rating.Easy


def update_card(fsrs_state: dict, is_correct: bool, response_seconds: float) -> dict:
    """Apply a review result to an existing card state. Returns new state dict."""
    card = deserialize_card(fsrs_state)
    rating = map_answer_to_rating(is_correct, response_seconds)
    card, _ = _scheduler.review_card(card, rating)
    return serialize_card(card)


def serialize_card(card: Card) -> dict:
    return {
        "due": card.due.isoformat(),
        "stability": card.stability,
        "difficulty": card.difficulty,
        "reps": card.reps,
        "lapses": card.lapses,
        "state": card.state.value,
        "last_review": card.last_review.isoformat() if card.last_review else None,
    }


def deserialize_card(data: dict) -> Card:
    from fsrs import State
    card = Card()
    card.due = datetime.fromisoformat(data["due"])
    card.stability = data["stability"]
    card.difficulty = data["difficulty"]
    card.reps = data["reps"]
    card.lapses = data["lapses"]
    card.state = State(data["state"])
    if data.get("last_review"):
        card.last_review = datetime.fromisoformat(data["last_review"])
    return card
```

**Step 4: Run tests — expect PASS**

```bash
uv run pytest backend/tests/test_fsrs_engine.py -v
# Expected: 5 PASSED
```

**Step 5: Commit**

```bash
git add backend/fsrs_engine.py backend/tests/test_fsrs_engine.py
git commit -m "feat: add py-fsrs engine with rating mapping and card serialization"
```

---

## Task 5: DeepAgent Planner Tools

**Files:**
- Create: `backend/planner/__init__.py`
- Create: `backend/planner/tools.py`
- Create: `backend/tests/test_planner_tools.py`

**Step 1: Write failing test for scrape_article mock**

```python
# backend/tests/test_planner_tools.py
import pytest
from unittest.mock import patch, MagicMock
from backend.planner.tools import scrape_article


def test_scrape_article_returns_text_on_success():
    mock_page = MagicMock()
    mock_page.get_best_text.return_value = "This is the article body text."

    mock_scraper = MagicMock()
    mock_scraper.get.return_value = mock_page

    with patch("backend.planner.tools.Scraper", return_value=mock_scraper):
        result = scrape_article.invoke({"url": "https://example.com/article"})

    assert "article body text" in result
    assert len(result) > 10


def test_scrape_article_falls_back_on_exception():
    """When Scrapling raises, the tool should not crash (Playwright fallback handled)."""
    with patch("backend.planner.tools.Scraper") as mock_cls:
        mock_cls.return_value.get.side_effect = Exception("blocked")
        # Playwright fallback also mocked to avoid network calls in tests
        with patch("backend.planner.tools._playwright_scrape", return_value="fallback text"):
            result = scrape_article.invoke({"url": "https://example.com/article"})
    assert result == "fallback text"
```

**Step 2: Run test — expect FAIL**

```bash
uv run pytest backend/tests/test_planner_tools.py -v
```

**Step 3: Create backend/planner/tools.py**

```python
import asyncio
import json
import logging
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl
from langchain.tools import tool
from langchain_anthropic import ChatAnthropic

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
        from scrapling import Scraper
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
    # C1 fix: use with_structured_output — same pattern as highlight_key_paragraphs
    result = _llm.with_structured_output(WritingTaskCreate).invoke(prompt)
    return result.model_dump()


@tool
def save_daily_lesson(article: ArticleCreate, task: WritingTaskCreate) -> str:
    """Save today's article and writing task to the database. Call as the final step."""
    # C2 fix: accept typed Pydantic models — LangChain enforces schema before body executes
    article = article.model_copy(update={"date": date.today().isoformat()})
    article_id = _db.upsert_article(article)

    task = task.model_copy(update={"article_id": article_id})
    _db.upsert_writing_task(task)

    return f"Saved: '{article.original_title}'"
```

**Step 4: Run tests — expect PASS**

```bash
uv run pytest backend/tests/test_planner_tools.py -v
# Expected: 2 PASSED
```

**Step 5: Commit**

```bash
git add backend/planner/ backend/tests/test_planner_tools.py
git commit -m "feat: add DeepAgent Planner tools (scrape, highlight, generate, save)"
```

---

## Task 6: DeepAgent Planner Agent + FastAPI Routes

**Files:**
- Create: `backend/planner/agent.py`
- Modify: `backend/main.py`

**Step 1: Create backend/planner/agent.py**

```python
from datetime import date
from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.sqlite import SqliteSaver

from backend.planner.tools import (
    load_user_profile,
    scrape_article,
    highlight_key_paragraphs,
    generate_writing_task,
    save_daily_lesson,
)

# Search tool from dedicated package
from langchain_tavily import TavilySearch

search_articles = TavilySearch(max_results=3)

PLANNER_SYSTEM_PROMPT = """
你是一个语言学习内容策划师。
根据用户的兴趣和职业目标，每天为他选择一篇真实的英文文章，
标注最核心的 3-5 个段落（用于前端高亮深读），识别文章底层逻辑类型，
并生成一个针对其目标的微型写作任务。
优先选择时效性强、与用户当前项目直接相关的内容。

完成目标：读取用户画像 → 搜索并抓取相关文章 → 标注核心段落和逻辑类型 →
生成写作任务 → 调用 save_daily_lesson 存库（必须最后调用）。
"""

# H1 fix: system prompt 改为目标导向（prose），避免与 write_todos 中间件的步骤列表冲突

_planner: object | None = None  # H3 fix: singleton，避免每次请求泄漏连接


def get_planner(checkpointer):
    global _planner
    if _planner is None:
        _planner = create_deep_agent(
            model=init_chat_model("anthropic:claude-haiku-4-5-20251001"),
            tools=[
                load_user_profile,
                search_articles,
                scrape_article,
                highlight_key_paragraphs,
                generate_writing_task,
                save_daily_lesson,
            ],
            system_prompt=PLANNER_SYSTEM_PROMPT,
            checkpointer=checkpointer,  # H3: 由 main.py lifespan 传入共享实例
        )
    return _planner


def get_planner_config():
    return {"configurable": {"thread_id": f"planner-{date.today().isoformat()}"}}
```

**Step 2: Add planner routes to backend/main.py**

Add these imports and routes to the existing `main.py`:

```python
# Add to backend/main.py imports
from fastapi import BackgroundTasks
from datetime import date

# Add route: POST /api/planner/run
@app.post("/api/planner/run")
async def run_planner(background_tasks: BackgroundTasks):
    from backend.planner.agent import get_planner, get_planner_config
    # H3 fix: 传入 lifespan 创建的共享 checkpointer（app.state.checkpointer）
    planner = get_planner(app.state.checkpointer)
    config = get_planner_config()
    background_tasks.add_task(
        planner.ainvoke,
        {"messages": [{"role": "user", "content": "为今天准备一节课"}]},
        config,
    )
    return {"status": "started", "date": date.today().isoformat()}


# Add route: GET /api/planner/status
@app.get("/api/planner/status")
async def planner_status():
    from backend.database import Database
    db = Database()
    article = db.get_today_article()
    task = db.get_today_writing_task()
    return {"ready": article is not None and task is not None}
```

**Step 3: Manual smoke test**

```bash
# Terminal 1: start backend
uv run uvicorn backend.main:app --reload --port 8000

# Terminal 2: trigger planner
curl -X POST http://localhost:8000/api/planner/run
# Expect: {"status": "started", "date": "2026-03-19"}

# Wait ~60s then check status
curl http://localhost:8000/api/planner/status
# Expect: {"ready": true}
```

**Step 4: Commit**

```bash
git add backend/planner/agent.py backend/main.py
git commit -m "feat: add DeepAgent Planner with FastAPI planner routes"
```

---

## Task 7: LangGraph Tutor Tools

**Files:**
- Create: `backend/tutor/__init__.py`
- Create: `backend/tutor/tools.py`

**Step 1: Create backend/tutor/tools.py**

```python
import logging
from langchain.tools import tool
from langchain_anthropic import ChatAnthropic
from backend.models import WritingFeedback, WritingTask

logger = logging.getLogger(__name__)

_llm = ChatAnthropic(model="claude-haiku-4-5-20251001")

FEEDBACK_PROMPT = """
You are a native English editor reviewing writing from a Chinese professional.

Source article topic: {article_topic}
Writer's goal: {user_goal}
Writer's level: {level}/10

PASS 1 — Grammar: Find objective errors (tense, agreement, articles).
PASS 2 — Native fluency: Find phrases where Chinese L1 is showing through.
  Ask: "Would a native speaker in this professional context phrase it this way?"
  Focus on: verb weakening (using "have" instead of strong verbs), logic connectors,
            sentence rhythm.
  Do NOT flag correct-but-non-native as grammar errors.

IMPORTANT: Only flag the 1-2 most severe issues. Do not overwhelm the learner.
Include exactly 2 rewrite_suggestions (complete rewrites of the full text).
Be encouraging — start with what's good.

Return valid JSON matching the WritingFeedback schema exactly. No prose outside JSON.

User's writing:
{user_text}
"""


@tool
def explain_word(word: str, context: str, level: int) -> str:
    """Explain a word in context for a language learner at the given level (1-10)."""
    prompt = f"""
Explain the word "{word}" as used in this sentence:
"{context}"

The learner is level {level}/10. Adjust depth accordingly:
- Level 1-3: simple definition + 1 example
- Level 4-6: definition + usage nuance + 1 native collocation
- Level 7-10: usage nuance + register note + comparison with synonyms

Respond in Chinese (简体中文). Keep it under 100 words.
"""
    response = _llm.invoke(prompt)
    return response.content


@tool
def analyze_sentence(sentence: str) -> str:
    """Break down a complex English sentence into its grammatical structure."""
    prompt = f"""
Analyze this English sentence for a Chinese learner:
"{sentence}"

Identify: main clause, subordinate clauses, subject/verb/object, and any difficult structures.
Use color labels in your response like [主语], [谓语], [宾语], [从句].
Explain in Chinese (简体中文). Keep it under 150 words.
"""
    response = _llm.invoke(prompt)
    return response.content


def run_feedback(user_text: str, task: WritingTask, user_goal: str, level: int) -> WritingFeedback:
    """Run structured writing feedback. Retries up to 3 times on parse failure."""
    structured_llm = _llm.with_structured_output(WritingFeedback, include_raw=True)
    prompt = FEEDBACK_PROMPT.format(
        article_topic=task.instruction[:100],
        user_goal=user_goal,
        level=level,
        user_text=user_text,
    )
    for attempt in range(3):
        result = structured_llm.invoke(prompt)
        if result["parsed"] is not None:
            return result["parsed"]
        logger.warning(f"Feedback attempt {attempt + 1} failed: {result['raw']}")
    raise ValueError("Feedback generation failed after 3 attempts")
```

**Step 2: Commit**

```bash
git add backend/tutor/
git commit -m "feat: add LangGraph Tutor tools (explain_word, analyze_sentence, run_feedback)"
```

---

## Task 8: LangGraph Tutor Graph + Nodes

**Files:**
- Create: `backend/tutor/nodes.py`
- Create: `backend/tutor/graph.py`
- Create: `backend/tests/test_tutor_routing.py`

**Step 1: Write failing routing test**

```python
# backend/tests/test_tutor_routing.py
import pytest
from unittest.mock import patch, MagicMock
from datetime import date


def test_route_start_goes_to_review_when_due_items_exist():
    """route_start should return Command(goto='spaced_review') when vocab is due."""
    from backend.tutor.nodes import route_start
    from backend.models import VocabItem

    due_item = VocabItem(
        id=1, word="leverage", context_sentence="We leverage this.",
        source="reading_click", next_review=date.today().isoformat(),
        fsrs_state={}, article_id=None,
    )

    with patch("backend.tutor.nodes._db") as mock_db:
        mock_db.get_due_vocab_items.return_value = [due_item]
        state = {
            "user_profile": None, "today_article": None, "today_task": None,
            "review_queue": [], "review_index": 0,
            "user_writing": None, "messages": [],
        }
        result = route_start(state)

    assert result.goto == "spaced_review"
    assert len(result.update["review_queue"]) == 1


def test_route_start_goes_to_reading_when_no_due_items():
    """route_start should return Command(goto='reading') when no vocab is due."""
    from backend.tutor.nodes import route_start

    with patch("backend.tutor.nodes._db") as mock_db:
        mock_db.get_due_vocab_items.return_value = []
        state = {
            "user_profile": None, "today_article": None, "today_task": None,
            "review_queue": [], "review_index": 0,
            "user_writing": None, "messages": [],
        }
        result = route_start(state)

    assert result.goto == "reading"
```

**Step 2: Run test — expect FAIL**

```bash
uv run pytest backend/tests/test_tutor_routing.py -v
```

**Step 3: Create backend/tutor/nodes.py**

```python
from __future__ import annotations
import json
import logging
from datetime import date, datetime
from typing import Literal

from langgraph.types import Command, interrupt
from langgraph.config import get_stream_writer

from backend.database import Database
from backend.fsrs_engine import update_card, map_answer_to_rating, new_card_state
from backend.models import VocabItemCreate
from backend.tutor.tools import explain_word, analyze_sentence, run_feedback

logger = logging.getLogger(__name__)
_db = Database()


def route_start(state: dict) -> Command[Literal["spaced_review", "reading"]]:
    """Load profile + article + task, then route based on due vocab."""
    profile = _db.get_user_profile()
    article = _db.get_today_article()
    task = _db.get_today_writing_task()
    due_items = _db.get_due_vocab_items(date.today())

    updates = {
        "user_profile": profile,
        "today_article": article,
        "today_task": task,
    }

    if due_items:
        updates["review_queue"] = due_items
        updates["review_index"] = 0
        return Command(update=updates, goto="spaced_review")

    return Command(update=updates, goto="reading")


def spaced_review(state: dict) -> Command[Literal["spaced_review", "reading"]]:
    """Present one fill-blank card; loop until all done."""
    item = state["review_queue"][state["review_index"]]

    user_answer = interrupt({
        "type": "fill_blank",
        "question": f"Fill in the blank: {item.context_sentence.replace(item.word, '______')}",
        "word": item.word,
    })

    is_correct = user_answer.get("answer", "").strip().lower() == item.word.lower()
    response_seconds = user_answer.get("response_seconds", 10.0)

    new_state = update_card(item.fsrs_state, is_correct, response_seconds)
    new_next_review = new_state["due"][:10]

    updated_item = VocabItemCreate(
        word=item.word,
        context_sentence=item.context_sentence,
        source=item.source,
        next_review=new_next_review,
        fsrs_state=new_state,
        article_id=item.article_id,
    )
    _db.upsert_vocab_item(updated_item)

    next_index = state["review_index"] + 1
    if next_index < len(state["review_queue"]):
        return Command(update={"review_index": next_index}, goto="spaced_review")
    return Command(goto="reading")


def reading_session(state: dict) -> Command[Literal["writing_task"]]:
    """Loop: wait for user actions (explain_word, analyze_sentence, done_reading)."""
    _db.upsert_reading_start(date.today())

    while True:
        user_action = interrupt({
            "type": "awaiting_action",
            "article_full_text": state["today_article"].full_text if state["today_article"] else "",
            "highlight_indices": state["today_article"].highlight_indices if state["today_article"] else [],
            "user_level": state["user_profile"].level if state["user_profile"] else 5,
        })

        writer = get_stream_writer()
        action_type = user_action.get("type")

        if action_type == "explain_word":
            result = explain_word.invoke({
                "word": user_action["word"],
                "context": user_action.get("context", ""),
                "level": state["user_profile"].level if state["user_profile"] else 5,
            })
            # Auto-save to vocab
            if state["today_article"]:
                _db.upsert_vocab_item(VocabItemCreate(
                    word=user_action["word"],
                    context_sentence=user_action.get("context", ""),
                    source="reading_click",
                    next_review=date.today().isoformat(),
                    fsrs_state=new_card_state(),  # C4 fix: 用 fsrs_engine.new_card_state()
                    article_id=state["today_article"].id,
                ))
            writer({"type": "word_explanation", "result": result})

        elif action_type == "analyze_sentence":
            result = analyze_sentence.invoke({"sentence": user_action["sentence"]})
            writer({"type": "sentence_analysis", "result": result})

        elif action_type == "done_reading":
            break

    return Command(goto="writing_task")


def writing_task(state: dict) -> dict:
    """Present writing task and wait for submission."""
    task = state["today_task"]
    user_action = interrupt({
        "type": "writing_task",
        "instruction": task.instruction if task else "",
        "min_words": task.min_words if task else 50,
    })
    return {"user_writing": user_action.get("text", "")}


def evaluate_writing(state: dict) -> dict:
    """Run AI feedback on the user's writing."""
    writer = get_stream_writer()
    profile = state["user_profile"]
    task = state["today_task"]
    user_text = state.get("user_writing", "")

    if not user_text or not task or not profile:
        writer({"type": "error", "message": "Missing writing or task context"})
        return {}

    feedback = run_feedback(
        user_text=user_text,
        task=task,
        user_goal=profile.goal,
        level=profile.level,
    )
    writer({"type": "feedback", "result": feedback.model_dump()})
    # C3 fix: 将 feedback 存入 state，供 save_results 使用
    return {
        "writing_feedback": feedback,
        "messages": [{"role": "assistant", "content": f"Score: {feedback.overall_score}/10"}],
    }


def save_results(state: dict) -> dict:
    """Persist submission and update vocab from writing errors."""
    # C3 fix: 实际持久化，驱动 写作错误→生词本 飞轮
    from backend.models import WritingSubmissionCreate
    from datetime import datetime
    feedback = state.get("writing_feedback")
    task = state.get("today_task")
    user_text = state.get("user_writing", "")
    if feedback and task and user_text:
        sub = WritingSubmissionCreate(
            task_id=task.id,
            user_text=user_text,
            overall_score=feedback.overall_score,
            grammar_errors=feedback.grammar_errors,
            chinglish_flags=feedback.chinglish_flags,
            rewrite_suggestions=feedback.rewrite_suggestions,
            submitted_at=datetime.now(),
        )
        _db.save_writing_submission(sub)
        # 将 chinglish_flags 词汇自动加入生词本（写作错误→复习飞轮）
        article_id = state["today_article"].id if state["today_article"] else None
        for flag in feedback.chinglish_flags:
            _db.upsert_vocab_item(VocabItemCreate(
                word=flag.original,
                context_sentence=flag.original,
                source="writing_error",
                next_review=date.today().isoformat(),
                fsrs_state=new_card_state(),
                article_id=article_id,
            ))
    return {"user_writing": None, "writing_feedback": None}
```

**Step 4: Run routing tests — expect PASS**

```bash
uv run pytest backend/tests/test_tutor_routing.py -v
# Expected: 2 PASSED
```

**Step 5: Create backend/tutor/graph.py**

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import Annotated
from typing_extensions import TypedDict
import operator

from backend.tutor.nodes import (
    route_start, spaced_review, reading_session,
    writing_task, evaluate_writing, save_results,
)


class TutorState(TypedDict):
    user_profile: object | None
    today_article: object | None
    today_task: object | None
    review_queue: list
    review_index: int
    user_writing: str | None
    writing_feedback: object | None  # C3 fix: evaluate_writing → save_results 传递
    messages: Annotated[list, operator.add]


def build_tutor_graph(checkpointer):
    # H3 fix: checkpointer 由 main.py lifespan 传入，不在此处新建连接
    return (
        StateGraph(TutorState)
        .add_node("route_start", route_start)
        .add_node("spaced_review", spaced_review)
        .add_node("reading", reading_session)
        .add_node("writing_task", writing_task)
        .add_node("evaluate_writing", evaluate_writing)
        .add_node("save_results", save_results)
        .add_edge(START, "route_start")
        # reading → writing_task via Command only (no static edge to avoid double execution)
        .add_edge("writing_task", "evaluate_writing")
        .add_edge("evaluate_writing", "save_results")
        .add_edge("save_results", END)
        .compile(checkpointer=checkpointer)
    )


_graph = None


def get_tutor_graph(checkpointer=None):
    global _graph
    if _graph is None:
        _graph = build_tutor_graph(checkpointer)
    return _graph
```

**Step 6: Commit**

```bash
git add backend/tutor/ backend/tests/test_tutor_routing.py
git commit -m "feat: add LangGraph Tutor graph with nodes and routing"
```

---

## Task 9: Tutor FastAPI Routes + Onboarding

**Files:**
- Create: `backend/onboarding/__init__.py`
- Create: `backend/onboarding/agent.py`
- Modify: `backend/main.py`

**Step 1: Create backend/onboarding/agent.py**

```python
from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langgraph.checkpoint.sqlite import SqliteSaver

from backend.database import Database
from backend.models import UserProfile

_db = Database()


@tool
def save_partial_profile(
    goal: str,
    interests: list[str],
    level: int,
) -> str:
    """Save initial profile fields after AI conversation (phases 1-3). Frontend handles phases 4-5."""
    from backend.models import UserProfile
    # Save with defaults; will be updated after UI card selection
    profile = UserProfile(
        goal=goal,
        interests=interests,
        level=level,
        bandwidth_minutes=25,   # default, updated by UI
        writing_mode="professional",  # default, updated by UI
    )
    _db.upsert_user_profile(profile)
    return f"Saved profile for level-{level} learner with goal: {goal}"


ONBOARDING_PROMPT = """
你是一位温和的语言学习顾问，正在为用户做入学评估。
通过自然对话（不超过 6 轮）完成以下收集：

1. goal（学习目标）：具体的应用场景，追问直到足够具体
   例："读英文文档" → "读哪类文档？" → "TypeScript 官方文档和 RFC"
2. interests（兴趣关键词）：3-5 个，用于指导文章抓取
3. level（英文水平 1-10）：请用户写 2-3 句英文，通过语法错误频率和词汇复杂度隐式判断，
   不要直接问"你几级"

收集完 1-3 后调用 save_partial_profile 工具。
调用后告知用户："好的，马上为你选择每日时长和写作目标（最后两步由你在卡片上点选）。"

对话语气：专业、温和、简洁，不要过度热情。
"""


def create_onboarding_agent(checkpointer):
    # H3 fix: checkpointer 由 main.py lifespan 传入，不在此处新建连接
    return create_deep_agent(
        model=init_chat_model("anthropic:claude-haiku-4-5-20251001"),
        tools=[save_partial_profile],  # H2 fix: update_profile_preferences 已删除（死代码）
        checkpointer=checkpointer,
        system_prompt=ONBOARDING_PROMPT,
    )


ONBOARDING_CONFIG = {"configurable": {"thread_id": "onboarding"}}
```

**Step 2: Add all remaining routes to backend/main.py**

```python
# Add to backend/main.py

import json
from fastapi.responses import StreamingResponse
from fastapi import HTTPException
from langgraph.types import Command
from datetime import date

# ─── Onboarding ───────────────────────────────────────────────────────────

@app.post("/api/onboarding/message")
async def onboarding_message(body: dict):
    from backend.onboarding.agent import create_onboarding_agent, ONBOARDING_CONFIG
    agent = create_onboarding_agent()

    async def generate():
        async for chunk in agent.astream(
            {"messages": [{"role": "user", "content": body.get("message", "")}]},
            config=ONBOARDING_CONFIG,
            stream_mode="messages",
        ):
            token, _ = chunk
            if hasattr(token, "content") and token.content:
                yield f"data: {json.dumps({'type': 'token', 'content': token.content})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/onboarding/status")
async def onboarding_status():
    from backend.database import Database
    db = Database()
    profile = db.get_user_profile()
    return {"ready": profile is not None}


@app.post("/api/onboarding/preferences")
async def save_preferences(body: dict):
    from backend.database import Database
    db = Database()
    profile = db.get_user_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    updated = profile.model_copy(update={
        "bandwidth_minutes": body.get("bandwidth_minutes", 25),
        "writing_mode": body.get("writing_mode", "professional"),
    })
    db.upsert_user_profile(updated)
    return {"status": "ok"}


# ─── Lesson ───────────────────────────────────────────────────────────────

@app.get("/api/lesson/today")
async def get_today_lesson():
    from backend.database import Database
    db = Database()
    article = db.get_today_article()
    task = db.get_today_writing_task()
    if article is None or task is None:
        raise HTTPException(status_code=404, detail="Today's lesson not ready. Run planner first.")
    return {"article": article.model_dump(), "task": task.model_dump()}


@app.post("/api/lesson/action")
async def lesson_action(action: dict):
    from backend.tutor.graph import get_tutor_graph
    graph = get_tutor_graph()
    config = {"configurable": {"thread_id": date.today().isoformat()}}

    async def generate():
        async for chunk in graph.astream(
            Command(resume=action),
            config=config,
            stream_mode="custom",
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/lesson/start")
async def start_lesson():
    """Initialize or resume today's LangGraph session."""
    from backend.tutor.graph import get_tutor_graph
    graph = get_tutor_graph()
    config = {"configurable": {"thread_id": date.today().isoformat()}}

    async def generate():
        async for chunk in graph.astream(
            {"user_profile": None, "today_article": None, "today_task": None,
             "review_queue": [], "review_index": 0, "user_writing": None, "messages": []},
            config=config,
            stream_mode="custom",
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ─── Profile ──────────────────────────────────────────────────────────────

@app.get("/api/profile")
async def get_profile():
    from backend.database import Database
    db = Database()
    profile = db.get_user_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile.model_dump()


@app.patch("/api/profile")
async def update_profile(body: dict):
    from backend.database import Database
    db = Database()
    profile = db.get_user_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    # Natural language interest update via LLM
    new_interests_str = body.get("interests_update", "")
    if new_interests_str:
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(model="claude-haiku-4-5-20251001")
        response = llm.invoke(f"""
Current interests: {profile.interests}
User update: "{new_interests_str}"
Return a JSON array of updated interests (3-5 items). Only the array, no explanation.
""")
        import ast
        new_interests = json.loads(response.content)
        profile = profile.model_copy(update={"interests": new_interests})
    db.upsert_user_profile(profile)
    return profile.model_dump()


# ─── Vocab ────────────────────────────────────────────────────────────────

@app.get("/api/vocab")
async def get_vocab():
    from backend.database import Database
    db = Database()
    items = db.get_all_vocab_items()
    return [item.model_dump() for item in items]
```

**Step 3: Restart and test all routes**

```bash
uv run uvicorn backend.main:app --reload --port 8000
curl http://localhost:8000/health
curl http://localhost:8000/api/onboarding/status
curl http://localhost:8000/api/planner/status
# All should return valid JSON without errors
```

**Step 4: Commit**

```bash
git add backend/onboarding/ backend/main.py
git commit -m "feat: add Onboarding Agent and all FastAPI routes"
```

---

## Task 10: Frontend TypeScript Types + SSE Client + Hooks

**Files:**
- Create: `frontend/types/index.ts`
- Create: `frontend/lib/sse.ts`
- Create: `frontend/hooks/useLesson.ts`

**Step 1: Create frontend/types/index.ts**

```typescript
// frontend/types/index.ts

export type LessonPhase = 'review' | 'reading' | 'writing' | 'feedback'

export interface UserProfile {
  goal: string
  interests: string[]
  level: number
  bandwidth_minutes: number
  writing_mode: 'professional' | 'ielts' | 'both'
}

export interface Article {
  id: number
  date: string
  source_url: string
  original_title: string
  full_text: string
  highlight_indices: number[]
  article_logic: 'compare' | 'cause_effect' | 'argumentation'
  topic_tags: string[]
}

export interface WritingTask {
  id: number
  article_id: number
  mode: 'professional' | 'ielts_task1' | 'ielts_task2'
  instruction: string
  min_words: number
}

export interface ChinglishFlag {
  original: string
  issue: 'word_choice' | 'sentence_structure' | 'logic_connector'
  explanation_zh: string
  native_alternative: string
}

export interface GrammarError {
  original: string
  correction: string
  explanation_zh: string
}

export interface WritingFeedback {
  overall_score: number
  grammar_errors: GrammarError[]
  chinglish_flags: ChinglishFlag[]
  rewrite_suggestions: string[]
}

export interface VocabItem {
  id: number
  word: string
  context_sentence: string
  source: 'reading_click' | 'writing_error'
  next_review: string
  fsrs_state: Record<string, unknown>
  article_id: number | null
}

export type SSEChunk =
  | { type: 'fill_blank'; question: string; word: string }
  | { type: 'word_explanation'; result: string }
  | { type: 'sentence_analysis'; result: string }
  | { type: 'feedback'; result: WritingFeedback }
  | { type: 'writing_task'; instruction: string; min_words: number }
  | { type: 'awaiting_action'; article_full_text: string; highlight_indices: number[]; user_level: number }
  | { type: 'error'; message: string }
  | { type: 'token'; content: string }

export type LessonAction =
  | { type: 'explain_word'; word: string; context: string }
  | { type: 'analyze_sentence'; sentence: string }
  | { type: 'done_reading' }
  | { type: 'fill_blank_answer'; answer: string; response_seconds: number }
  | { type: 'submit_writing'; text: string }
```

**Step 2: Create frontend/lib/sse.ts**

```typescript
// frontend/lib/sse.ts
import type { SSEChunk, LessonAction } from '@/types'

export async function sendAction(
  action: LessonAction,
  onChunk: (chunk: SSEChunk) => void,
): Promise<void> {
  const res = await fetch('/api/lesson/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(action),
  })

  if (!res.ok) throw new Error(`API error: ${res.status}`)

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const lines = decoder.decode(value).split('\n')
    for (const line of lines) {
      if (line.startsWith('data: ') && !line.includes('[DONE]')) {
        try {
          onChunk(JSON.parse(line.slice(6)))
        } catch {
          // skip malformed chunk
        }
      }
    }
  }
}

export async function startLesson(onChunk: (chunk: SSEChunk) => void): Promise<void> {
  const res = await fetch('/api/lesson/start', { method: 'POST' })
  if (!res.ok) throw new Error(`API error: ${res.status}`)

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const lines = decoder.decode(value).split('\n')
    for (const line of lines) {
      if (line.startsWith('data: ') && !line.includes('[DONE]')) {
        try {
          onChunk(JSON.parse(line.slice(6)))
        } catch {
          // skip
        }
      }
    }
  }
}

export async function sendOnboardingMessage(
  message: string,
  onToken: (token: string) => void,
): Promise<void> {
  const res = await fetch('/api/onboarding/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const lines = decoder.decode(value).split('\n')
    for (const line of lines) {
      if (line.startsWith('data: ') && !line.includes('[DONE]')) {
        try {
          const chunk = JSON.parse(line.slice(6))
          if (chunk.type === 'token') onToken(chunk.content)
        } catch {
          // skip
        }
      }
    }
  }
}
```

**Step 3: Create frontend/hooks/useLesson.ts**

```typescript
// frontend/hooks/useLesson.ts
import useSWR from 'swr'
import type { Article, WritingTask, VocabItem, UserProfile } from '@/types'

const fetcher = (url: string) => fetch(url).then(r => r.json())

export function useTodayLesson() {
  return useSWR<{ article: Article; task: WritingTask }>('/api/lesson/today', fetcher)
}

export function usePlannerStatus() {
  return useSWR<{ ready: boolean }>('/api/planner/status', fetcher, {
    refreshInterval: (data) => (data?.ready ? 0 : 3000),
  })
}

export function useOnboardingStatus() {
  return useSWR<{ ready: boolean }>('/api/onboarding/status', fetcher, {
    refreshInterval: (data) => (data?.ready ? 0 : 2000),
  })
}

export function useVocab() {
  return useSWR<VocabItem[]>('/api/vocab', fetcher)
}

export function useProfile() {
  return useSWR<UserProfile>('/api/profile', fetcher)
}
```

**Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
# Expected: no errors
```

**Step 5: Commit**

```bash
git add frontend/types/ frontend/lib/ frontend/hooks/
git commit -m "feat: add frontend types, SSE client, and SWR hooks"
```

---

## Task 11: Onboarding UI

**Files:**
- Create: `frontend/app/onboarding/page.tsx`
- Modify: `frontend/app/page.tsx`

**Step 1: Create the onboarding chat page**

```typescript
// frontend/app/onboarding/page.tsx
'use client'
import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { sendOnboardingMessage } from '@/lib/sse'
import { useOnboardingStatus } from '@/hooks/useLesson'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const PHASE_LABELS = ['目标', '兴趣', '水平', '时长', '写作模式']

export default function OnboardingPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: '你好！我是你的语言学习顾问。先告诉我，你学英语最迫切想解决什么问题？' }
  ])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [showPreferenceCards, setShowPreferenceCards] = useState(false)
  const [bandwidth, setBandwidth] = useState<number | null>(null)
  const [writingMode, setWritingMode] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { data: status, mutate } = useOnboardingStatus()

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (status?.ready && !showPreferenceCards) {
      setShowPreferenceCards(true)
    }
  }, [status?.ready])

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setIsStreaming(true)

    let assistantContent = ''
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])

    try {
      await sendOnboardingMessage(userMsg, (token) => {
        assistantContent += token
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: 'assistant', content: assistantContent }
          return updated
        })
      })
      await mutate()  // re-check profile status
    } finally {
      setIsStreaming(false)
    }
  }

  const handlePreferenceSubmit = async () => {
    if (!bandwidth || !writingMode) return
    await fetch('/api/onboarding/preferences', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bandwidth_minutes: bandwidth, writing_mode: writingMode }),
    })
    await fetch('/api/planner/run', { method: 'POST' })
    router.push('/lesson')
  }

  return (
    <div className="max-w-2xl mx-auto p-4 h-screen flex flex-col">
      <h1 className="text-xl font-bold mb-4">入学评估</h1>

      <div className="flex-1 overflow-y-auto space-y-3 mb-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-xl px-4 py-2 ${
              m.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-100'
            }`}>
              {m.content || (isStreaming && m.role === 'assistant' ? '...' : '')}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {showPreferenceCards ? (
        <Card className="mb-4">
          <CardContent className="pt-4 space-y-4">
            <p className="font-medium">最后两步：</p>
            <div>
              <p className="text-sm mb-2">每日学习时长</p>
              <div className="flex gap-2">
                {[15, 25].map(m => (
                  <Button
                    key={m}
                    variant={bandwidth === m ? 'default' : 'outline'}
                    onClick={() => setBandwidth(m)}
                  >{m} 分钟</Button>
                ))}
              </div>
            </div>
            <div>
              <p className="text-sm mb-2">写作目标</p>
              <div className="flex gap-2 flex-wrap">
                {[['professional', '职场流'], ['ielts', '雅思流'], ['both', '两者']].map(([val, label]) => (
                  <Button
                    key={val}
                    variant={writingMode === val ? 'default' : 'outline'}
                    onClick={() => setWritingMode(val)}
                  >{label}</Button>
                ))}
              </div>
            </div>
            <Button
              className="w-full"
              disabled={!bandwidth || !writingMode}
              onClick={handlePreferenceSubmit}
            >
              开始准备今日内容 →
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="flex gap-2">
          <Input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder="输入你的回答..."
            disabled={isStreaming}
          />
          <Button onClick={handleSend} disabled={isStreaming || !input.trim()}>
            发送
          </Button>
        </div>
      )}
    </div>
  )
}
```

**Step 2: Update frontend/app/page.tsx (entry redirect)**

```typescript
// frontend/app/page.tsx
import { redirect } from 'next/navigation'

async function getOnboardingStatus() {
  try {
    const res = await fetch('http://localhost:8000/api/onboarding/status', { cache: 'no-store' })
    return res.json()
  } catch {
    return { ready: false }
  }
}

async function getPlannerStatus() {
  try {
    const res = await fetch('http://localhost:8000/api/planner/status', { cache: 'no-store' })
    return res.json()
  } catch {
    return { ready: false }
  }
}

export default async function HomePage() {
  const [onboarding, planner] = await Promise.all([
    getOnboardingStatus(),
    getPlannerStatus(),
  ])

  if (!onboarding.ready) redirect('/onboarding')
  if (!planner.ready) redirect('/lesson?loading=true')
  redirect('/lesson')
}
```

**Step 3: Verify pages load**

```bash
cd frontend && npm run dev
# Visit http://localhost:3000 — should redirect to /onboarding
```

**Step 4: Commit**

```bash
git add frontend/app/
git commit -m "feat: add onboarding chat UI with preference cards and routing"
```

---

## Task 12: Lesson Page State Machine + Review Gate

**Files:**
- Create: `frontend/app/lesson/reducer.ts`
- Create: `frontend/app/lesson/page.tsx`
- Create: `frontend/components/FillBlankCard.tsx`

**Step 1: Create frontend/app/lesson/reducer.ts**

```typescript
// frontend/app/lesson/reducer.ts
import type { LessonPhase, WritingFeedback } from '@/types'

export interface LessonState {
  phase: LessonPhase
  popover: { word: string; explanation: string } | null
  drawer: { sentence: string; analysis: string } | null
  feedback: WritingFeedback | null
  isStreaming: boolean
  fillBlank: { question: string; word: string } | null
}

export type LessonAction =
  | { type: 'FILL_BLANK_RECEIVED'; question: string; word: string }
  | { type: 'REVIEW_DONE' }
  | { type: 'AWAITING_READING' }
  | { type: 'WORD_CLICK'; word: string }
  | { type: 'WORD_EXPLAINED'; word: string; explanation: string }
  | { type: 'POPOVER_CLOSE' }
  | { type: 'SENTENCE_CLICK'; sentence: string }
  | { type: 'SENTENCE_ANALYZED'; analysis: string }
  | { type: 'READING_DONE' }
  | { type: 'WRITING_TASK_RECEIVED' }
  | { type: 'WRITING_STREAM_START' }
  | { type: 'FEEDBACK_DONE'; feedback: WritingFeedback }

export const initialState: LessonState = {
  phase: 'review',
  popover: null,
  drawer: null,
  feedback: null,
  isStreaming: false,
  fillBlank: null,
}

export function lessonReducer(state: LessonState, action: LessonAction): LessonState {
  switch (action.type) {
    case 'FILL_BLANK_RECEIVED':
      return { ...state, phase: 'review', fillBlank: { question: action.question, word: action.word } }
    case 'REVIEW_DONE':
      return { ...state, fillBlank: null }
    case 'AWAITING_READING':
      return { ...state, phase: 'reading' }
    case 'WORD_CLICK':
      return { ...state, isStreaming: true }
    case 'WORD_EXPLAINED':
      return { ...state, isStreaming: false, popover: { word: action.word, explanation: action.explanation } }
    case 'POPOVER_CLOSE':
      return { ...state, popover: null }
    case 'SENTENCE_CLICK':
      return { ...state, isStreaming: true, drawer: { sentence: action.sentence, analysis: '' } }
    case 'SENTENCE_ANALYZED':
      return { ...state, isStreaming: false, drawer: state.drawer ? { ...state.drawer, analysis: action.analysis } : null }
    case 'READING_DONE':
      return { ...state, phase: 'writing', drawer: null, popover: null }
    case 'WRITING_TASK_RECEIVED':
      return { ...state, phase: 'writing' }
    case 'WRITING_STREAM_START':
      return { ...state, isStreaming: true }
    case 'FEEDBACK_DONE':
      return { ...state, phase: 'feedback', isStreaming: false, feedback: action.feedback }
    default:
      return state
  }
}
```

**Step 2: Create frontend/components/FillBlankCard.tsx**

```typescript
// frontend/components/FillBlankCard.tsx
'use client'
import { useState, useEffect } from 'react'
import { sendAction } from '@/lib/sse'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface Props {
  question: string
  word: string
  onDone: () => void
}

export function FillBlankCard({ question, word, onDone }: Props) {
  const [answer, setAnswer] = useState('')
  const [startTime] = useState(Date.now())
  const [hint, setHint] = useState<string | null>(null)
  const [attempts, setAttempts] = useState(0)
  const [revealed, setRevealed] = useState(false)

  const handleSubmit = async () => {
    const response_seconds = (Date.now() - startTime) / 1000
    const isCorrect = answer.trim().toLowerCase() === word.toLowerCase()

    if (isCorrect || attempts >= 2) {
      await sendAction(
        { type: 'fill_blank_answer', answer: isCorrect ? answer : word, response_seconds },
        () => {},
      )
      onDone()
      return
    }

    // Progressive hints
    const newAttempts = attempts + 1
    setAttempts(newAttempts)
    if (newAttempts === 1) {
      setHint(`词性提示：动词（verb）`)
    } else if (newAttempts === 2) {
      setHint(`首字母提示：${word[0].toUpperCase()}...`)
    }
  }

  const handleReveal = async () => {
    const response_seconds = (Date.now() - startTime) / 1000
    await sendAction(
      { type: 'fill_blank_answer', answer: word, response_seconds: 30 },
      () => {},
    )
    setRevealed(true)
    setTimeout(onDone, 2000)
  }

  return (
    <Card className="max-w-lg mx-auto">
      <CardHeader>
        <CardTitle className="text-base">每日复习</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-lg leading-relaxed">{question}</p>
        {hint && <p className="text-sm text-blue-600">{hint}</p>}
        {revealed && <p className="text-green-600 font-medium">答案：{word}</p>}
        {!revealed && (
          <div className="flex gap-2">
            <Input
              value={answer}
              onChange={e => setAnswer(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSubmit()}
              placeholder="填写答案..."
            />
            <Button onClick={handleSubmit}>确认</Button>
            {attempts >= 2 && (
              <Button variant="ghost" onClick={handleReveal}>揭晓</Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
```

**Step 3: Commit**

```bash
git add frontend/app/lesson/ frontend/components/FillBlankCard.tsx
git commit -m "feat: add lesson state machine and fill-blank review card"
```

---

## Task 13: Article Reader UI

**Files:**
- Create: `frontend/components/FullArticle.tsx`
- Create: `frontend/components/WordChip.tsx`
- Create: `frontend/components/ArticleReader.tsx`

**Step 1: Create frontend/components/WordChip.tsx**

```typescript
// frontend/components/WordChip.tsx
'use client'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { sendAction } from '@/lib/sse'
import { useState } from 'react'

interface Props {
  word: string
  context: string
}

export function WordChip({ word, context }: Props) {
  const [explanation, setExplanation] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const handleClick = async () => {
    setIsOpen(true)
    if (explanation) return
    setIsLoading(true)
    let buffer = ''
    await sendAction(
      { type: 'explain_word', word, context },
      chunk => {
        if (chunk.type === 'word_explanation') {
          buffer += chunk.result
          setExplanation(buffer)
        }
      },
    )
    setIsLoading(false)
  }

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <span
          className="cursor-pointer underline decoration-dotted underline-offset-2 hover:bg-yellow-100 rounded px-0.5"
          onClick={handleClick}
        >
          {word}
        </span>
      </PopoverTrigger>
      <PopoverContent className="max-w-xs text-sm">
        {isLoading ? '解释中...' : explanation || '点击获取解释'}
      </PopoverContent>
    </Popover>
  )
}
```

**Step 2: Create frontend/components/FullArticle.tsx**

```typescript
// frontend/components/FullArticle.tsx
'use client'
import { WordChip } from './WordChip'
import type { Article } from '@/types'

interface Props {
  article: Article
  onSentenceClick: (sentence: string) => void
}

function renderParagraph(text: string, isHighlighted: boolean, onSentenceClick: (s: string) => void) {
  // Split into words for word-click support — simplified tokenization
  const words = text.split(/(\s+)/)
  return (
    <p
      className={`mb-4 leading-relaxed ${isHighlighted ? 'bg-yellow-50 border-l-4 border-yellow-400 pl-3 py-1' : ''}`}
      onDoubleClick={() => onSentenceClick(text)}
      title="双击分析句子"
    >
      {words.map((token, i) =>
        /\s+/.test(token) ? (
          <span key={i}>{token}</span>
        ) : (
          <WordChip key={i} word={token.replace(/[.,!?;:'"()\[\]]/g, '')} context={text} />
        )
      )}
    </p>
  )
}

export function FullArticle({ article, onSentenceClick }: Props) {
  const paragraphs = article.full_text.split('\n\n')

  return (
    <div className="prose max-w-none">
      <h2 className="text-xl font-bold mb-2">{article.original_title}</h2>
      <div className="flex gap-2 mb-4 flex-wrap">
        {article.topic_tags.map(tag => (
          <span key={tag} className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs">{tag}</span>
        ))}
        <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
          {article.article_logic === 'compare' ? '对比分析' :
           article.article_logic === 'cause_effect' ? '因果推导' : '论证立场'}
        </span>
      </div>
      <p className="text-xs text-gray-400 mb-4">双击任意段落可分析句子结构 · 点击单词获取上下文释义</p>
      {paragraphs.map((para, i) =>
        renderParagraph(para, article.highlight_indices.includes(i), onSentenceClick)
      )}
    </div>
  )
}
```

**Step 3: Create frontend/components/ArticleReader.tsx**

```typescript
// frontend/components/ArticleReader.tsx
'use client'
import { useState } from 'react'
import { FullArticle } from './FullArticle'
import { sendAction } from '@/lib/sse'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import type { Article } from '@/types'

interface Props {
  article: Article
  onDoneReading: () => void
}

export function ArticleReader({ article, onDoneReading }: Props) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [analysis, setAnalysis] = useState('')
  const [currentSentence, setCurrentSentence] = useState('')

  const handleSentenceClick = async (sentence: string) => {
    setCurrentSentence(sentence)
    setDrawerOpen(true)
    setAnalysis('')
    let buffer = ''
    await sendAction(
      { type: 'analyze_sentence', sentence },
      chunk => {
        if (chunk.type === 'sentence_analysis') {
          buffer += chunk.result
          setAnalysis(buffer)
        }
      },
    )
  }

  const handleDoneReading = async () => {
    await sendAction({ type: 'done_reading' }, () => {})
    onDoneReading()
  }

  return (
    <div className="max-w-3xl mx-auto p-4">
      <FullArticle article={article} onSentenceClick={handleSentenceClick} />

      <div className="mt-6 flex justify-end">
        <Button onClick={handleDoneReading} size="lg">
          完成阅读 → 去写作
        </Button>
      </div>

      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent side="bottom" className="h-64">
          <SheetHeader>
            <SheetTitle className="text-sm text-gray-500 font-normal">句子分析</SheetTitle>
          </SheetHeader>
          <p className="text-sm italic text-gray-600 mb-2">"{currentSentence}"</p>
          <p className="text-sm leading-relaxed">{analysis || '分析中...'}</p>
        </SheetContent>
      </Sheet>
    </div>
  )
}
```

**Step 4: Commit**

```bash
git add frontend/components/
git commit -m "feat: add FullArticle reader with word chips and sentence analysis"
```

---

## Task 14: Writing Panel + Feedback + Lesson Page Assembly

**Files:**
- Create: `frontend/components/WritingPanel.tsx`
- Create: `frontend/components/FeedbackView.tsx`
- Modify: `frontend/app/lesson/page.tsx`

**Step 1: Create frontend/components/WritingPanel.tsx**

```typescript
// frontend/components/WritingPanel.tsx
'use client'
import { useState } from 'react'
import { sendAction } from '@/lib/sse'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { WritingTask, WritingFeedback } from '@/types'

interface Props {
  task: WritingTask
  onFeedback: (feedback: WritingFeedback) => void
}

export function WritingPanel({ task, onFeedback }: Props) {
  const [text, setText] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const wordCount = text.trim().split(/\s+/).filter(Boolean).length
  const meetsMinimum = wordCount >= task.min_words

  const handleSubmit = async () => {
    if (!meetsMinimum || isSubmitting) return
    setIsSubmitting(true)
    await sendAction(
      { type: 'submit_writing', text },
      chunk => {
        if (chunk.type === 'feedback') {
          onFeedback(chunk.result)
        }
      },
    )
    setIsSubmitting(false)
  }

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">写作任务</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="leading-relaxed">{task.instruction}</p>
          <p className="text-sm text-gray-500 mt-2">最少 {task.min_words} 字</p>
        </CardContent>
      </Card>

      <Textarea
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="用英文写作..."
        className="min-h-48 text-base"
      />

      <div className="flex justify-between items-center">
        <span className={`text-sm ${meetsMinimum ? 'text-green-600' : 'text-gray-400'}`}>
          {wordCount} / {task.min_words} words
        </span>
        <Button onClick={handleSubmit} disabled={!meetsMinimum || isSubmitting}>
          {isSubmitting ? '批改中...' : '提交写作'}
        </Button>
      </div>
    </div>
  )
}
```

**Step 2: Create frontend/components/FeedbackView.tsx**

```typescript
// frontend/components/FeedbackView.tsx
'use client'
import type { WritingFeedback } from '@/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface Props {
  feedback: WritingFeedback
}

export function FeedbackView({ feedback }: Props) {
  const scoreColor =
    feedback.overall_score >= 8 ? 'text-green-600' :
    feedback.overall_score >= 5 ? 'text-yellow-600' : 'text-red-600'

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <div className="text-center">
        <span className={`text-5xl font-bold ${scoreColor}`}>{feedback.overall_score}</span>
        <span className="text-gray-400 text-xl">/10</span>
      </div>

      {feedback.grammar_errors.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">语法问题</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {feedback.grammar_errors.slice(0, 2).map((err, i) => (
              <div key={i} className="border-l-4 border-red-300 pl-3">
                <p className="line-through text-gray-400 text-sm">{err.original}</p>
                <p className="text-green-700 text-sm font-medium">{err.correction}</p>
                <p className="text-xs text-gray-500">{err.explanation_zh}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {feedback.chinglish_flags.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Chinglish 识别</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {feedback.chinglish_flags.slice(0, 2).map((flag, i) => (
              <div key={i} className="border-l-4 border-orange-300 pl-3">
                <p className="text-gray-400 text-sm">{flag.original}</p>
                <p className="text-blue-700 text-sm font-medium">→ {flag.native_alternative}</p>
                <p className="text-xs text-gray-500">{flag.explanation_zh}</p>
                <Badge variant="outline" className="text-xs mt-1">{flag.issue}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {feedback.rewrite_suggestions.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">重写建议</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {feedback.rewrite_suggestions.map((suggestion, i) => (
              <div key={i} className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-400 mb-1">版本 {i + 1}</p>
                <p className="text-sm leading-relaxed">{suggestion}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
```

**Step 3: Create frontend/app/lesson/page.tsx (full assembly)**

```typescript
// frontend/app/lesson/page.tsx
'use client'
import { useReducer, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { lessonReducer, initialState } from './reducer'
import { FillBlankCard } from '@/components/FillBlankCard'
import { ArticleReader } from '@/components/ArticleReader'
import { WritingPanel } from '@/components/WritingPanel'
import { FeedbackView } from '@/components/FeedbackView'
import { useTodayLesson, usePlannerStatus } from '@/hooks/useLesson'
import { startLesson } from '@/lib/sse'
import type { SSEChunk } from '@/types'

export default function LessonPage() {
  const searchParams = useSearchParams()
  const isLoading = searchParams.get('loading') === 'true'
  const { data: lesson, isLoading: lessonLoading } = useTodayLesson()
  const { data: plannerStatus } = usePlannerStatus()
  const [state, dispatch] = useReducer(lessonReducer, initialState)

  useEffect(() => {
    if (!lesson) return

    const handleChunk = (chunk: SSEChunk) => {
      switch (chunk.type) {
        case 'fill_blank':
          dispatch({ type: 'FILL_BLANK_RECEIVED', question: chunk.question, word: chunk.word })
          break
        case 'awaiting_action':
          dispatch({ type: 'AWAITING_READING' })
          break
        case 'writing_task':
          dispatch({ type: 'WRITING_TASK_RECEIVED' })
          break
        case 'feedback':
          dispatch({ type: 'FEEDBACK_DONE', feedback: chunk.result })
          break
      }
    }

    startLesson(handleChunk).catch(console.error)
  }, [lesson])

  if (isLoading || !plannerStatus?.ready) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center space-y-2">
          <p className="text-lg">今日内容准备中...</p>
          <p className="text-sm text-gray-500">DeepAgent 正在为你抓取文章</p>
        </div>
      </div>
    )
  }

  if (lessonLoading || !lesson) {
    return <div className="flex items-center justify-center h-screen">加载中...</div>
  }

  return (
    <main className="min-h-screen pb-16">
      {state.phase === 'review' && state.fillBlank && (
        <div className="flex items-center justify-center min-h-screen">
          <FillBlankCard
            question={state.fillBlank.question}
            word={state.fillBlank.word}
            onDone={() => dispatch({ type: 'REVIEW_DONE' })}
          />
        </div>
      )}

      {state.phase === 'reading' && (
        <ArticleReader
          article={lesson.article}
          onDoneReading={() => dispatch({ type: 'READING_DONE' })}
        />
      )}

      {state.phase === 'writing' && (
        <WritingPanel
          task={lesson.task}
          onFeedback={feedback => dispatch({ type: 'FEEDBACK_DONE', feedback })}
        />
      )}

      {state.phase === 'feedback' && state.feedback && (
        <FeedbackView feedback={state.feedback} />
      )}
    </main>
  )
}
```

**Step 4: Install shadcn components used**

```bash
cd frontend
npx shadcn@latest add card button input textarea badge sheet popover
```

**Step 5: Final check**

```bash
cd frontend && npx tsc --noEmit
npm run build
# Expected: no TypeScript errors, build succeeds
```

**Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: add WritingPanel, FeedbackView, and full lesson page assembly"
```

---

## Task 15: Quality Guards + Pre-commit Hooks

**Files:**
- Create: `.pre-commit-config.yaml`
- Create: `frontend/commitlint.config.js`

**Step 1: Create .pre-commit-config.yaml**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: local
    hooks:
      - id: mypy
        name: mypy
        entry: uv run mypy backend/
        language: system
        pass_filenames: false
        types: [python]

      - id: tsc
        name: tsc
        entry: bash -c 'cd frontend && npx tsc --noEmit'
        language: system
        pass_filenames: false
        types: [ts, tsx]

      - id: openapi-drift
        name: Warn if models.py changed without regenerating types
        entry: bash -c 'git diff --cached --name-only | grep -q "backend/models.py" && echo "⚠️  models.py changed — run: task generate-types" && exit 1 || exit 0'
        language: system
        pass_filenames: false

  - repo: https://github.com/commitizen-tools/commitizen
    rev: v3.13.0
    hooks:
      - id: commitizen
        stages: [commit-msg]
```

**Step 2: Install hooks**

```bash
uv add --dev pre-commit
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
cd frontend && npx husky init
echo "npx lint-staged" > frontend/.husky/pre-commit
```

**Step 3: Add lint-staged config to frontend/package.json**

Add to `package.json`:
```json
"lint-staged": {
  "*.{ts,tsx}": ["eslint --fix", "prettier --write"],
  "*.{json,css,md}": ["prettier --write"]
}
```

**Step 4: Run full quality check**

```bash
task check
# Both Python and frontend checks should pass
```

**Step 5: Run all tests**

```bash
uv run pytest backend/tests/ -v
# Expected: all tests PASS
```

**Step 6: Final commit**

```bash
git add .pre-commit-config.yaml frontend/package.json frontend/commitlint.config.js
git commit -m "chore: add pre-commit hooks and quality guards"
```

---

## Implementation Order Summary

| Task | Description | Est. effort |
|------|-------------|-------------|
| 1 | Python backend scaffold | 30 min |
| 2 | Frontend scaffold | 30 min |
| 3 | Pydantic models + SQLite | 45 min |
| 4 | FSRS engine | 20 min |
| 5 | Planner tools | 40 min |
| 6 | Planner agent + routes | 30 min |
| 7 | Tutor tools | 30 min |
| 8 | Tutor graph + nodes | 45 min |
| 9 | Tutor routes + onboarding agent | 30 min |
| 10 | Frontend types + SSE + hooks | 25 min |
| 11 | Onboarding UI | 30 min |
| 12 | Lesson page + review gate | 30 min |
| 13 | Article reader UI | 35 min |
| 14 | Writing panel + feedback + assembly | 40 min |
| 15 | Quality guards | 20 min |

## Smoke Test Sequence (after all tasks)

```bash
# 1. Start backend
uv run uvicorn backend.main:app --reload --port 8000

# 2. Start frontend
cd frontend && npm run dev

# 3. Open http://localhost:3000
# → Redirects to /onboarding (profile not set)
# → Chat with AI, complete preferences
# → Triggers planner (watch logs for article scraping)
# → Redirects to /lesson when ready
# → Review gate (if vocab due)
# → Read article with highlights
# → Click words → popover explanations
# → Double-click sentence → drawer analysis
# → Done reading → writing panel
# → Submit writing → SSE feedback
```
