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


def test_challenge_mode_skips_reading_node():
    """[P2#19] route_start must NOT have a static (non-conditional) edge to reading.

    Command routing appears as conditional=True edges; add_edge() produces conditional=False.
    If a static edge to 'reading' exists alongside Command routing, reading executes twice.
    """
    from langgraph.checkpoint.memory import MemorySaver

    graph = build_general_lesson_graph(MemorySaver())
    drawable = graph.get_graph()
    # Static edges are conditional=False; Command edges are conditional=True
    static_targets = [
        e.target for e in drawable.edges if e.source == "route_start" and not e.conditional
    ]
    assert (
        "reading" not in static_targets
    ), "route_start has a static edge to 'reading' — conflicts with Command routing!"
