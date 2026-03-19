from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
