import time
from datetime import UTC, datetime

import structlog

from src.api.schemas.topics import RawTopic
from src.api.schemas.trends import HNFetchResponse
from src.services.hackernews_client import HackerNewsClient, HNStoryResponse

logger = structlog.get_logger()


class HackerNewsService:
    def __init__(
        self,
        client: HackerNewsClient,
        points_cap: float,
    ) -> None:
        self._client = client
        self._points_cap = points_cap

    async def fetch_and_normalize(
        self,
        domain_keywords: list[str],
        max_results: int,
        min_points: int,
    ) -> HNFetchResponse:
        start = time.monotonic()
        logger.info(
            "hackernews_fetch_started",
            domain_keywords=domain_keywords,
            max_results=max_results,
            min_points=min_points,
        )
        query = " ".join(domain_keywords)
        stories = await self._client.fetch_stories(
            query,
            min_points,
            max_results,
        )
        total_fetched = len(stories)
        filtered = self.filter_by_domain(
            stories,
            domain_keywords,
        )
        logger.debug(
            "hackernews_stories_filtered",
            before_count=total_fetched,
            after_count=len(filtered),
            domain_keywords=domain_keywords,
        )
        topics = [
            self.map_to_raw_topic(
                story,
                kws,
                self._points_cap,
            )
            for story, kws in filtered
        ]
        duration_ms = round(
            (time.monotonic() - start) * 1000,
        )
        logger.info(
            "hackernews_fetch_completed",
            total_fetched=total_fetched,
            total_after_filter=len(topics),
            duration_ms=duration_ms,
        )
        return HNFetchResponse(
            topics=topics,
            total_fetched=total_fetched,
            total_after_filter=len(topics),
        )

    @staticmethod
    def calculate_score(
        points: int,
        num_comments: int,
        points_cap: float,
    ) -> float:
        raw = (points * 0.7) + (num_comments * 0.3)
        return min(100.0, (raw / points_cap) * 100)

    @staticmethod
    def calculate_velocity(points: int, hours_ago: float) -> float:
        hours = max(1.0, hours_ago)
        return points / hours

    @staticmethod
    def filter_by_domain(
        stories: list[HNStoryResponse],
        domain_keywords: list[str],
    ) -> list[tuple[HNStoryResponse, list[str]]]:
        results: list[tuple[HNStoryResponse, list[str]]] = []
        for story in stories:
            title = story["title"].lower()
            url = (story.get("url") or "").lower()
            matched = [
                kw for kw in domain_keywords if kw.lower() in title or kw.lower() in url
            ]
            if matched:
                results.append((story, matched))
        return results

    @staticmethod
    def map_to_raw_topic(
        story: HNStoryResponse,
        matched_keywords: list[str],
        points_cap: float,
        now: datetime | None = None,
    ) -> RawTopic:
        if now is None:
            now = datetime.now(UTC)
        points = story.get("points") or 0
        comments = story.get("num_comments") or 0
        created = datetime.fromtimestamp(
            story["created_at_i"],
            tz=UTC,
        )
        hours_ago = (now - created).total_seconds() / 3600
        url = story.get("url") or (
            f"https://news.ycombinator.com/item?id={story['objectID']}"
        )
        text = story.get("story_text") or ""
        return RawTopic(
            title=story["title"],
            description=text[:200],
            source="hackernews",
            external_url=url,
            trend_score=HackerNewsService.calculate_score(
                points,
                comments,
                points_cap,
            ),
            discovered_at=created,
            velocity=HackerNewsService.calculate_velocity(
                points,
                hours_ago,
            ),
            domain_keywords=matched_keywords,
        )
