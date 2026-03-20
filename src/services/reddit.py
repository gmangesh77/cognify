import math
import time
from datetime import UTC, datetime
from difflib import SequenceMatcher

import structlog

from src.api.schemas.topics import RawTopic
from src.api.schemas.trends import RedditFetchResponse
from src.services.trends.reddit_client import (
    RedditAPIError,
    RedditClient,
    RedditPostResponse,
)

logger = structlog.get_logger()

# 12-hour half-life for recency decay
_RECENCY_LAMBDA = math.log(2) / 12


class RedditService:
    def __init__(
        self,
        client: RedditClient,
        score_cap: float,
    ) -> None:
        self._client = client
        self._score_cap = score_cap

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
    def deduplicate_crossposts(
        posts: list[RedditPostResponse],
    ) -> tuple[list[RedditPostResponse], int]:
        """Two-pass dedup: crosspost_parent IDs then fuzzy title match.
        Returns (deduped_posts, removed_count)."""
        if not posts:
            return [], 0

        # Pass 1: group by crosspost_parent
        parent_groups: dict[str, list[RedditPostResponse]] = {}
        no_parent: list[RedditPostResponse] = []
        for post in posts:
            parent = post["crosspost_parent"]
            if parent:
                parent_groups.setdefault(parent, []).append(post)
            else:
                no_parent.append(post)

        # Keep highest score per parent group
        survivors: list[RedditPostResponse] = []
        for group in parent_groups.values():
            best = max(group, key=lambda p: p["score"])
            survivors.append(best)

        # Pass 2: fuzzy title match on remaining posts
        merged_into: dict[int, int] = {}  # index -> group leader index
        for i, post_a in enumerate(no_parent):
            if i in merged_into:
                continue
            for j in range(i + 1, len(no_parent)):
                if j in merged_into:
                    continue
                ratio = SequenceMatcher(
                    None,
                    post_a["title"].lower(),
                    no_parent[j]["title"].lower(),
                ).ratio()
                if ratio > 0.85:
                    merged_into[j] = i

        # Build fuzzy groups
        fuzzy_groups: dict[int, list[int]] = {}
        for j, leader in merged_into.items():
            fuzzy_groups.setdefault(leader, [leader]).append(j)

        # Keep highest score per fuzzy group
        seen_leaders: set[int] = set()
        for i, post in enumerate(no_parent):
            if i in merged_into:
                continue
            if i in fuzzy_groups:
                seen_leaders.add(i)
                group_indices = fuzzy_groups[i]
                group_posts = [no_parent[idx] for idx in group_indices]
                best = max(group_posts, key=lambda p: p["score"])
                survivors.append(best)
            else:
                survivors.append(post)

        original_count = len(posts)
        removed = original_count - len(survivors)
        return survivors, removed

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

    async def fetch_and_normalize(
        self,
        domain_keywords: list[str],
        subreddits: list[str],
        max_results: int,
        sort: str,
        time_filter: str,
    ) -> RedditFetchResponse:
        start = time.monotonic()
        logger.info(
            "reddit_fetch_started",
            domain_keywords=domain_keywords,
            subreddits=subreddits,
            max_results=max_results,
            sort=sort,
        )

        all_posts: list[RedditPostResponse] = []
        scanned = 0
        for subreddit in subreddits:
            try:
                posts = await self._client.fetch_subreddit_posts(
                    subreddit,
                    sort,
                    time_filter,
                    max_results,
                )
                all_posts.extend(posts)
                scanned += 1
            except RedditAPIError:
                logger.warning(
                    "reddit_subreddit_failed",
                    subreddit=subreddit,
                )
                continue

        if scanned == 0:
            raise RedditAPIError(
                "All subreddits failed",
            )

        total_fetched = len(all_posts)

        deduped, removed = self.deduplicate_crossposts(all_posts)
        logger.debug(
            "reddit_crossposts_deduped",
            before_count=total_fetched,
            after_count=len(deduped),
            groups_merged=removed,
        )

        filtered = self.filter_by_domain(deduped, domain_keywords)
        logger.debug(
            "reddit_posts_filtered",
            before_count=len(deduped),
            after_count=len(filtered),
            domain_keywords=domain_keywords,
        )

        topics = sorted(
            [
                self.map_to_raw_topic(
                    post,
                    kws,
                    self._score_cap,
                )
                for post, kws in filtered
            ],
            key=lambda t: t.trend_score,
            reverse=True,
        )

        duration_ms = round(
            (time.monotonic() - start) * 1000,
        )
        logger.info(
            "reddit_fetch_completed",
            total_fetched=total_fetched,
            total_after_dedup=len(deduped),
            total_after_filter=len(topics),
            subreddits_scanned=scanned,
            duration_ms=duration_ms,
        )

        return RedditFetchResponse(
            topics=topics,
            total_fetched=total_fetched,
            total_after_dedup=len(deduped),
            total_after_filter=len(topics),
            subreddits_scanned=scanned,
        )
