import operator
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

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
    writing_feedback: object | None
    messages: Annotated[list, operator.add]


def build_tutor_graph(checkpointer):
    return (
        StateGraph(TutorState)
        .add_node("route_start", route_start)
        .add_node("spaced_review", spaced_review)
        .add_node("reading", reading_session)
        .add_node("writing_task", writing_task)
        .add_node("evaluate_writing", evaluate_writing)
        .add_node("save_results", save_results)
        .add_edge(START, "route_start")
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
