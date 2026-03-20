import math
import time
from datetime import UTC, datetime

import structlog
from pydantic import BaseModel

from src.api.schemas.topics import RawTopic
from src.services.trends._dedup import deduplicate_crossposts
from src.services.trends.protocol import TrendFetchConfig
from src.services.trends.reddit_client import (
    RedditAPIError,
    RedditClient,
    RedditPostResponse,
)

logger = structlog.get_logger()

# 12-hour half-life for recency decay
_RECENCY_LAMBDA = math.log(2) / 12


class RedditFetchDefaults(BaseModel, frozen=True):
    """Reddit-specific fetch defaults set at init time."""

    subreddits: list[str]
    sort: str = "hot"
    time_filter: str = "day"


class RedditService:
    def __init__(
        self,
        client: RedditClient,
        score_cap: float,
        defaults: RedditFetchDefaults,
    ) -> None:
        self._client = client
        self._score_cap = score_cap
        self._defaults = defaults

    @property
    def source_name(self) -> str:
        return "reddit"

    @staticmethod
    def calculate_score(
        score: int,
        num_comments: int,
        hours_ago: float,
        score_cap: float,
    ) -> float:
        hours = max(1.0, hours_ago)
        comment_velocity = num_comments / hours
        recency_bonus = 100.0 * math.exp(
            -_RECENCY_LAMBDA * hours_ago,
        )
        raw = (score * 0.3) + (comment_velocity * 0.5) + (recency_bonus * 0.2)
        return min(100.0, (raw / score_cap) * 100)

    @staticmethod
    def calculate_velocity(
        score: int,
        hours_ago: float,
    ) -> float:
        hours = max(1.0, hours_ago)
        return score / hours

    @staticmethod
    def filter_by_domain(
        posts: list[RedditPostResponse],
        domain_keywords: list[str],
    ) -> list[tuple[RedditPostResponse, list[str]]]:
        results: list[tuple[RedditPostResponse, list[str]]] = []
        for post in posts:
            title = post["title"].lower()
            selftext = post["selftext"].lower()
            subreddit = post["subreddit"].lower()
            matched = [
                kw
                for kw in domain_keywords
                if kw.lower() in title
                or kw.lower() in selftext
                or kw.lower() in subreddit
            ]
            if matched:
                results.append((post, matched))
        return results

    @staticmethod
    def map_to_raw_topic(
        post: RedditPostResponse,
        matched_keywords: list[str],
        score_cap: float,
        now: datetime | None = None,
    ) -> RawTopic:
        if now is None:
            now = datetime.now(UTC)
        created = datetime.fromtimestamp(
            post["created_utc"],
            tz=UTC,
        )
        hours_ago = (now - created).total_seconds() / 3600
        return RawTopic(
            title=post["title"],
            description=post["selftext"][:200],
            source="reddit",
            external_url=f"https://www.reddit.com{post['permalink']}",
            trend_score=RedditService.calculate_score(
                post["score"],
                post["num_comments"],
                hours_ago,
                score_cap,
            ),
            discovered_at=created,
            velocity=RedditService.calculate_velocity(
                post["score"],
                hours_ago,
            ),
            domain_keywords=matched_keywords,
        )

    async def _collect_posts(
        self,
        config: TrendFetchConfig,
    ) -> tuple[list[RedditPostResponse], int]:
        """Fetch posts from all subreddits; return (posts, scanned_count)."""
        all_posts: list[RedditPostResponse] = []
        scanned = 0
        for subreddit in self._defaults.subreddits:
            try:
                posts = await self._client.fetch_subreddit_posts(
                    subreddit,
                    self._defaults.sort,
                    self._defaults.time_filter,
                    config.max_results,
                )
                all_posts.extend(posts)
                scanned += 1
            except RedditAPIError:
                logger.warning("reddit_subreddit_failed", subreddit=subreddit)
        return all_posts, scanned

    async def fetch_and_normalize(
        self,
        config: TrendFetchConfig,
    ) -> list[RawTopic]:
        start = time.monotonic()
        logger.info(
            "reddit_fetch_started",
            domain_keywords=config.domain_keywords,
            subreddits=self._defaults.subreddits,
            max_results=config.max_results,
        )
        all_posts, scanned = await self._collect_posts(config)
        if scanned == 0:
            raise RedditAPIError("All subreddits failed")
        total_fetched = len(all_posts)
        deduped, removed = deduplicate_crossposts(all_posts)
        logger.debug(
            "reddit_crossposts_deduped",
            before_count=total_fetched,
            after_count=len(deduped),
            groups_merged=removed,
        )
        filtered = self.filter_by_domain(deduped, config.domain_keywords)
        logger.debug(
            "reddit_posts_filtered",
            before_count=len(deduped),
            after_count=len(filtered),
            domain_keywords=config.domain_keywords,
        )
        topics = sorted(
            [self.map_to_raw_topic(p, kws, self._score_cap) for p, kws in filtered],
            key=lambda t: t.trend_score,
            reverse=True,
        )
        duration_ms = round((time.monotonic() - start) * 1000)
        logger.info(
            "reddit_fetch_completed",
            total_fetched=total_fetched,
            total_after_dedup=len(deduped),
            total_after_filter=len(topics),
            subreddits_scanned=scanned,
            duration_ms=duration_ms,
        )
        return topics
