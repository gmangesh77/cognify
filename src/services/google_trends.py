import time
from datetime import UTC, datetime
from urllib.parse import quote_plus

import structlog

from src.api.schemas.topics import RawTopic
from src.api.schemas.trends import GTFetchResponse
from src.services.google_trends_client import (
    GoogleTrendsClient,
    GTRelatedQuery,
    GTTrendingSearch,
)

logger = structlog.get_logger()


class GoogleTrendsService:
    def __init__(self, client: GoogleTrendsClient) -> None:
        self._client = client

    async def fetch_and_normalize(
        self,
        domain_keywords: list[str],
        country: str,
        max_results: int,
    ) -> GTFetchResponse:
        start = time.monotonic()
        logger.info(
            "google_trends_fetch_started",
            domain_keywords=domain_keywords,
            country=country,
            max_results=max_results,
        )
        trending = await self._client.fetch_trending_searches(
            country,
        )
        related = await self._client.fetch_related_queries(
            domain_keywords,
        )
        total_trending = len(trending)
        total_related = len(related)

        all_items: list[GTTrendingSearch | GTRelatedQuery] = [
            *trending,
            *related,
        ]
        filtered = self.filter_by_domain(
            all_items,
            domain_keywords,
        )
        logger.debug(
            "google_trends_results_filtered",
            before_count=len(all_items),
            after_count=len(filtered),
            domain_keywords=domain_keywords,
        )

        topics: list[RawTopic] = []
        for item, kws in filtered:
            query_type, value = self._extract_type_value(item)
            topic = self.map_to_raw_topic(
                title=item["title"],
                query_type=query_type,
                value=value,
                matched_keywords=kws,
            )
            topics.append(topic)

        topics = self._deduplicate(topics)
        total_after_filter = len(topics)
        topics = topics[:max_results]

        duration_ms = round(
            (time.monotonic() - start) * 1000,
        )
        logger.info(
            "google_trends_fetch_completed",
            total_trending=total_trending,
            total_related=total_related,
            total_after_filter=total_after_filter,
            duration_ms=duration_ms,
        )
        return GTFetchResponse(
            topics=topics,
            total_trending=total_trending,
            total_related=total_related,
            total_after_filter=total_after_filter,
        )

    @staticmethod
    def _extract_type_value(
        item: GTTrendingSearch | GTRelatedQuery,
    ) -> tuple[str, int]:
        if "query_type" in item:
            rq: GTRelatedQuery = item  # type: ignore[assignment]
            return rq["query_type"], rq["value"]
        return "trending", 0

    @staticmethod
    def calculate_score(query_type: str, value: int) -> float:
        if query_type == "trending":
            return 70.0
        if query_type == "rising":
            return min(100.0, 50.0 + (value / 100.0) * 10.0)
        return float(value)

    @staticmethod
    def calculate_velocity(query_type: str, value: int) -> float:
        if query_type == "trending":
            return 50.0
        if query_type == "rising":
            return min(100.0, value / 10.0)
        return 5.0

    @staticmethod
    def filter_by_domain(
        items: list[GTTrendingSearch | GTRelatedQuery],
        domain_keywords: list[str],
    ) -> list[tuple[GTTrendingSearch | GTRelatedQuery, list[str]]]:
        results: list[tuple[GTTrendingSearch | GTRelatedQuery, list[str]]] = []
        for item in items:
            title_lower = item["title"].lower()
            matched = [kw for kw in domain_keywords if kw.lower() in title_lower]
            if matched:
                results.append((item, matched))
        return results

    @staticmethod
    def map_to_raw_topic(
        title: str,
        query_type: str,
        value: int,
        matched_keywords: list[str],
    ) -> RawTopic:
        encoded = quote_plus(title)
        url = f"https://trends.google.com/trends/explore?q={encoded}"
        return RawTopic(
            title=title,
            description="",
            source="google_trends",
            external_url=url,
            trend_score=GoogleTrendsService.calculate_score(
                query_type,
                value,
            ),
            discovered_at=datetime.now(UTC),
            velocity=GoogleTrendsService.calculate_velocity(
                query_type,
                value,
            ),
            domain_keywords=matched_keywords,
        )

    @staticmethod
    def _deduplicate(topics: list[RawTopic]) -> list[RawTopic]:
        seen: dict[str, RawTopic] = {}
        for topic in topics:
            key = topic.title.lower()
            if key not in seen or topic.trend_score > seen[key].trend_score:
                seen[key] = topic
        return list(seen.values())
