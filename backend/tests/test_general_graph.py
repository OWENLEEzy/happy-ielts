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


def test_state_has_session_mode_field():
    assert "session_mode" in GeneralLessonState.__annotations__


def test_state_has_metacog_fields():
    assert "metacog_question" in GeneralLessonState.__annotations__
    assert "metacog_feedback" in GeneralLessonState.__annotations__


def test_state_has_review_cache_field():
    assert "review_questions_cache" in GeneralLessonState.__annotations__


def test_state_has_fsrs_review_updates_field():
    assert "fsrs_review_updates" in GeneralLessonState.__annotations__
