from datetime import UTC, date, timedelta

from backend.fsrs_engine import (
    map_answer_to_rating,
    new_card_state,
    update_card,
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


# ---------------------------------------------------------------------------
# is_due
# ---------------------------------------------------------------------------


def test_is_due_past_due_date():
    from datetime import datetime

    from backend.fsrs_engine import is_due

    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    assert is_due({"due": past}) is True


def test_is_due_future_date():
    from datetime import datetime

    from backend.fsrs_engine import is_due

    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert is_due({"due": future}) is False


def test_is_due_no_due_field():
    from backend.fsrs_engine import is_due

    assert is_due({}) is True


def test_is_due_invalid_date():
    from backend.fsrs_engine import is_due

    assert is_due({"due": "not-a-date"}) is True
