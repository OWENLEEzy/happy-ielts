import operator
from typing import Annotated

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from backend.tutor.nodes import (
    evaluate_writing,
    reading_session,
    route_start,
    save_results,
    spaced_review,
    writing_task,
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
    graph: StateGraph = StateGraph(TutorState)  # type: ignore[type-var]
    graph.add_node("route_start", route_start)  # type: ignore[type-var]
    graph.add_node("spaced_review", spaced_review)  # type: ignore[type-var]
    graph.add_node("reading", reading_session)  # type: ignore[type-var]
    graph.add_node("writing_task", writing_task)  # type: ignore[type-var]
    graph.add_node("evaluate_writing", evaluate_writing)  # type: ignore[type-var]
    graph.add_node("save_results", save_results)  # type: ignore[type-var]
    graph.add_edge(START, "route_start")
    graph.add_edge("writing_task", "evaluate_writing")
    graph.add_edge("evaluate_writing", "save_results")
    graph.add_edge("save_results", END)
    return graph.compile(checkpointer=checkpointer)


_graph = None


def get_tutor_graph(checkpointer=None):
    global _graph
    if _graph is None:
        _graph = build_tutor_graph(checkpointer)
    return _graph
