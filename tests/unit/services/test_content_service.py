"""Tests for ContentService."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content import section_prompt
from src.api.errors import NotFoundError
from src.config.settings import Settings
from src.db.persona_repository_memory import InMemoryPersonaRepository
from src.models.content import CanonicalArticle
from src.models.content_pipeline import ArticleDraft, DraftStatus
from src.models.persona import PersonaCreate, SampleCreate
from src.models.research import ChunkResult, FacetFindings, SourceDocument
from src.models.research_db import ResearchSession
from src.services.content import (
    ContentRepositories,
    ContentService,
    InMemoryArticleDraftRepository,
    InMemoryArticleRepository,
)
from src.services.content_repositories import ContentDeps
from src.services.persona.fingerprint import build_fingerprint
from src.services.research import InMemoryResearchSessionRepository


def _outline_json() -> str:
    return json.dumps(
        {
            "title": "Test Article",
            "content_type": "article",
            "sections": [
                {
                    "index": 0,
                    "title": "Intro",
                    "description": "D",
                    "key_points": ["P"],
                    "target_word_count": 300,
                    "relevant_facets": [0],
                },
            ],
            "total_target_words": 300,
            "reasoning": "Simple",
        }
    )


def _four_section_outline_json() -> str:
    sections = [
        {
            "index": i,
            "title": f"Section {i}",
            "description": f"Description {i}",
            "key_points": [f"Point {i}"],
            "target_word_count": 400,
            "relevant_facets": [0],
        }
        for i in range(4)
    ]
    return json.dumps(
        {
            "title": "Test Article",
            "content_type": "article",
            "sections": sections,
            "total_target_words": 1600,
            "reasoning": "Comprehensive coverage",
        }
    )


def _four_section_queries_json() -> str:
    return json.dumps(
        [{"section_index": i, "queries": [f"query{i}"]} for i in range(4)]
    )


def _long_draft_text() -> str:
    """Build ~400 words of prose with [1]-[5] citation markers."""
    base = (
        "Research shows important findings in this area [1]. "
        "Multiple studies confirm these results with high confidence [2]. "
        "Experts at leading institutions have validated the approach [3]. "
        "Recent experiments demonstrate significant improvements [4]. "
        "Independent teams replicated outcomes successfully [5]. "
        "Analysis reveals consistent patterns across all datasets. "
        "Several factors contribute to the observed effects. "
        "Controlled trials produced measurable differences. "
        "Statistical methods confirmed the significance of results. "
        "Peer review validated the methodology and conclusions. "
    )
    # ~70 words per repetition; 6 reps gives ~420 words
    return " ".join([base] * 6)


def _seo_json() -> str:
    return json.dumps(
        {
            "title": "Test SEO Title for the Article",
            "description": (
                "A test description that is long enough to pass "
                "validation for the SEO metadata."
            ),
            "keywords": ["test", "seo", "ai"],
        }
    )


def _discoverability_json() -> str:
    return json.dumps(
        {
            "summary": "Test summary of the article content.",
            "key_claims": ["Key claim one [1]", "Key claim two [1]"],
        }
    )


def _make_complete_session() -> ResearchSession:
    findings = [
        FacetFindings(
            facet_index=0,
            sources=[
                SourceDocument(
                    url="https://a.com",
                    title="A",
                    snippet="S",
                    retrieved_at=datetime.now(UTC),
                )
            ],
            claims=["Claim"],
            summary="Summary",
        )
    ]
    return ResearchSession(
        topic_id=uuid4(),
        status="complete",
        started_at=datetime.now(UTC),
        findings_data=[f.model_dump() for f in findings],
        topic_title="Test Topic",
        topic_description="Test desc",
        topic_domain="tech",
    )


def _make_retriever_mock() -> AsyncMock:
    retriever = AsyncMock()
    retriever.retrieve = AsyncMock(
        return_value=[
            ChunkResult(
                text=f"Chunk {i} with detailed research content.",
                source_url=f"https://src{i}.com",
                source_title=f"Source {i}",
                score=0.9 - i * 0.01,
                chunk_index=0,
            )
            for i in range(5)
        ]
    )
    return retriever


async def _make_service(
    session: ResearchSession | None = None,
) -> tuple[ContentService, ResearchSession]:
    session = session or _make_complete_session()
    session_repo = InMemoryResearchSessionRepository()
    await session_repo.create(session)
    queries_json = json.dumps([{"section_index": 0, "queries": ["q1"]}])
    section_body = "Test section body with content. " * 15
    seo_json = json.dumps(
        {
            "title": "T",
            "description": "D",
            "keywords": ["k"],
            "summary": "S",
            "key_claims": ["C"],
            "ai_disclosure": "AI generated",
        }
    )
    chart_json = json.dumps({"charts": []})
    diagram_json = json.dumps({"diagrams": []})
    responses = [
        _outline_json(),
        queries_json,
        section_body,
        section_body,
        seo_json,
        seo_json,
        chart_json,
        diagram_json,
        "pad",
        "pad",
        "pad",
        "pad",
    ]
    llm = FakeListChatModel(responses=responses * 3)
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
        articles=InMemoryArticleRepository(),
    )
    deps = ContentDeps(llm=llm)
    return ContentService(repos, deps), session


class TestGenerateOutline:
    async def test_returns_draft_with_outline(self) -> None:
        svc, session = await _make_service()
        draft = await svc.generate_outline(session.id)
        assert isinstance(draft, ArticleDraft)
        assert draft.outline is not None
        assert draft.status in (
            DraftStatus.OUTLINE_COMPLETE,
            DraftStatus.DRAFT_COMPLETE,
        )
        assert draft.session_id == session.id

    async def test_rejects_unknown_session(self) -> None:
        svc, _ = await _make_service()
        with pytest.raises(NotFoundError):
            await svc.generate_outline(uuid4())

    async def test_rejects_incomplete_session(self) -> None:
        session = ResearchSession(
            topic_id=uuid4(),
            status="planning",
            started_at=datetime.now(UTC),
        )
        svc, _ = await _make_service(session)
        with pytest.raises(ValueError, match="not complete"):
            await svc.generate_outline(session.id)

    async def test_accepts_awaiting_outline_review_session(self) -> None:
        # AUTHOR-002: sessions paused for outline approval must still be
        # loadable (e.g. to regenerate/finalize the outline).
        session = _make_complete_session().model_copy(
            update={"status": "awaiting_outline_review"}
        )
        svc, _ = await _make_service(session)
        draft = await svc.generate_outline(session.id)
        assert draft.session_id == session.id


class TestGetDraft:
    async def test_returns_draft(self) -> None:
        svc, session = await _make_service()
        draft = await svc.generate_outline(session.id)
        retrieved = await svc.get_draft(draft.id)
        assert retrieved.id == draft.id

    async def test_not_found(self) -> None:
        svc, _ = await _make_service()
        with pytest.raises(NotFoundError):
            await svc.get_draft(uuid4())


async def _make_service_with_retriever(
    session: ResearchSession | None = None,
) -> tuple[ContentService, ResearchSession]:
    session = session or _make_complete_session()
    session_repo = InMemoryResearchSessionRepository()
    await session_repo.create(session)

    queries_json = json.dumps([{"section_index": 0, "queries": ["q0"]}])
    draft_text = "Draft text [1] citation [2] about [3] research [4] findings [5]."
    chart_json = json.dumps({"charts": []})
    diagram_json = json.dumps({"diagrams": []})
    one_run = [
        _outline_json(),
        queries_json,
        draft_text,
        draft_text,
        _seo_json(),
        _discoverability_json(),
        chart_json,
        diagram_json,
        "pad",
        "pad",
    ]
    llm = FakeListChatModel(responses=one_run * 3)
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
        articles=InMemoryArticleRepository(),
    )
    retriever = _make_retriever_mock()
    deps = ContentDeps(llm=llm, retriever=retriever)
    return ContentService(repos, deps), session


async def _make_full_pipeline_service(
    session: ResearchSession | None = None,
) -> tuple[ContentService, ResearchSession]:
    """Build a service with 4-section outline for finalize tests.

    Produces enough words (>= 1500) and citations (>= 5) for the
    article assembler validation to pass.
    """
    session = session or _make_complete_session()
    session_repo = InMemoryResearchSessionRepository()
    await session_repo.create(session)

    draft_text = _long_draft_text()
    chart_json = json.dumps({"charts": []})
    diagram_json = json.dumps({"diagrams": []})
    one_run = [
        _four_section_outline_json(),
        _four_section_queries_json(),
        draft_text,
        draft_text,
        draft_text,
        draft_text,
        draft_text,  # redraft (validation)
        _seo_json(),
        _discoverability_json(),
        chart_json,
        diagram_json,
        "pad",
        "pad",
    ]
    llm = FakeListChatModel(responses=one_run * 3)
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
        articles=InMemoryArticleRepository(),
    )
    retriever = _make_retriever_mock()
    deps = ContentDeps(llm=llm, retriever=retriever)
    return ContentService(repos, deps), session


class TestDraftArticle:
    async def test_generate_outline_produces_full_draft(self) -> None:
        """generate_outline now runs the full pipeline."""
        svc, session = await _make_service_with_retriever()
        draft = await svc.generate_outline(session.id)
        assert draft.status in (
            DraftStatus.OUTLINE_COMPLETE,
            DraftStatus.DRAFT_COMPLETE,
        )
        assert draft.outline is not None

    async def test_rejects_unknown_draft(self) -> None:
        svc, _ = await _make_service_with_retriever()
        with pytest.raises(NotFoundError):
            await svc.draft_article(uuid4())

    async def test_rejects_draft_not_outline_complete(self) -> None:
        svc, session = await _make_service_with_retriever()
        draft = ArticleDraft(
            session_id=session.id,
            topic_id=session.topic_id,
            status=DraftStatus.OUTLINE_GENERATING,
            created_at=datetime.now(UTC),
        )
        await svc._repos.drafts.create(draft)
        with pytest.raises(ValueError, match="not ready"):
            await svc.draft_article(draft.id)

    async def test_works_without_retriever(self) -> None:
        """Drafting without retriever logs warning but proceeds."""
        svc, session = await _make_service()  # no retriever
        draft = await svc.generate_outline(session.id)
        assert draft.outline is not None


class TestDraftArticleWithSEO:
    async def test_generate_outline_includes_seo(self) -> None:
        """Full pipeline produces drafts with SEO when it succeeds."""
        svc, session = await _make_service_with_retriever()
        draft = await svc.generate_outline(session.id)
        assert draft.outline is not None


class TestFinalizeArticle:
    async def test_happy_path(self) -> None:
        svc, session = await _make_full_pipeline_service()
        article = await svc.generate_full_article(session.id)
        assert isinstance(article, CanonicalArticle)
        assert article.domain == "tech"

    async def test_rejects_unknown_draft(self) -> None:
        svc, _ = await _make_full_pipeline_service()
        with pytest.raises(NotFoundError):
            await svc.finalize_article(uuid4())

    async def test_rejects_no_seo_result(self) -> None:
        """Finalize with missing SEO uses fallback."""
        svc, session = await _make_full_pipeline_service()
        # generate_full_article handles SEO fallback internally
        article = await svc.generate_full_article(session.id)
        assert article is not None


class TestGetArticle:
    async def test_returns_article(self) -> None:
        svc, session = await _make_full_pipeline_service()
        article = await svc.generate_full_article(session.id)
        retrieved = await svc.get_article(article.id)
        assert retrieved.id == article.id

    async def test_not_found(self) -> None:
        svc, _ = await _make_full_pipeline_service()
        with pytest.raises(NotFoundError):
            await svc.get_article(uuid4())


class TestContentDeps:
    async def test_service_uses_deps(self) -> None:
        svc, session = await _make_service()
        draft = await svc.generate_outline(session.id)
        assert draft.outline is not None


class TestDepsProperty:
    def test_deps_exposes_injected_content_deps(self) -> None:
        from src.services.content import (
            ContentDeps,
            ContentRepositories,
            ContentService,
        )
        from src.services.content_repositories import (
            InMemoryArticleDraftRepository,
            InMemoryArticleRepository,
        )

        llm = FakeListChatModel(responses=["x"])
        deps = ContentDeps(llm=llm)
        repos = ContentRepositories(
            drafts=InMemoryArticleDraftRepository(),
            research=None,  # type: ignore[arg-type]
            articles=InMemoryArticleRepository(),
        )
        assert ContentService(repos, deps).deps is deps


# --- AUTHOR-011 Task 9 — voice state seeded into the run, drafter carries it ---


class _CountingPersonaRepo(InMemoryPersonaRepository):
    """Counts `.get()` calls so a flag-off run can assert the repo is
    never touched."""

    def __init__(self) -> None:
        super().__init__()
        self.get_calls = 0

    async def get(self, persona_id: UUID):  # type: ignore[override]
        self.get_calls += 1
        return await super().get(persona_id)


async def _ready_voice_repo(
    repo_cls: type[InMemoryPersonaRepository] = InMemoryPersonaRepository,
) -> tuple[InMemoryPersonaRepository, UUID]:
    """Fingerprint built from the exact text every section will draft
    (`_long_draft_text()`), so every section scores ~100 and the voice
    fix pass never fires — a fix pass would consume an extra FakeLLM
    response and desync the fixed response queue below (L-007)."""
    repo = repo_cls()
    persona = await repo.create("owner-1", PersonaCreate(name="Voice"))
    sample_text = _long_draft_text()
    for _ in range(5):
        await repo.add_sample(persona.id, SampleCreate(text=sample_text))
    samples = await repo.list_samples(persona.id)
    fp = build_fingerprint([s.text for s in samples])
    await repo.set_fingerprint(persona.id, fp)
    return repo, persona.id


async def _make_voice_service(
    persona_repo: InMemoryPersonaRepository,
    persona_id: UUID,
    *,
    enable_voice_engine: bool,
) -> tuple[ContentService, ResearchSession]:
    session = _make_complete_session().model_copy(
        update={"voice_persona_id": persona_id}
    )
    session_repo = InMemoryResearchSessionRepository()
    await session_repo.create(session)
    draft_text = _long_draft_text()
    chart_json = json.dumps({"charts": []})
    diagram_json = json.dumps({"diagrams": []})
    one_run = [
        _four_section_outline_json(),
        _four_section_queries_json(),
        draft_text,
        draft_text,
        draft_text,
        draft_text,
        draft_text,  # redraft (validation)
        _seo_json(),
        _discoverability_json(),
        chart_json,
        diagram_json,
        "pad",
        "pad",
    ]
    llm = FakeListChatModel(responses=one_run * 3)
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
        articles=InMemoryArticleRepository(),
    )
    retriever = _make_retriever_mock()
    settings = Settings(_env_file=None, enable_voice_engine=enable_voice_engine)
    deps = ContentDeps(
        llm=llm, retriever=retriever, settings=settings, persona_repo=persona_repo
    )
    return ContentService(repos, deps), session


async def _run_and_capture_system_prompts(
    svc: ContentService, session_id: UUID
) -> list[str]:
    """Run the full pipeline, recording every drafter system prompt built."""
    captured: list[str] = []
    original = section_prompt.build_system_prompt

    def _capture(section: object, ctx: object) -> str:
        result = original(section, ctx)  # type: ignore[arg-type]
        captured.append(result)
        return result

    with patch.object(section_prompt, "build_system_prompt", side_effect=_capture):
        await svc.generate_full_article(session_id)
    return captured


class TestVoiceStateInjection:
    async def test_drafter_system_prompt_carries_voice_block_when_flag_on(
        self,
    ) -> None:
        persona_repo, persona_id = await _ready_voice_repo()
        svc, session = await _make_voice_service(
            persona_repo, persona_id, enable_voice_engine=True
        )
        captured = await _run_and_capture_system_prompts(svc, session.id)
        assert any("Voice." in c for c in captured)

    async def test_no_voice_block_and_repo_untouched_when_flag_off(self) -> None:
        persona_repo, persona_id = await _ready_voice_repo(_CountingPersonaRepo)
        svc, session = await _make_voice_service(
            persona_repo, persona_id, enable_voice_engine=False
        )
        captured = await _run_and_capture_system_prompts(svc, session.id)
        assert not any("Voice." in c for c in captured)
        assert isinstance(persona_repo, _CountingPersonaRepo)
        assert persona_repo.get_calls == 0
