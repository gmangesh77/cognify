from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.trends.reddit_client import (
    RedditAPIError,
    RedditClient,
)


async def _async_iter(items: list[Any]) -> AsyncIterator[Any]:
    """Helper: wrap a list into an async iterator for mocking asyncpraw listings."""
    for item in items:
        yield item


def _mock_submission(**overrides: object) -> MagicMock:
    """Create a mock asyncpraw Submission object."""
    defaults = {
        "id": "abc123",
        "title": "Test Post",
        "selftext": "Some text content",
        "score": 100,
        "num_comments": 50,
        "created_utc": 1710000000.0,
        "url": "https://example.com/article",
        "permalink": "/r/test/comments/abc123/test_post/",
        "subreddit": MagicMock(display_name="test"),
        "upvote_ratio": 0.95,
        "crosspost_parent_list": [],
    }
    defaults.update(overrides)
    sub = MagicMock()
    for key, val in defaults.items():
        setattr(sub, key, val)
    return sub


class TestFetchSubredditPosts:
    async def test_successful_fetch(self) -> None:
        mock_sub = _mock_submission()
        mock_subreddit = MagicMock()
        mock_subreddit.hot = MagicMock(
            return_value=_async_iter([mock_sub]),
        )

        mock_reddit = AsyncMock()
        mock_reddit.subreddit = AsyncMock(return_value=mock_subreddit)

        with patch(
            "src.services.trends.reddit_client.asyncpraw.Reddit",
            return_value=mock_reddit,
        ):
            client = RedditClient(
                client_id="test",
                client_secret="test",
                user_agent="test",
                timeout=5.0,
            )
            posts = await client.fetch_subreddit_posts(
                "test",
                "hot",
                "day",
                10,
            )

        assert len(posts) == 1
        assert posts[0]["title"] == "Test Post"
        assert posts[0]["score"] == 100
        assert posts[0]["subreddit"] == "test"

    async def test_empty_subreddit(self) -> None:
        mock_subreddit = MagicMock()
        mock_subreddit.hot = MagicMock(
            return_value=_async_iter([]),
        )

        mock_reddit = AsyncMock()
        mock_reddit.subreddit = AsyncMock(return_value=mock_subreddit)

        with patch(
            "src.services.trends.reddit_client.asyncpraw.Reddit",
            return_value=mock_reddit,
        ):
            client = RedditClient(
                client_id="test",
                client_secret="test",
                user_agent="test",
                timeout=5.0,
            )
            posts = await client.fetch_subreddit_posts(
                "empty",
                "hot",
                "day",
                10,
            )

        assert posts == []

    async def test_api_error_raises(self) -> None:
        mock_reddit = AsyncMock()
        mock_reddit.subreddit = AsyncMock(
            side_effect=Exception("API failure"),
        )

        with patch(
            "src.services.trends.reddit_client.asyncpraw.Reddit",
            return_value=mock_reddit,
        ):
            client = RedditClient(
                client_id="test",
                client_secret="test",
                user_agent="test",
                timeout=5.0,
            )
            with pytest.raises(RedditAPIError, match="API failure"):
                await client.fetch_subreddit_posts(
                    "test",
                    "hot",
                    "day",
                    10,
                )
