from backend.general.graph import GeneralLessonState, build_general_lesson_graph


def test_graph_builds_without_error():
    from langgraph.checkpoint.memory import MemorySaver

    checkpointer = MemorySaver()
    graph = build_general_lesson_graph(checkpointer)
    assert graph is not None


def test_state_has_required_fields():
    import typing

    hints = typing.get_type_hints(GeneralLessonState)
    assert "lesson" in hints
    assert "phase" in hints
    assert "messages" in hints
