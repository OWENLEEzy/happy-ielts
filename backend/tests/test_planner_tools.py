from unittest.mock import MagicMock, patch

from backend.planner.tools import scrape_article


def test_scrape_article_returns_text_on_success():
    mock_page = MagicMock()
    mock_page.get_best_text.return_value = "This is the article body text."

    mock_scraper = MagicMock()
    mock_scraper.get.return_value = mock_page

    with patch("backend.planner.tools.Scraper", return_value=mock_scraper):
        result = scrape_article.invoke({"url": "https://example.com/article"})

    assert result["status"] == "success"
    assert "article body text" in result["data"]
    assert len(result["data"]) > 10


def test_scrape_article_falls_back_on_exception():
    """When Scrapling raises, the tool should not crash (Playwright fallback handled)."""
    with patch("backend.planner.tools.Scraper") as mock_cls:
        mock_cls.return_value.get.side_effect = Exception("blocked")
        # Playwright fallback also mocked to avoid network calls in tests
        with patch("backend.planner.tools._trafilatura_scrape", return_value="fallback text"):
            result = scrape_article.invoke({"url": "https://example.com/article"})
    assert result["status"] == "success"
    assert result["data"] == "fallback text"
