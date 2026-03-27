import operator
from typing import Annotated

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from typing_extensions import TypedDict

from backend.general.nodes import (
    challenge_quiz,
    free_qa_session,
    metacog_session,
    quiz_session,
    reading_session,
    route_start,
    save_results,
    scaffold_quiz,
)
from backend.models import GeneralLesson


class MetacogQuestion(TypedDict):
    question: str
    correct_answer: str


class GeneralLessonState(TypedDict):
    project: dict
    lesson: GeneralLesson
    phase: str
    session_mode: str  # "scaffold" | "normal" | "challenge"
    quiz_answers: list
    quiz_score: int  # lesson-only score (excludes review Qs)
    qa_history: list
    messages: Annotated[list, operator.add]
    retry_hint: list  # wrong questions from last low-score attempt; [] on first try
    fsrs_wrong_items: list  # wrong quiz items with FSRS initial state for this session
    metacog_question: MetacogQuestion | None  # [P1#5] nullable typed dict
    metacog_feedback: str  # [P1#6] idempotency guard (replaces metacog_answered)
    review_questions_cache: list  # [P0#1] HITL-safe: persisted in checkpoint
    fsrs_review_updates: list  # [P2#11] deferred FSRS updates for save_results


def build_general_lesson_graph(checkpointer):
    g: StateGraph = StateGraph(GeneralLessonState)  # type: ignore[type-var]

    # Nodes
    g.add_node("route_start", route_start)  # type: ignore[call-overload,type-var]
    g.add_node("reading", reading_session)  # type: ignore[call-overload,type-var]
    g.add_node("quiz", quiz_session)  # type: ignore[call-overload,type-var]
    g.add_node("scaffold_quiz", scaffold_quiz)  # type: ignore[call-overload,type-var]
    g.add_node("challenge_quiz", challenge_quiz)  # type: ignore[call-overload,type-var]
    g.add_node(  # type: ignore[call-overload,type-var]
        "metacog_session",
        metacog_session,
        retry_policy=RetryPolicy(max_attempts=3),  # [P2#16] LLM call retry
    )
    g.add_node("free_qa", free_qa_session)  # type: ignore[call-overload,type-var]
    g.add_node("save_results", save_results)  # type: ignore[call-overload,type-var]

    # Edges
    # CRITICAL: route_start and reading use Command routing.
    # Do NOT add static outgoing edges for these nodes.
    g.add_edge(START, "route_start")
    # route_start -> "reading" or "challenge_quiz" (via Command)
    # reading    -> "quiz" or "scaffold_quiz" (via Command)
    g.add_edge("quiz", "free_qa")
    g.add_edge("scaffold_quiz", "free_qa")
    g.add_edge("challenge_quiz", "metacog_session")
    g.add_edge("metacog_session", "free_qa")
    g.add_edge("free_qa", "save_results")
    g.add_edge("save_results", END)

    return g.compile(checkpointer=checkpointer)


_graph = None
_graph_checkpointer = None


def get_general_lesson_graph(checkpointer):
    global _graph, _graph_checkpointer
    if _graph is None or _graph_checkpointer is not checkpointer:
        _graph = build_general_lesson_graph(checkpointer)
        _graph_checkpointer = checkpointer
    return _graph
