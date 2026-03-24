import threading

from fsrs import Card, Rating, Scheduler

_scheduler = Scheduler()
_scheduler_lock = threading.Lock()


def new_card_state() -> dict:
    """Create a serialized state for a brand-new vocab card."""
    card = Card()
    return serialize_card(card)


def map_answer_to_rating(is_correct: bool, response_seconds: float) -> Rating:
    if not is_correct:
        return Rating.Again
    # Clamp to non-negative; negative values from timing bugs should not affect rating
    secs = max(0.0, float(response_seconds))
    if secs > 15:
        return Rating.Hard
    elif secs > 5:
        return Rating.Good
    else:
        return Rating.Easy


def update_card(fsrs_state: dict, is_correct: bool, response_seconds: float) -> dict:
    """Apply a review result to an existing card state. Returns new state dict."""
    card = deserialize_card(fsrs_state)
    rating = map_answer_to_rating(is_correct, response_seconds)
    with _scheduler_lock:
        card, _ = _scheduler.review_card(card, rating)
    return serialize_card(card)


def serialize_card(card: Card) -> dict:
    return card.to_dict()  # type: ignore[return-value]


def deserialize_card(data: dict) -> Card:
    return Card.from_dict(data)  # type: ignore[arg-type]
