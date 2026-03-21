"""Research service — bridges API layer to the orchestrator.

Contains repository protocols, in-memory implementations, and
the ResearchService that manages session lifecycle.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import structlog
from pydantic import BaseModel

from src.agents.research.runner import ResearchOrchestrator
from src.api.errors import NotFoundError
from src.models.research import TopicInput
from src.models.research_db import AgentStep, ResearchSession

logger = structlog.get_logger()


# --- Repository protocols ---


class ResearchSessionRepository(Protocol):
    async def create(self, session: ResearchSession) -> ResearchSession: ...
    async def get(self, session_id: UUID) -> ResearchSession | None: ...
    async def update(self, session: ResearchSession) -> ResearchSession: ...
    async def list(
        self, status: str | None, page: int, size: int
    ) -> tuple[list[ResearchSession], int]: ...


class AgentStepRepository(Protocol):
    async def create(self, step: AgentStep) -> AgentStep: ...
    async def update(self, step: AgentStep) -> AgentStep: ...
    async def list_by_session(self, session_id: UUID) -> list[AgentStep]: ...


class TopicRepository(Protocol):
    async def exists(self, topic_id: UUID) -> bool: ...
    async def get(self, topic_id: UUID) -> TopicInput | None: ...


# --- In-memory implementations ---


class InMemoryResearchSessionRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, ResearchSession] = {}

    async def create(self, session: ResearchSession) -> ResearchSession:
        self._store[session.id] = session
        return session

    async def get(self, session_id: UUID) -> ResearchSession | None:
        return self._store.get(session_id)

    async def update(self, session: ResearchSession) -> ResearchSession:
        self._store[session.id] = session
        return session

    async def list(
        self, status: str | None, page: int, size: int
    ) -> tuple[list[ResearchSession], int]:
        items = list(self._store.values())
        if status:
            items = [s for s in items if s.status == status]
        total = len(items)
        start = (page - 1) * size
        return items[start : start + size], total


class InMemoryAgentStepRepository:
    def __init__(self) -> None:
        self._store: list[AgentStep] = []

    async def create(self, step: AgentStep) -> AgentStep:
        self._store.append(step)
        return step

    async def update(self, step: AgentStep) -> AgentStep:
        self._store = [
            step if s.id == step.id else s for s in self._store
        ]
        return step

    async def list_by_session(self, session_id: UUID) -> list[AgentStep]:
        return [s for s in self._store if s.session_id == session_id]


class InMemoryTopicRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, TopicInput] = {}

    def seed(self, topic: TopicInput) -> None:
        self._store[topic.id] = topic

    async def exists(self, topic_id: UUID) -> bool:
        return topic_id in self._store

    async def get(self, topic_id: UUID) -> TopicInput | None:
        return self._store.get(topic_id)


# --- Service ---


@dataclass(frozen=True)
class ResearchRepositories:
    sessions: ResearchSessionRepository
    steps: AgentStepRepository
    topics: TopicRepository


class SessionDetail(BaseModel):
    session: ResearchSession
    steps: list[AgentStep]


class PaginatedSessions(BaseModel):
    items: list[ResearchSession]
    total: int
    page: int
    size: int


class ResearchService:
    def __init__(
        self,
        repos: ResearchRepositories,
        orchestrator: ResearchOrchestrator,
    ) -> None:
        self._repos = repos
        self._orchestrator = orchestrator

    async def start_session(self, topic_id: UUID) -> ResearchSession:
        if not await self._repos.topics.exists(topic_id):
            raise NotFoundError(f"Topic {topic_id} not found")
        session = ResearchSession(topic_id=topic_id, started_at=datetime.now(UTC))
        return await self._repos.sessions.create(session)

    async def get_topic(self, topic_id: UUID) -> TopicInput:
        """Fetch a topic by ID. Raises NotFoundError if missing."""
        topic = await self._repos.topics.get(topic_id)
        if topic is None:
            raise NotFoundError(f"Topic {topic_id} not found")
        return topic

    async def get_session(self, session_id: UUID) -> SessionDetail:
        session = await self._repos.sessions.get(session_id)
        if session is None:
            raise NotFoundError(f"Session {session_id} not found")
        steps = await self._repos.steps.list_by_session(session_id)
        return SessionDetail(session=session, steps=steps)

    async def list_sessions(
        self, status: str | None, page: int, size: int
    ) -> PaginatedSessions:
        items, total = await self._repos.sessions.list(status, page, size)
        return PaginatedSessions(items=items, total=total, page=page, size=size)

    async def run_and_finalize(self, session_id: UUID, topic: TopicInput) -> None:
        try:
            result = await self._orchestrator.run(session_id, topic)
            await self._persist_success(session_id, topic, result)
        except Exception as exc:
            logger.error(
                "orchestrator_failed",
                session_id=str(session_id),
                error=str(exc),
            )
            await self._persist_failure(session_id)

    async def _persist_success(
        self, session_id: UUID, topic: TopicInput, result: object
    ) -> None:
        """Persist findings and mark session complete."""
        session = await self._repos.sessions.get(session_id)
        if not session:
            return
        findings_raw = result.get("findings", []) if isinstance(result, dict) else []
        findings_data = [
            f.model_dump() if hasattr(f, "model_dump") else f for f in findings_raw
        ]
        updated = session.model_copy(
            update={
                "status": "complete",
                "findings_data": findings_data,
                "topic_title": topic.title,
                "topic_description": topic.description,
                "topic_domain": topic.domain,
                "completed_at": datetime.now(UTC),
            }
        )
        await self._repos.sessions.update(updated)

    async def _persist_failure(self, session_id: UUID) -> None:
        """Mark session as failed."""
        session = await self._repos.sessions.get(session_id)
        if session:
            updated = session.model_copy(
                update={"status": "failed", "completed_at": datetime.now(UTC)}
            )
            await self._repos.sessions.update(updated)
