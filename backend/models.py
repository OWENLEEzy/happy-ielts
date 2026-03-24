from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

WritingMode = Literal["professional", "ielts_task1", "ielts_task2"]


class UserProfile(BaseModel):
    goal: str
    interests: list[str]
    level: int = Field(ge=1, le=10)
    bandwidth_minutes: int
    writing_mode: WritingMode


class ArticleCreate(BaseModel):
    date: str = Field(description="ISO date string (YYYY-MM-DD) for the lesson date")
    source_url: str = Field(description="Full URL of the scraped article")
    original_title: str = Field(description="Title of the article as it appears on the page")
    full_text: str = Field(
        min_length=100, description="Full article body text returned by scrape_article"
    )
    highlight_indices: list[int] = Field(
        min_length=3,
        max_length=5,
        description="0-based paragraph indices returned by highlight_key_paragraphs",
    )
    article_logic: Literal[
        "compare", "cause_effect", "argumentation", "narrative", "problem_solution"
    ] = Field(description="Logical structure type returned by highlight_key_paragraphs")
    topic_tags: list[str] = Field(
        min_length=1,
        max_length=5,
        description="1-5 topic keywords extracted from the article relevant to user's interests",
    )


class Article(ArticleCreate):
    id: int


class WritingTaskCreate(BaseModel):
    article_id: int = Field(
        description="Set to 0 as placeholder; save_daily_lesson assigns the real ID"
    )
    mode: WritingMode = Field(
        description="Writing mode matching the user's profile: professional / ielts_task1 / ielts_task2"  # noqa: E501
    )
    instruction: str = Field(
        min_length=50,
        description="Full writing task description referencing article topics (min 50 chars)",
    )
    min_words: int = Field(
        ge=50, le=250, description="Minimum word count: 50 for professional, 150 for IELTS modes"
    )


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
    word: str = Field(max_length=100)
    context_sentence: str = Field(max_length=400)
    source: Literal["reading_click", "writing_error"]
    next_review: str  # ISO date string
    fsrs_state: dict[str, Any]
    article_id: int | None


class VocabItem(VocabItemCreate):
    id: int


class TutorHandoff(BaseModel):
    """Structured summary from Tutor → Orchestrator after a lesson session."""

    date: str  # "2026-03-21"
    phases_completed: list[str]  # ["review", "reading", "writing", "feedback"]
    writing_score: int  # 0 if no writing submitted
    observations: list[str]  # notable things Tutor noticed
    vocab_reviewed: int  # number of vocab cards shown
    vocab_correct: int  # number answered correctly
    article_topic: str  # first topic_tag of today's article
    article_logic: str  # article_logic field


class ReflectHandoff(BaseModel):
    """Structured output from Reflect → Orchestrator → Planner."""

    date: str
    level_suggestion: int = Field(ge=1, le=10)
    top_weaknesses: list[str]  # e.g. ["run-on sentence", "weak thesis"]
    improving_areas: list[str]  # areas showing improvement
    topic_recommendation: str = Field(max_length=300)
    task_recommendation: str = Field(max_length=300)
    teaching_insight: str = Field(max_length=1000)  # embedded in Planner system prompt


# ── General Learning ──────────────────────────────────────


class UserGoalProfile(BaseModel):
    mode: Literal["english", "skill"]
    topic: str
    motivation: str
    goal_outcome: str
    context: str
    current_level: str
    time_per_week: int = Field(ge=1, le=168)
    duration_weeks: int = Field(ge=1, le=52)
    constraints: list[str] = []


class LearningLesson(BaseModel):
    title: str
    objectives: list[str] = []


class LearningChapter(BaseModel):
    title: str
    lessons: list[LearningLesson]


class LearningMap(BaseModel):
    topic: str
    total_weeks: int
    chapters: list[LearningChapter]


class GeneralProject(BaseModel):
    id: int
    user_topic: str
    status: Literal["onboarding", "researching", "extracting", "active", "complete", "error"]
    goal_profile: UserGoalProfile | None = None
    learning_map: LearningMap | None = None
    notebook_id: str | None = None
    tier: Literal["free", "paid"] = "free"
    budget_used: int = 0
    created_at: str


class GeneralLesson(BaseModel):
    id: int
    project_id: int
    chapter: int
    lesson: int
    title: str
    study_guide: str | None = None
    quiz_json: list[dict] | None = None
    flashcards: list[dict] | None = None
    status: Literal["pending", "ready"] = "pending"


class DimensionState(BaseModel):
    mastery: float = Field(ge=0.0, le=1.0)
    sessions: int = 0
    last_reviewed: str
    trend: Literal["improving", "stable", "worsening"] = "stable"


class GeneralStudentModel(BaseModel):
    project_id: int
    goal_outcome: str
    goal_progress: float = Field(ge=0.0, le=1.0, default=0.0)
    dimensions: dict[str, DimensionState] = {}
    fsrs_due: list[str] = []
    updated: str
