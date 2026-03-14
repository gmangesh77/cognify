from typing import Literal

from pydantic import BaseModel, Field

from src.api.schemas.topics import RawTopic


class HNFetchRequest(BaseModel):
    domain_keywords: list[str] = Field(min_length=1)
    max_results: int = Field(default=30, ge=1, le=100)
    min_points: int = Field(default=10, ge=0)


class HNFetchResponse(BaseModel):
    topics: list[RawTopic]
    total_fetched: int
    total_after_filter: int


class GTFetchRequest(BaseModel):
    domain_keywords: list[str] = Field(min_length=1)
    country: str = Field(default="united_states")
    max_results: int = Field(default=30, ge=1, le=100)


class GTFetchResponse(BaseModel):
    topics: list[RawTopic]
    total_trending: int
    total_related: int
    total_after_filter: int


class RedditFetchRequest(BaseModel):
    domain_keywords: list[str] = Field(min_length=1)
    subreddits: list[str] | None = Field(
        default=None,
        max_length=20,
    )
    max_results: int = Field(default=20, ge=1, le=100)
    sort: Literal["hot", "top", "new", "rising"] = "hot"
    time_filter: Literal["hour", "day", "week"] = "day"


class RedditFetchResponse(BaseModel):
    topics: list[RawTopic]
    total_fetched: int
    total_after_dedup: int
    total_after_filter: int
    subreddits_scanned: int


class NewsAPIFetchRequest(BaseModel):
    domain_keywords: list[str] = Field(min_length=1)
    max_results: int = Field(default=30, ge=1, le=100)
    category: str = Field(default="technology")
    country: str = Field(default="us")


class NewsAPIFetchResponse(BaseModel):
    topics: list[RawTopic]
    total_fetched: int
    total_after_filter: int
