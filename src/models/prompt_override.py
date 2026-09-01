"""Persisted prompt override (AUTHOR-012)."""

from datetime import datetime

from pydantic import BaseModel, Field


class PromptOverride(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    template: str = Field(min_length=1)
    updated_by: str = Field(max_length=100)
    updated_at: datetime
