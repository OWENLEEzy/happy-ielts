from fsrs import Scheduler, Card, Rating, State


_scheduler = Scheduler()


def new_card_state() -> dict:
    """Create a serialized state for a brand-new vocab card."""
    card = Card()
    return serialize_card(card)


def map_answer_to_rating(is_correct: bool, response_seconds: float) -> Rating:
    if not is_correct:
        return Rating.Again
    if response_seconds > 15:
        return Rating.Hard
    elif response_seconds > 5:
        return Rating.Good
    else:
        return Rating.Easy


def update_card(fsrs_state: dict, is_correct: bool, response_seconds: float) -> dict:
    """Apply a review result to an existing card state. Returns new state dict."""
    card = deserialize_card(fsrs_state)
    rating = map_answer_to_rating(is_correct, response_seconds)
    card, _ = _scheduler.review_card(card, rating)
    return serialize_card(card)


def serialize_card(card: Card) -> dict:
    return card.to_dict()


def deserialize_card(data: dict) -> Card:
    return Card.from_dict(data)
