from typing import TypedDict

import asyncpraw  # type: ignore[import-untyped]


class RedditPostResponse(TypedDict):
    id: str
    title: str
    selftext: str
    score: int
    num_comments: int
    created_utc: float
    url: str
    permalink: str
    subreddit: str
    upvote_ratio: float
    crosspost_parent: str | None


class RedditAPIError(Exception):
    """Raised when the Reddit API is unreachable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class RedditClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        timeout: float,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._user_agent = user_agent
        self._timeout = timeout

    async def fetch_subreddit_posts(
        self,
        subreddit: str,
        sort: str,
        time_filter: str,
        limit: int,
    ) -> list[RedditPostResponse]:
        try:
            reddit = asyncpraw.Reddit(
                client_id=self._client_id,
                client_secret=self._client_secret,
                user_agent=self._user_agent,
                requestor_kwargs={"timeout": self._timeout},
            )
            try:
                sub = await reddit.subreddit(subreddit)
                fetch_fn = getattr(sub, sort)
                kwargs: dict[str, object] = {"limit": limit}
                if sort == "top":
                    kwargs["time_filter"] = time_filter
                posts: list[RedditPostResponse] = []
                async for submission in fetch_fn(**kwargs):
                    crosspost_parent: str | None = None
                    if hasattr(submission, "crosspost_parent_list"):
                        parents = submission.crosspost_parent_list
                        if parents:
                            crosspost_parent = parents[0].get("id")
                    posts.append(
                        RedditPostResponse(
                            id=submission.id,
                            title=submission.title,
                            selftext=submission.selftext or "",
                            score=submission.score,
                            num_comments=submission.num_comments,
                            created_utc=submission.created_utc,
                            url=submission.url,
                            permalink=submission.permalink,
                            subreddit=submission.subreddit.display_name,
                            upvote_ratio=submission.upvote_ratio,
                            crosspost_parent=crosspost_parent,
                        ),
                    )
                return posts
            finally:
                await reddit.close()
        except RedditAPIError:
            raise
        except Exception as exc:
            raise RedditAPIError(
                f"Reddit API error: {exc}",
            ) from exc
