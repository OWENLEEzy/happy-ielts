import pytest
from unittest.mock import patch, MagicMock
from datetime import date


def test_route_start_goes_to_review_when_due_items_exist():
    """route_start should return Command(goto='spaced_review') when vocab is due."""
    from backend.tutor.nodes import route_start
    from backend.models import VocabItem

    due_item = VocabItem(
        id=1, word="leverage", context_sentence="We leverage this.",
        source="reading_click", next_review=date.today().isoformat(),
        fsrs_state={}, article_id=None,
    )

    with patch("backend.tutor.nodes._db") as mock_db:
        mock_db.get_due_vocab_items.return_value = [due_item]
        state = {
            "user_profile": None, "today_article": None, "today_task": None,
            "review_queue": [], "review_index": 0,
            "user_writing": None, "writing_feedback": None, "messages": [],
        }
        result = route_start(state)

    assert result.goto == "spaced_review"
    assert len(result.update["review_queue"]) == 1


def test_route_start_goes_to_reading_when_no_due_items():
    """route_start should return Command(goto='reading') when no vocab is due."""
    from backend.tutor.nodes import route_start

    with patch("backend.tutor.nodes._db") as mock_db:
        mock_db.get_due_vocab_items.return_value = []
        state = {
            "user_profile": None, "today_article": None, "today_task": None,
            "review_queue": [], "review_index": 0,
            "user_writing": None, "writing_feedback": None, "messages": [],
        }
        result = route_start(state)

    assert result.goto == "reading"
