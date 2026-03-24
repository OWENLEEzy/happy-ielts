import operator
from typing import Annotated

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from backend.general.nodes import (
    free_qa_session,
    quiz_session,
    reading_session,
    route_start,
    save_results,
)
from backend.models import GeneralLesson


class GeneralLessonState(TypedDict):
    project: dict
    lesson: GeneralLesson
    phase: str
    quiz_answers: list
    quiz_score: int
    qa_history: list
    messages: Annotated[list, operator.add]


def build_general_lesson_graph(checkpointer):
    g: StateGraph = StateGraph(GeneralLessonState)  # type: ignore[type-var]
    g.add_node("route_start", route_start)  # type: ignore[call-overload,type-var]
    g.add_node("reading", reading_session)  # type: ignore[call-overload,type-var]
    g.add_node("quiz", quiz_session)  # type: ignore[call-overload,type-var]
    g.add_node("free_qa", free_qa_session)  # type: ignore[call-overload,type-var]
    g.add_node("save_results", save_results)  # type: ignore[call-overload,type-var]
    g.add_edge(START, "route_start")
    g.add_edge("route_start", "reading")
    g.add_edge("reading", "quiz")
    g.add_edge("quiz", "free_qa")
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
