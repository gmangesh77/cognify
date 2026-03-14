import asyncio
from typing import TypedDict

from pytrends.request import TrendReq


class GTTrendingSearch(TypedDict):
    title: str


class GTRelatedQuery(TypedDict):
    title: str
    value: int
    query_type: str
    seed_keyword: str


class GoogleTrendsAPIError(Exception):
    """Raised when Google Trends API is unreachable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class GoogleTrendsClient:
    def __init__(
        self,
        language: str,
        timezone_offset: int,
        timeout: float,
    ) -> None:
        self._pytrends = TrendReq(
            hl=language,
            tz=timezone_offset,
            requests_args={"timeout": timeout},
        )

    def _fetch_trending_sync(
        self,
        country: str,
    ) -> list[GTTrendingSearch]:
        df = self._pytrends.trending_searches(pn=country)
        results: list[GTTrendingSearch] = []
        for title in df[0].tolist():
            results.append(GTTrendingSearch(title=str(title)))
        return results

    def _fetch_related_sync(
        self,
        keywords: list[str],
    ) -> list[GTRelatedQuery]:
        self._pytrends.build_payload(kw_list=keywords[:5])
        raw = self._pytrends.related_queries()
        results: list[GTRelatedQuery] = []
        for keyword, data in raw.items():
            for query_type in ("rising", "top"):
                df = data.get(query_type)
                if df is None or df.empty:
                    continue
                for _, row in df.iterrows():
                    value = row["value"]
                    if value == "Breakout":
                        value = 5000
                    results.append(
                        GTRelatedQuery(
                            title=str(row["query"]),
                            value=int(value),
                            query_type=query_type,
                            seed_keyword=str(keyword),
                        ),
                    )
        return results

    async def fetch_trending_searches(
        self,
        country: str,
    ) -> list[GTTrendingSearch]:
        try:
            return await asyncio.to_thread(
                self._fetch_trending_sync,
                country,
            )
        except GoogleTrendsAPIError:
            raise
        except Exception as exc:
            raise GoogleTrendsAPIError(str(exc)) from exc

    async def fetch_related_queries(
        self,
        keywords: list[str],
    ) -> list[GTRelatedQuery]:
        try:
            return await asyncio.to_thread(
                self._fetch_related_sync,
                keywords,
            )
        except GoogleTrendsAPIError:
            raise
        except Exception as exc:
            raise GoogleTrendsAPIError(str(exc)) from exc
