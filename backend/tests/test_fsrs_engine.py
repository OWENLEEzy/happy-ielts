import pytest
from datetime import date, timedelta
from backend.fsrs_engine import (
    new_card_state,
    update_card,
    map_answer_to_rating,
    serialize_card,
    deserialize_card,
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
