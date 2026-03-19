"""Research pipeline models — orchestrator state and agent contracts.

These models define the data flowing through the LangGraph research
orchestrator. See the RESEARCH-001 spec for full design context.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TopicInput(BaseModel, frozen=True):
    """Narrowed topic data for the orchestrator (avoids API layer import)."""

    id: UUID
    title: str
    description: str
    domain: str


class ResearchFacet(BaseModel, frozen=True):
    """A single research facet within a research plan."""

    index: int
    title: str
    description: str
    search_queries: list[str]


class ResearchPlan(BaseModel, frozen=True):
    """LLM-generated research plan with 3-5 facets."""

    facets: list[ResearchFacet]
    reasoning: str


class SourceDocument(BaseModel, frozen=True):
    """A document retrieved during research."""

    url: str
    title: str
    snippet: str
    retrieved_at: datetime
    published_at: datetime | None = None
    author: str | None = None


class FacetFindings(BaseModel, frozen=True):
    """Results from researching a single facet."""

    facet_index: int
    sources: list[SourceDocument]
    claims: list[str]
    summary: str


class FacetTask(BaseModel, frozen=True):
    """Tracks dispatch status for a single facet."""

    facet_index: int
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None


class EvaluationResult(BaseModel, frozen=True):
    """LLM completeness evaluation of research findings."""

    is_complete: bool
    weak_facets: list[int]
    reasoning: str


class ChunkMetadata(BaseModel, frozen=True):
    """Metadata for a document chunk (passed to TokenChunker)."""

    source_url: str
    source_title: str
    topic_id: str
    session_id: str
    published_at: str | None = None
    author: str | None = None


class DocumentChunk(BaseModel, frozen=True):
    """A chunked document ready for embedding and Milvus storage."""

    text: str
    source_url: str
    source_title: str
    topic_id: str
    session_id: str
    chunk_index: int
    published_at: str | None = None
    author: str | None = None


class ChunkResult(BaseModel, frozen=True):
    """A retrieved chunk from Milvus similarity search."""

    text: str
    source_url: str
    source_title: str
    score: float
    chunk_index: int
    published_at: datetime | None = None
    author: str | None = None


class KnowledgeBaseStats(BaseModel, frozen=True):
    """Knowledge base statistics from Milvus."""

    total_chunks: int
    total_documents: int
    collection_name: str
    topic_id: str | None = None
