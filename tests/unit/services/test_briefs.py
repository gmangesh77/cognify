"""BriefService ownership + CRUD semantics (AUTHOR-003)."""

from uuid import uuid4

import pytest

from src.api.errors import NotFoundError
from src.models.brief import BriefCreate, BriefUpdate
from src.services.briefs import (
    BriefService,
    BriefUpdateCommand,
    InMemoryBriefRepository,
)


@pytest.fixture
def svc() -> BriefService:
    return BriefService(InMemoryBriefRepository())


async def test_create_and_get(svc: BriefService) -> None:
    b = await svc.create("u1", BriefCreate(name="A"))
    assert (await svc.get("u1", b.id)).name == "A"


async def test_get_other_owner_is_not_found(svc: BriefService) -> None:
    b = await svc.create("u1", BriefCreate(name="A"))
    with pytest.raises(NotFoundError):
        await svc.get("u2", b.id)


async def test_get_missing_is_not_found(svc: BriefService) -> None:
    with pytest.raises(NotFoundError):
        await svc.get("u1", uuid4())


async def test_list_is_owner_scoped_newest_first(svc: BriefService) -> None:
    a = await svc.create("u1", BriefCreate(name="A"))
    b = await svc.create("u1", BriefCreate(name="B"))
    await svc.create("u2", BriefCreate(name="C"))
    assert [x.id for x in await svc.list("u1")] == [b.id, a.id]


async def test_update_changes_only_given_fields(svc: BriefService) -> None:
    b = await svc.create("u1", BriefCreate(name="A", keywords=["k"]))
    out = await svc.update(BriefUpdateCommand("u1", b.id, BriefUpdate(name="Z")))
    assert out.name == "Z" and out.keywords == ["k"]
    assert out.updated_at >= b.updated_at


async def test_update_other_owner_not_found(svc: BriefService) -> None:
    b = await svc.create("u1", BriefCreate(name="A"))
    with pytest.raises(NotFoundError):
        await svc.update(BriefUpdateCommand("u2", b.id, BriefUpdate(name="Z")))


async def test_delete_then_get_not_found(svc: BriefService) -> None:
    b = await svc.create("u1", BriefCreate(name="A"))
    await svc.delete("u1", b.id)
    with pytest.raises(NotFoundError):
        await svc.get("u1", b.id)


async def test_duplicate_copies_fields_with_copy_suffix(svc: BriefService) -> None:
    b = await svc.create(
        "u1",
        BriefCreate(name="A", keywords=["k"], length_target="long"),
    )
    dup = await svc.duplicate("u1", b.id)
    assert dup.id != b.id
    assert dup.name == "A (copy)"
    assert dup.keywords == ["k"] and dup.length_target == "long"
