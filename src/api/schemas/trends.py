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
