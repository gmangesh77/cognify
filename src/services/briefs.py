"""Brief service — owner-scoped CRUD over the Brief input contract (ADR-007)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

import structlog

from src.api.errors import NotFoundError
from src.models.brief import Brief, BriefCreate, BriefUpdate

logger = structlog.get_logger()


class BriefRepository(Protocol):
    async def create(self, owner_id: str, data: BriefCreate) -> Brief: ...
    async def get(self, brief_id: UUID) -> Brief | None: ...
    async def list_by_owner(self, owner_id: str) -> list[Brief]: ...
    async def update(self, brief_id: UUID, data: BriefUpdate) -> Brief | None: ...
    async def delete(self, brief_id: UUID) -> bool: ...


class InMemoryBriefRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Brief] = {}

    async def create(self, owner_id: str, data: BriefCreate) -> Brief:
        now = datetime.now(UTC)
        brief = Brief(
            id=uuid4(),
            owner_id=owner_id,
            created_at=now,
            updated_at=now,
            **data.model_dump(),
        )
        self._store[brief.id] = brief
        return brief

    async def get(self, brief_id: UUID) -> Brief | None:
        return self._store.get(brief_id)

    async def list_by_owner(self, owner_id: str) -> list[Brief]:
        mine = [b for b in self._store.values() if b.owner_id == owner_id]
        return sorted(mine, key=lambda b: (b.updated_at, b.created_at), reverse=True)

    async def update(self, brief_id: UUID, data: BriefUpdate) -> Brief | None:
        current = self._store.get(brief_id)
        if current is None:
            return None
        changes = data.model_dump(exclude_none=True)
        changes["updated_at"] = datetime.now(UTC)
        updated = current.model_copy(update=changes)
        self._store[brief_id] = updated
        return updated

    async def delete(self, brief_id: UUID) -> bool:
        return self._store.pop(brief_id, None) is not None


@dataclass(frozen=True)
class BriefUpdateCommand:
    owner_id: str
    brief_id: UUID
    data: BriefUpdate


class BriefService:
    def __init__(self, repo: BriefRepository) -> None:
        self._repo = repo

    async def create(self, owner_id: str, data: BriefCreate) -> Brief:
        return await self._repo.create(owner_id, data)

    async def get(self, owner_id: str, brief_id: UUID) -> Brief:
        brief = await self._repo.get(brief_id)
        if brief is None or brief.owner_id != owner_id:
            raise NotFoundError(f"Brief {brief_id} not found")
        return brief

    async def list(self, owner_id: str) -> list[Brief]:
        return await self._repo.list_by_owner(owner_id)

    async def update(self, cmd: BriefUpdateCommand) -> Brief:
        await self.get(cmd.owner_id, cmd.brief_id)
        updated = await self._repo.update(cmd.brief_id, cmd.data)
        if updated is None:
            raise NotFoundError(f"Brief {cmd.brief_id} not found")
        return updated

    async def delete(self, owner_id: str, brief_id: UUID) -> None:
        await self.get(owner_id, brief_id)
        await self._repo.delete(brief_id)
        logger.info("brief_deleted", brief_id=str(brief_id), owner_id=owner_id)

    async def duplicate(self, owner_id: str, brief_id: UUID) -> Brief:
        source = await self.get(owner_id, brief_id)
        exclude_fields = {"id", "owner_id", "created_at", "updated_at"}
        fields = source.model_dump(exclude=exclude_fields)
        fields["name"] = f"{source.name} (copy)"[:200]
        return await self._repo.create(owner_id, BriefCreate(**fields))
