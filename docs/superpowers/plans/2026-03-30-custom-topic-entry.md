# Custom Topic Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to manually enter topics with LLM-powered auto-fill of metadata, and add per-article customization (audience, tone, angle) to the content pipeline.

**Architecture:** New `POST /topics/analyze` endpoint uses Claude Sonnet to suggest metadata from a title. New `POST /topics` endpoint creates manual topics. Research sessions gain three nullable columns for per-article params. Content pipeline nodes read per-article params with fallback to global settings. Frontend gets a Create Topic modal with auto-fill UX and the existing Generate Article modal gets per-article customization.

**Tech Stack:** Python/FastAPI (backend), Alembic (migration), LangChain (LLM call), Next.js/React (frontend), pytest + Vitest (testing)

**Spec:** `docs/superpowers/specs/2026-03-30-custom-topic-entry-design.md`

---

### Task 1: DB Migration — Add per-article params to research_sessions

**Files:**
- Create: `alembic/versions/xxxx_add_article_params_to_research_sessions.py` (auto-generated)
- Modify: `src/db/tables.py:54-82`
- Modify: `src/models/research_db.py:13-30`

- [ ] **Step 1: Add columns to SQLAlchemy model**

In `src/db/tables.py`, add three nullable columns to `ResearchSessionRow` after line 76 (`findings_data`):

```python
    target_audience: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_tone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_angle: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

- [ ] **Step 2: Add fields to Pydantic model**

In `src/models/research_db.py`, add three fields to the `ResearchSession` class after `topic_domain`:

```python
    target_audience: str | None = None
    content_tone: str | None = None
    preferred_angle: str | None = None
```

- [ ] **Step 3: Generate Alembic migration**

Run: `uv run alembic revision --autogenerate -m "add per-article params to research_sessions"`
Expected: New migration file created in `alembic/versions/`

- [ ] **Step 4: Apply migration**

Run: `uv run alembic upgrade head`
Expected: Migration applies successfully (if DB is available), or note this for Docker setup.

- [ ] **Step 5: Update PgResearchSessionRepository**

In `src/db/repositories.py`, update the `PgResearchSessionRepository.create` method to include the new fields when creating a `ResearchSessionRow`. Find the `create` method (around line 55-90) and add:

```python
            row.target_audience = session.target_audience
            row.content_tone = session.content_tone
            row.preferred_angle = session.preferred_angle
```

Also update the `_to_model` method to read these fields back:

```python
            target_audience=row.target_audience,
            content_tone=row.content_tone,
            preferred_angle=row.preferred_angle,
```

- [ ] **Step 6: Commit**

```bash
git add src/db/tables.py src/models/research_db.py src/db/repositories.py alembic/
git commit -m "feat: add per-article params (audience, tone, angle) to research_sessions"
```

---

### Task 2: Topic Analysis Endpoint (Backend)

**Files:**
- Create: `src/services/topic_analyzer.py`
- Create: `src/api/schemas/topic_analysis.py`
- Modify: `src/api/routers/topics.py`
- Test: `tests/unit/test_topic_analyzer.py`

- [ ] **Step 1: Write failing test for topic analyzer service**

Create `tests/unit/test_topic_analyzer.py`:

```python
"""Tests for the topic analyzer service."""

import pytest
from unittest.mock import AsyncMock

from src.services.topic_analyzer import TopicAnalyzer, TopicAnalysisResult


@pytest.mark.asyncio
async def test_analyze_topic_returns_all_fields():
    """Analyzer returns description, domain, keywords, audience, tone, angle."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AsyncMock(
        content='{"description": "An exploration of zero trust security", '
        '"domain": "cybersecurity", '
        '"keywords": ["zero trust", "cloud-native"], '
        '"target_audience": "Security engineers", '
        '"content_tone": "technical-authoritative", '
        '"preferred_angle": "Implementation guide"}'
    )
    analyzer = TopicAnalyzer(llm=mock_llm)
    result = await analyzer.analyze("Zero Trust Architecture")
    assert isinstance(result, TopicAnalysisResult)
    assert result.description == "An exploration of zero trust security"
    assert result.domain == "cybersecurity"
    assert result.keywords == ["zero trust", "cloud-native"]
    assert result.target_audience == "Security engineers"
    assert result.content_tone == "technical-authoritative"
    assert result.preferred_angle == "Implementation guide"


@pytest.mark.asyncio
async def test_analyze_topic_with_configured_domains():
    """Analyzer includes configured domains in prompt context."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AsyncMock(
        content='{"description": "desc", "domain": "ai-ml", '
        '"keywords": ["llm"], "target_audience": "ML engineers", '
        '"content_tone": "educational", "preferred_angle": "Tutorial"}'
    )
    analyzer = TopicAnalyzer(llm=mock_llm)
    result = await analyzer.analyze(
        "Fine-tuning LLMs",
        configured_domains=["cybersecurity", "ai-ml", "cloud"],
    )
    assert result.domain == "ai-ml"
    # Verify domains were passed in the prompt
    call_args = mock_llm.ainvoke.call_args[0][0]
    prompt_text = str(call_args[-1].content)
    assert "cybersecurity" in prompt_text
    assert "ai-ml" in prompt_text


@pytest.mark.asyncio
async def test_analyze_regenerate_single_field():
    """Regenerate only the specified field, keeping others stable."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AsyncMock(
        content='{"description": "desc", "domain": "cybersecurity", '
        '"keywords": ["microsegmentation", "sase", "ztna"], '
        '"target_audience": "Security engineers", '
        '"content_tone": "technical-authoritative", '
        '"preferred_angle": "Implementation guide"}'
    )
    analyzer = TopicAnalyzer(llm=mock_llm)
    current = TopicAnalysisResult(
        description="desc",
        domain="cybersecurity",
        keywords=["zero trust"],
        target_audience="Security engineers",
        content_tone="technical-authoritative",
        preferred_angle="Implementation guide",
    )
    result = await analyzer.analyze(
        "Zero Trust Architecture",
        regenerate_field="keywords",
        current_values=current,
    )
    assert isinstance(result, TopicAnalysisResult)
    # Verify regenerate instruction was in prompt
    call_args = mock_llm.ainvoke.call_args[0][0]
    prompt_text = str(call_args[-1].content)
    assert "keywords" in prompt_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_topic_analyzer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.topic_analyzer'`

- [ ] **Step 3: Create TopicAnalysisResult schema**

Create `src/api/schemas/topic_analysis.py`:

```python
"""Schemas for topic analysis API."""

from pydantic import BaseModel, Field


VALID_TONES = [
    "technical-authoritative",
    "conversational",
    "educational",
    "analytical",
    "news-reporting",
]


class TopicAnalysisResult(BaseModel):
    """LLM-suggested metadata for a topic."""

    description: str
    domain: str
    keywords: list[str] = Field(max_length=10)
    target_audience: str
    content_tone: str
    preferred_angle: str


class AnalyzeTopicRequest(BaseModel):
    """Request body for POST /topics/analyze."""

    title: str = Field(min_length=3, max_length=500)
    regenerate_field: str | None = None
    current_values: TopicAnalysisResult | None = None


class ManualTopicCreateRequest(BaseModel):
    """Request body for POST /topics."""

    title: str = Field(min_length=3, max_length=500)
    description: str = Field(max_length=2000)
    domain: str = Field(max_length=100)
    keywords: list[str] = Field(default_factory=list, max_length=10)


class ManualTopicResult(BaseModel):
    """Response for POST /topics."""

    topic: "PersistedTopic"  # noqa: F821 — forward ref resolved at import
    is_duplicate: bool = False
    duplicate_of: str | None = None


# Avoid circular import — resolve forward ref at module level
from src.api.schemas.topics import PersistedTopic  # noqa: E402

ManualTopicResult.model_rebuild()
```

- [ ] **Step 4: Implement TopicAnalyzer service**

Create `src/services/topic_analyzer.py`:

```python
"""Topic analysis service — LLM-powered metadata suggestion."""

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.api.schemas.topic_analysis import VALID_TONES, TopicAnalysisResult
from src.utils.llm_json import parse_llm_json

logger = structlog.get_logger()

_SYSTEM_PROMPT = (
    "You are an expert content strategist. Given a topic title, suggest "
    "metadata for article generation. Return valid JSON only."
)

_USER_TEMPLATE = (
    "Analyze this topic and suggest article metadata:\n\n"
    "Title: {title}\n\n"
    "{domains_section}"
    "Return JSON with these fields:\n"
    '- "description": 1-2 sentence description of the topic\n'
    '- "domain": best-fit domain for this topic\n'
    '- "keywords": 3-5 keywords for research\n'
    '- "target_audience": who should read this article\n'
    '- "content_tone": one of {valid_tones}\n'
    '- "preferred_angle": suggested editorial angle\n'
)

_REGENERATE_TEMPLATE = (
    "Regenerate ONLY the '{field}' field for this topic.\n\n"
    "Title: {title}\n\n"
    "Current values (keep all except {field}):\n"
    "{current_json}\n\n"
    "Return the full JSON with only '{field}' changed."
)

_MAX_RETRIES = 2


class TopicAnalyzer:
    """Analyzes a topic title and suggests metadata via LLM."""

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

    async def analyze(
        self,
        title: str,
        configured_domains: list[str] | None = None,
        regenerate_field: str | None = None,
        current_values: TopicAnalysisResult | None = None,
    ) -> TopicAnalysisResult:
        """Analyze a topic title and return suggested metadata."""
        if regenerate_field and current_values:
            return await self._regenerate(
                title, regenerate_field, current_values
            )
        return await self._full_analyze(title, configured_domains)

    async def _full_analyze(
        self,
        title: str,
        configured_domains: list[str] | None,
    ) -> TopicAnalysisResult:
        """Full analysis — suggest all fields."""
        domains_section = ""
        if configured_domains:
            domains_section = (
                f"Available domains: {', '.join(configured_domains)}\n"
                "Prefer one of these domains if the topic fits.\n\n"
            )
        user_msg = _USER_TEMPLATE.format(
            title=title,
            domains_section=domains_section,
            valid_tones=", ".join(VALID_TONES),
        )
        return await self._call_llm(user_msg)

    async def _regenerate(
        self,
        title: str,
        field: str,
        current: TopicAnalysisResult,
    ) -> TopicAnalysisResult:
        """Regenerate a single field, keeping others stable."""
        user_msg = _REGENERATE_TEMPLATE.format(
            title=title,
            field=field,
            current_json=current.model_dump_json(indent=2),
        )
        return await self._call_llm(user_msg)

    async def _call_llm(self, user_msg: str) -> TopicAnalysisResult:
        """Call LLM and parse response."""
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ]
        for attempt in range(_MAX_RETRIES):
            response = await self._llm.ainvoke(messages)
            try:
                data = parse_llm_json(str(response.content))
                result = TopicAnalysisResult.model_validate(data)
                logger.info("topic_analysis_complete", domain=result.domain)
                return result
            except Exception as exc:
                logger.warning(
                    "topic_analysis_parse_failed",
                    attempt=attempt + 1,
                    error=str(exc),
                )
        msg = f"Topic analysis failed after {_MAX_RETRIES} attempts"
        raise ValueError(msg)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_topic_analyzer.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/services/topic_analyzer.py src/api/schemas/topic_analysis.py tests/unit/test_topic_analyzer.py
git commit -m "feat: add topic analyzer service with LLM-powered metadata suggestion"
```

---

### Task 3: Manual Topic Creation Endpoint (Backend)

**Files:**
- Modify: `src/api/routers/topics.py`
- Modify: `src/db/repositories.py:259-412` (PgTopicRepository)
- Test: `tests/unit/test_manual_topic_creation.py`

- [ ] **Step 1: Write failing test for manual topic creation**

Create `tests/unit/test_manual_topic_creation.py`:

```python
"""Tests for manual topic creation."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.api.schemas.topic_analysis import ManualTopicCreateRequest


@pytest.mark.asyncio
async def test_create_manual_topic():
    """Create a manual topic with source='manual' and trend_score=0."""
    from src.db.repositories import PgTopicRepository

    mock_sf = MagicMock()
    mock_session = AsyncMock()
    mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

    repo = PgTopicRepository(mock_sf)
    req = ManualTopicCreateRequest(
        title="Zero Trust Architecture",
        description="An exploration of zero trust",
        domain="cybersecurity",
        keywords=["zero trust", "cloud-native"],
    )
    topic_id = await repo.create_manual(req)
    assert topic_id is not None
    # Verify TopicRow was added with source="manual"
    add_call = mock_session.add.call_args[0][0]
    assert add_call.source == "manual"
    assert add_call.trend_score == 0.0
    assert add_call.velocity == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_manual_topic_creation.py -v`
Expected: FAIL — `AttributeError: 'PgTopicRepository' object has no attribute 'create_manual'`

- [ ] **Step 3: Add `create_manual` method to PgTopicRepository**

In `src/db/repositories.py`, add a new method to `PgTopicRepository` after `create_from_ranked` (around line 328):

```python
    async def create_manual(
        self,
        req: "ManualTopicCreateRequest",
    ) -> UUID:
        """Insert a manually created topic."""
        from datetime import UTC, datetime

        topic_id = uuid4()
        async with self._sf() as session:
            row = TopicRow(
                id=topic_id,
                title=req.title,
                description=req.description,
                source="manual",
                external_url="",
                trend_score=0.0,
                velocity=0.0,
                domain=req.domain,
                discovered_at=datetime.now(UTC),
                domain_keywords=req.keywords,
                composite_score=None,
                rank=None,
                source_count=1,
            )
            session.add(row)
            await session.commit()
        logger.debug(
            "manual_topic_created",
            topic_id=str(topic_id),
            domain=req.domain,
        )
        return topic_id
```

Add the import at the top of `repositories.py` (TYPE_CHECKING block):

```python
    from src.api.schemas.topic_analysis import ManualTopicCreateRequest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_manual_topic_creation.py -v`
Expected: PASS

- [ ] **Step 5: Add API routes for analyze and create**

In `src/api/routers/topics.py`, add the two new endpoints. Add imports at the top:

```python
from src.api.schemas.topic_analysis import (
    AnalyzeTopicRequest,
    ManualTopicCreateRequest,
    ManualTopicResult,
    TopicAnalysisResult,
)
from src.api.dependencies import require_editor_or_above
from src.services.topic_analyzer import TopicAnalyzer
```

Add the endpoints after the existing `list_topics` endpoint:

```python
@limiter.limit("5/minute")
@topics_router.post(
    "/topics/analyze",
    response_model=TopicAnalysisResult,
    summary="Analyze a topic title and suggest metadata",
)
async def analyze_topic(
    request: Request,
    body: AnalyzeTopicRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> TopicAnalysisResult:
    llm = getattr(request.app.state, "drafting_llm", None)
    if llm is None:
        raise ServiceUnavailableError(
            message="LLM not configured. Set COGNIFY_ANTHROPIC_API_KEY."
        )
    domains: list[str] = []
    domain_repo = getattr(request.app.state, "domain_config_repo", None)
    if domain_repo is not None:
        domains = await domain_repo.list_domain_names()
    analyzer = TopicAnalyzer(llm=llm)
    return await analyzer.analyze(
        title=body.title,
        configured_domains=domains or None,
        regenerate_field=body.regenerate_field,
        current_values=body.current_values,
    )


@limiter.limit("10/minute")
@topics_router.post(
    "/topics",
    response_model=ManualTopicResult,
    summary="Create a manual topic",
    status_code=201,
)
async def create_manual_topic(
    request: Request,
    body: ManualTopicCreateRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> ManualTopicResult:
    repo = request.app.state.topic_repo
    # Dedup check via embedding similarity
    embedding_svc = _get_embedding_service(request)
    persistence_svc = request.app.state.topic_persistence_service
    existing_id = await persistence_svc.find_duplicate_by_title(
        body.title, body.domain, embedding_svc,
    )
    if existing_id is not None:
        items, _ = await repo.list_by_domain("", 1, 1)
        # Fetch the specific topic
        from src.api.schemas.topics import PersistedTopic
        topic_input = await repo.get(existing_id)
        if topic_input:
            existing_items, _ = await repo.list_by_domain(body.domain, 1, 500)
            match = next((t for t in existing_items if t.id == existing_id), None)
            if match:
                return ManualTopicResult(
                    topic=match,
                    is_duplicate=True,
                    duplicate_of=str(existing_id),
                )
    topic_id = await repo.create_manual(body)
    # Fetch the newly created topic for response
    new_items, _ = await repo.list_by_domain(body.domain, 1, 500)
    created = next((t for t in new_items if t.id == topic_id), None)
    if created is None:
        raise ServiceUnavailableError(message="Topic created but not found")
    return ManualTopicResult(topic=created, is_duplicate=False)
```

- [ ] **Step 6: Add `find_duplicate_by_title` to TopicPersistenceService**

In `src/services/topic_persistence.py`, add a method to check for duplicate topics by title embedding:

```python
    async def find_duplicate_by_title(
        self,
        title: str,
        domain: str,
        embedding_service: "EmbeddingService",
    ) -> UUID | None:
        """Check if a similar topic already exists. Returns topic_id if found."""
        from src.api.schemas.topics import RawTopic
        from datetime import UTC, datetime

        # Get existing topics for the domain
        existing, _ = await self._repo.list_by_domain(domain, 1, 200)
        if not existing:
            return None

        existing_titles = [t.title for t in existing]
        try:
            new_emb = embedding_service.embed([title])[0]
            existing_embs = embedding_service.embed(existing_titles)
        except Exception:
            return None

        import numpy as np
        for i, emb in enumerate(existing_embs):
            similarity = float(
                np.dot(new_emb, emb)
                / (np.linalg.norm(new_emb) * np.linalg.norm(emb) + 1e-9)
            )
            if similarity >= 0.85:
                return existing[i].id
        return None
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/unit/test_manual_topic_creation.py tests/unit/test_topic_analyzer.py -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/api/routers/topics.py src/db/repositories.py src/services/topic_persistence.py src/api/schemas/topic_analysis.py tests/unit/test_manual_topic_creation.py
git commit -m "feat: add manual topic creation and analysis API endpoints"
```

---

### Task 4: Extend Research Session Creation with Per-Article Params

**Files:**
- Modify: `src/api/schemas/research.py:9-10`
- Modify: `src/api/routers/research.py:83-104`
- Modify: `src/services/research.py:136-140`
- Test: `tests/unit/test_research_session_params.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_research_session_params.py`:

```python
"""Tests for per-article params on research sessions."""

import pytest
from datetime import UTC, datetime
from uuid import uuid4
from unittest.mock import AsyncMock

from src.models.research_db import ResearchSession
from src.services.research import (
    InMemoryResearchSessionRepository,
    InMemoryAgentStepRepository,
    InMemoryTopicRepository,
    ResearchRepositories,
    ResearchService,
)
from src.models.research import TopicInput


@pytest.mark.asyncio
async def test_start_session_with_article_params():
    """Session stores per-article params when provided."""
    topic = TopicInput(
        id=uuid4(),
        title="Test Topic",
        description="desc",
        domain="tech",
    )
    session_repo = InMemoryResearchSessionRepository()
    step_repo = InMemoryAgentStepRepository()
    topic_repo = InMemoryTopicRepository()
    topic_repo.seed(topic)

    mock_orch = AsyncMock()
    repos = ResearchRepositories(
        sessions=session_repo, steps=step_repo, topics=topic_repo
    )
    svc = ResearchService(repos=repos, orchestrator=mock_orch)

    session = await svc.start_session(
        topic.id,
        target_audience="Security engineers",
        content_tone="technical-authoritative",
        preferred_angle="Implementation guide",
    )
    assert session.target_audience == "Security engineers"
    assert session.content_tone == "technical-authoritative"
    assert session.preferred_angle == "Implementation guide"


@pytest.mark.asyncio
async def test_start_session_without_article_params():
    """Session works without per-article params (backward compatible)."""
    topic = TopicInput(
        id=uuid4(),
        title="Test Topic",
        description="desc",
        domain="tech",
    )
    session_repo = InMemoryResearchSessionRepository()
    step_repo = InMemoryAgentStepRepository()
    topic_repo = InMemoryTopicRepository()
    topic_repo.seed(topic)

    mock_orch = AsyncMock()
    repos = ResearchRepositories(
        sessions=session_repo, steps=step_repo, topics=topic_repo
    )
    svc = ResearchService(repos=repos, orchestrator=mock_orch)

    session = await svc.start_session(topic.id)
    assert session.target_audience is None
    assert session.content_tone is None
    assert session.preferred_angle is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_research_session_params.py -v`
Expected: FAIL — `TypeError: start_session() got an unexpected keyword argument 'target_audience'`

- [ ] **Step 3: Update CreateResearchSessionRequest schema**

In `src/api/schemas/research.py`, add optional fields to `CreateResearchSessionRequest`:

```python
class CreateResearchSessionRequest(BaseModel):
    topic_id: UUID
    target_audience: str | None = None
    content_tone: str | None = None
    preferred_angle: str | None = None
```

- [ ] **Step 4: Update ResearchService.start_session**

In `src/services/research.py`, update `start_session` to accept and store per-article params:

```python
    async def start_session(
        self,
        topic_id: UUID,
        target_audience: str | None = None,
        content_tone: str | None = None,
        preferred_angle: str | None = None,
    ) -> ResearchSession:
        if not await self._repos.topics.exists(topic_id):
            raise NotFoundError(f"Topic {topic_id} not found")
        session = ResearchSession(
            topic_id=topic_id,
            started_at=datetime.now(UTC),
            target_audience=target_audience,
            content_tone=content_tone,
            preferred_angle=preferred_angle,
        )
        return await self._repos.sessions.create(session)
```

- [ ] **Step 5: Update the API route to pass params**

In `src/api/routers/research.py`, update `create_research_session` (line 90):

```python
    session = await svc.start_session(
        body.topic_id,
        target_audience=body.target_audience,
        content_tone=body.content_tone,
        preferred_angle=body.preferred_angle,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_research_session_params.py -v`
Expected: All 2 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/api/schemas/research.py src/services/research.py src/api/routers/research.py tests/unit/test_research_session_params.py
git commit -m "feat: extend research session creation with per-article params"
```

---

### Task 5: Thread Per-Article Params Through Content Pipeline

**Files:**
- Modify: `src/agents/content/pipeline.py:54-71` (ContentState)
- Modify: `src/services/content.py:100-134` (generate_full_article)
- Modify: `src/agents/content/outline_generator.py:21-45` (prompts)
- Modify: `src/agents/content/section_drafter.py:25-36` (system prompt)
- Modify: `src/agents/content/humanize_node.py:64-84` (_run_humanize)
- Modify: `src/agents/content/seo_node.py:77-107` (_run_seo)
- Test: `tests/unit/test_pipeline_article_params.py`

- [ ] **Step 1: Write failing test for pipeline state params**

Create `tests/unit/test_pipeline_article_params.py`:

```python
"""Tests for per-article params in content pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.content.pipeline import ContentState


def test_content_state_accepts_article_params():
    """ContentState TypedDict accepts per-article params."""
    state: ContentState = {
        "topic": MagicMock(),
        "research_plan": None,
        "findings": [],
        "session_id": MagicMock(),
        "outline": None,
        "status": "outline_generating",
        "error": None,
        "target_audience": "Security engineers",
        "content_tone": "technical-authoritative",
        "preferred_angle": "Implementation guide",
    }
    assert state["target_audience"] == "Security engineers"
    assert state["content_tone"] == "technical-authoritative"
    assert state["preferred_angle"] == "Implementation guide"


def test_content_state_works_without_article_params():
    """ContentState works without per-article params (backward compatible)."""
    state: ContentState = {
        "topic": MagicMock(),
        "research_plan": None,
        "findings": [],
        "session_id": MagicMock(),
        "outline": None,
        "status": "outline_generating",
        "error": None,
    }
    assert state.get("target_audience") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_pipeline_article_params.py -v`
Expected: FAIL (or type error) — `target_audience` not in ContentState

- [ ] **Step 3: Add per-article params to ContentState**

In `src/agents/content/pipeline.py`, add three fields to `ContentState` (after line 70, `visuals`):

```python
    target_audience: NotRequired[str | None]
    content_tone: NotRequired[str | None]
    preferred_angle: NotRequired[str | None]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_pipeline_article_params.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Update ContentService.generate_full_article to pass params**

In `src/services/content.py`, update `generate_full_article` (around line 124-134) to read per-article params from the session and pass them to the graph:

```python
        result: dict[str, object] = await graph.ainvoke(
            {
                "topic": topic,
                "research_plan": None,
                "findings": findings,
                "session_id": topic.id,
                "outline": None,
                "status": "outline_generating",
                "error": None,
                "target_audience": session.target_audience,
                "content_tone": session.content_tone,
                "preferred_angle": session.preferred_angle,
            }
        )
```

Also update `_run_pipeline` and `_run_drafting` similarly to pass the params (for the separate outline/draft API flows). These methods don't currently have the session, so add a `session` parameter or read from the existing session that's already loaded. The simplest approach: update `generate_outline` and `draft_article` to pass `None` for the params (preserving existing behavior):

In `_run_pipeline` (line 295-315), add the three `None` params to the `ainvoke` dict:

```python
                "target_audience": None,
                "content_tone": None,
                "preferred_angle": None,
```

In `_run_drafting` (line 317-340), add the same three `None` params.

- [ ] **Step 6: Update outline_generator.py prompts**

In `src/agents/content/outline_generator.py`, update `_USER_TEMPLATE` (line 33-45) to include conditional audience and angle sections. Update `generate_outline` function to accept optional params:

Replace the `generate_outline` function signature and user message building:

```python
async def generate_outline(
    topic: TopicInput,
    findings: list[FacetFindings],
    llm: BaseChatModel,
    target_audience: str | None = None,
    preferred_angle: str | None = None,
) -> ArticleOutline:
    """Generate an article outline from topic and findings."""
    logger.info("outline_generation_started", topic_title=topic.title)

    audience_section = ""
    if target_audience:
        audience_section = f"Target audience: {target_audience}\n"
    angle_section = ""
    if preferred_angle:
        angle_section = f"Editorial angle: {preferred_angle}\n"

    user_msg = _USER_TEMPLATE.format(
        title=topic.title,
        description=topic.description,
        domain=topic.domain,
        findings_summary=_summarize_findings(findings),
        schema_hint=_SCHEMA_HINT,
    )
    # Insert audience/angle before "Requirements:" line
    if audience_section or angle_section:
        user_msg = user_msg.replace(
            "Requirements:\n",
            f"{audience_section}{angle_section}\nRequirements:\n",
        )
```

Update `make_outline_node` in `nodes.py` to pass params from state:

```python
        try:
            outline = await generate_outline(
                topic,
                findings,
                llm,
                target_audience=state.get("target_audience"),
                preferred_angle=state.get("preferred_angle"),
            )
```

- [ ] **Step 7: Update section_drafter.py prompts**

In `src/agents/content/section_drafter.py`, update `_SYSTEM_PROMPT` to accept audience and tone. Update `DraftingContext` to include per-article params:

Add fields to `DraftingContext`:

```python
@dataclass(frozen=True)
class DraftingContext:
    """Shared dependencies for section drafting."""

    retriever: MilvusRetriever | None
    topic_id: str
    llm: BaseChatModel
    prior_drafts: list[SectionDraft]
    target_audience: str | None = None
    content_tone: str | None = None
```

Update `_call_llm` to include audience/tone in the system prompt:

```python
async def _call_llm(
    section: OutlineSection,
    chunks: list[ChunkResult],
    ctx: DraftingContext,
) -> str:
    """Build prompt and call LLM to draft section text."""
    system = _SYSTEM_PROMPT.format(
        target_word_count=section.target_word_count,
    )
    if ctx.target_audience:
        system += f"\nWrite for this audience: {ctx.target_audience}."
    if ctx.content_tone:
        system += f"\nTone: {ctx.content_tone}."
    user = _build_user_prompt(section, chunks, ctx.prior_drafts)
    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    response = await ctx.llm.ainvoke(messages)
    return str(response.content)
```

Update `make_draft_node` in `nodes.py` to pass params to DraftingContext:

```python
            ctx = DraftingContext(
                retriever=retriever,
                topic_id=str(topic.id),
                llm=llm,
                prior_drafts=list(drafts),
                target_audience=state.get("target_audience"),
                content_tone=state.get("content_tone"),
            )
```

- [ ] **Step 8: Update seo_node.py to include audience**

In `src/agents/content/seo_node.py`, update `_run_seo` to pass audience to `generate_seo_metadata`. The `generate_seo_metadata` function in `seo_optimizer.py` takes `(title, body_text, llm)` — add an optional `target_audience` param:

In `seo_node.py`, update the call:

```python
    seo = await generate_seo_metadata(
        outline.title,
        body_text,
        llm,
        target_audience=state.get("target_audience"),
    )
```

In `src/agents/content/seo_optimizer.py`, update `generate_seo_metadata` to accept `target_audience`:

```python
async def generate_seo_metadata(
    title: str,
    body_text: str,
    llm: BaseChatModel,
    target_audience: str | None = None,
) -> SEOMetadata:
```

And include it in the prompt if provided:

```python
    audience_hint = ""
    if target_audience:
        audience_hint = f"\nTarget audience: {target_audience}. Optimize keywords for what this audience searches."
    # Add audience_hint to the user message
```

- [ ] **Step 9: Run all backend tests**

Run: `uv run pytest tests/unit/ -q`
Expected: All tests PASS (no regressions)

- [ ] **Step 10: Commit**

```bash
git add src/agents/content/pipeline.py src/services/content.py src/agents/content/outline_generator.py src/agents/content/nodes.py src/agents/content/section_drafter.py src/agents/content/humanize_node.py src/agents/content/seo_node.py src/agents/content/seo_optimizer.py tests/unit/test_pipeline_article_params.py
git commit -m "feat: thread per-article params through content pipeline nodes"
```

---

### Task 6: Frontend — API Functions and Types

**Files:**
- Modify: `frontend/src/lib/api/trends.ts`
- Modify: `frontend/src/types/api.ts`
- Test: (covered by component tests in Task 8)

- [ ] **Step 1: Add TypeScript types**

In `frontend/src/types/api.ts`, add new types after `GenerateArticleResponse` (line 76):

```typescript
export interface TopicAnalysisResult {
  description: string;
  domain: string;
  keywords: string[];
  target_audience: string;
  content_tone: string;
  preferred_angle: string;
}

export interface AnalyzeTopicRequest {
  title: string;
  regenerate_field?: string | null;
  current_values?: TopicAnalysisResult | null;
}

export interface ManualTopicCreateRequest {
  title: string;
  description: string;
  domain: string;
  keywords: string[];
}

export interface ManualTopicResult {
  topic: import("@/lib/api/trends").PersistedTopic;
  is_duplicate: boolean;
  duplicate_of: string | null;
}

export type ContentTone =
  | "technical-authoritative"
  | "conversational"
  | "educational"
  | "analytical"
  | "news-reporting";

export interface ArticleParams {
  target_audience?: string;
  content_tone?: ContentTone;
  preferred_angle?: string;
}
```

- [ ] **Step 2: Add API functions**

In `frontend/src/lib/api/trends.ts`, add new functions after `createResearchSession`:

```typescript
export async function analyzeTopic(
  title: string,
  regenerateField?: string | null,
  currentValues?: import("@/types/api").TopicAnalysisResult | null,
): Promise<import("@/types/api").TopicAnalysisResult> {
  const { data } = await apiClient.post<import("@/types/api").TopicAnalysisResult>(
    "/topics/analyze",
    {
      title,
      regenerate_field: regenerateField ?? null,
      current_values: currentValues ?? null,
    },
    { timeout: 30000 },
  );
  return data;
}

export async function createManualTopic(
  req: import("@/types/api").ManualTopicCreateRequest,
): Promise<import("@/types/api").ManualTopicResult> {
  const { data } = await apiClient.post<import("@/types/api").ManualTopicResult>(
    "/topics",
    req,
  );
  return data;
}
```

Update `createResearchSession` to accept optional article params:

```typescript
export async function createResearchSession(
  topicId: string,
  articleParams?: import("@/types/api").ArticleParams,
): Promise<CreateSessionResponse> {
  const { data } = await apiClient.post<CreateSessionResponse>("/research/sessions", {
    topic_id: topicId,
    ...articleParams,
  });
  return data;
}
```

- [ ] **Step 3: Add "Manual" source label**

In `frontend/src/types/sources.ts`, add "manual" to the source names and labels:

```typescript
export const SOURCE_NAMES = [
  "google_trends",
  "reddit",
  "hackernews",
  "newsapi",
  "arxiv",
  "manual",
] as const;

export const SOURCE_LABELS: Record<SourceName, string> = {
  google_trends: "Google Trends",
  reddit: "Reddit",
  hackernews: "Hacker News",
  newsapi: "NewsAPI",
  arxiv: "arXiv",
  manual: "Manual",
};
```

This ensures manual topics display "Manual" in the topic card source label rather than the raw string "manual".

- [ ] **Step 4: Commit**

```bash
cd frontend && git add src/types/api.ts src/lib/api/trends.ts src/types/sources.ts
git commit -m "feat: add frontend API functions for topic analysis and manual creation"
```

---

### Task 7: Frontend — Create Topic Modal Component

**Files:**
- Create: `frontend/src/components/topics/create-topic-modal.tsx`
- Create: `frontend/src/hooks/use-topic-analysis.ts`
- Modify: `frontend/src/app/(dashboard)/topics/page.tsx`

- [ ] **Step 1: Create useTopicAnalysis hook**

Create `frontend/src/hooks/use-topic-analysis.ts`:

```typescript
"use client";

import { useState, useCallback } from "react";
import { analyzeTopic } from "@/lib/api/trends";
import type { TopicAnalysisResult } from "@/types/api";

interface UseTopicAnalysisReturn {
  analysis: TopicAnalysisResult | null;
  isAnalyzing: boolean;
  isRegenerating: string | null;
  error: string | null;
  analyze: (title: string) => Promise<void>;
  regenerateField: (title: string, field: string) => Promise<void>;
  updateField: <K extends keyof TopicAnalysisResult>(
    field: K,
    value: TopicAnalysisResult[K],
  ) => void;
  reset: () => void;
}

export function useTopicAnalysis(): UseTopicAnalysisReturn {
  const [analysis, setAnalysis] = useState<TopicAnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const analyze = useCallback(async (title: string) => {
    setIsAnalyzing(true);
    setError(null);
    try {
      const result = await analyzeTopic(title);
      setAnalysis(result);
    } catch {
      setError("Failed to analyze topic. Please try again.");
    } finally {
      setIsAnalyzing(false);
    }
  }, []);

  const regenerateField = useCallback(
    async (title: string, field: string) => {
      if (!analysis) return;
      setIsRegenerating(field);
      try {
        const result = await analyzeTopic(title, field, analysis);
        setAnalysis(result);
      } catch {
        setError(`Failed to regenerate ${field}.`);
      } finally {
        setIsRegenerating(null);
      }
    },
    [analysis],
  );

  const updateField = useCallback(
    <K extends keyof TopicAnalysisResult>(
      field: K,
      value: TopicAnalysisResult[K],
    ) => {
      if (!analysis) return;
      setAnalysis({ ...analysis, [field]: value });
    },
    [analysis],
  );

  const reset = useCallback(() => {
    setAnalysis(null);
    setIsAnalyzing(false);
    setIsRegenerating(null);
    setError(null);
  }, []);

  return {
    analysis,
    isAnalyzing,
    isRegenerating,
    error,
    analyze,
    regenerateField,
    updateField,
    reset,
  };
}
```

- [ ] **Step 2: Create the CreateTopicModal component**

Create `frontend/src/components/topics/create-topic-modal.tsx`:

```tsx
"use client";

import { useState } from "react";
import { RefreshCw, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useTopicAnalysis } from "@/hooks/use-topic-analysis";
import type { ContentTone } from "@/types/api";

const TONE_OPTIONS: { value: ContentTone; label: string }[] = [
  { value: "technical-authoritative", label: "Technical & Authoritative" },
  { value: "conversational", label: "Conversational" },
  { value: "educational", label: "Educational" },
  { value: "analytical", label: "Analytical" },
  { value: "news-reporting", label: "News Reporting" },
];

interface CreateTopicModalProps {
  open: boolean;
  onClose: () => void;
  onCreateOnly: (topicData: CreateTopicData) => void;
  onCreateAndGenerate: (topicData: CreateTopicData) => void;
}

export interface CreateTopicData {
  title: string;
  description: string;
  domain: string;
  keywords: string[];
  target_audience: string;
  content_tone: ContentTone;
  preferred_angle: string;
}

export function CreateTopicModal({
  open,
  onClose,
  onCreateOnly,
  onCreateAndGenerate,
}: CreateTopicModalProps) {
  const [title, setTitle] = useState("");
  const {
    analysis,
    isAnalyzing,
    isRegenerating,
    error,
    analyze,
    regenerateField,
    updateField,
    reset,
  } = useTopicAnalysis();

  if (!open) return null;

  function handleClose() {
    setTitle("");
    reset();
    onClose();
  }

  function buildData(): CreateTopicData {
    return {
      title,
      description: analysis!.description,
      domain: analysis!.domain,
      keywords: analysis!.keywords,
      target_audience: analysis!.target_audience,
      content_tone: analysis!.content_tone as ContentTone,
      preferred_angle: analysis!.preferred_angle,
    };
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleClose}
    >
      <div
        role="dialog"
        className="w-full max-w-lg rounded-lg bg-white p-6 shadow-lg max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-heading text-lg font-semibold text-neutral-900">
          Create Topic
        </h2>

        {/* Title input */}
        <div className="mt-4">
          <label className="text-sm font-medium text-neutral-700">
            Topic Title
          </label>
          <input
            type="text"
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g., Zero Trust Architecture in Cloud-Native Apps"
            className="mt-1 w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <Button
            className="mt-2 bg-primary hover:bg-primary/90"
            size="sm"
            disabled={title.length < 3 || isAnalyzing}
            onClick={() => analyze(title)}
          >
            <Sparkles className="mr-2 h-4 w-4" />
            {isAnalyzing ? "Analyzing..." : "Analyze"}
          </Button>
        </div>

        {/* Loading skeleton */}
        {isAnalyzing && (
          <div className="mt-4 space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-8 rounded-md" />
            ))}
          </div>
        )}

        {/* Error */}
        {error && (
          <p className="mt-3 text-sm text-error">{error}</p>
        )}

        {/* Analysis results */}
        {analysis && !isAnalyzing && (
          <div className="mt-4 space-y-4">
            <FieldWithRegenerate
              label="Description"
              field="description"
              isRegenerating={isRegenerating}
              onRegenerate={() => regenerateField(title, "description")}
            >
              <textarea
                value={analysis.description}
                onChange={(e) => updateField("description", e.target.value)}
                rows={2}
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
              />
            </FieldWithRegenerate>

            <FieldWithRegenerate
              label="Domain"
              field="domain"
              isRegenerating={isRegenerating}
              onRegenerate={() => regenerateField(title, "domain")}
            >
              <input
                type="text"
                value={analysis.domain}
                onChange={(e) => updateField("domain", e.target.value)}
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
              />
            </FieldWithRegenerate>

            <FieldWithRegenerate
              label="Keywords"
              field="keywords"
              isRegenerating={isRegenerating}
              onRegenerate={() => regenerateField(title, "keywords")}
            >
              <input
                type="text"
                value={analysis.keywords.join(", ")}
                onChange={(e) =>
                  updateField(
                    "keywords",
                    e.target.value.split(",").map((k) => k.trim()).filter(Boolean),
                  )
                }
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
                placeholder="comma-separated keywords"
              />
            </FieldWithRegenerate>

            <FieldWithRegenerate
              label="Target Audience"
              field="target_audience"
              isRegenerating={isRegenerating}
              onRegenerate={() => regenerateField(title, "target_audience")}
            >
              <input
                type="text"
                value={analysis.target_audience}
                onChange={(e) => updateField("target_audience", e.target.value)}
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
              />
            </FieldWithRegenerate>

            <FieldWithRegenerate
              label="Content Tone"
              field="content_tone"
              isRegenerating={isRegenerating}
              onRegenerate={() => regenerateField(title, "content_tone")}
            >
              <select
                value={analysis.content_tone}
                onChange={(e) => updateField("content_tone", e.target.value)}
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
              >
                {TONE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </FieldWithRegenerate>

            <FieldWithRegenerate
              label="Preferred Angle"
              field="preferred_angle"
              isRegenerating={isRegenerating}
              onRegenerate={() => regenerateField(title, "preferred_angle")}
            >
              <input
                type="text"
                value={analysis.preferred_angle}
                onChange={(e) => updateField("preferred_angle", e.target.value)}
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
              />
            </FieldWithRegenerate>
          </div>
        )}

        {/* Footer */}
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="ghost" onClick={handleClose}>
            Cancel
          </Button>
          {analysis && (
            <>
              <Button
                variant="outline"
                onClick={() => onCreateOnly(buildData())}
              >
                Create Topic
              </Button>
              <Button
                className="bg-primary hover:bg-primary/90"
                onClick={() => onCreateAndGenerate(buildData())}
              >
                Create & Generate Article
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function FieldWithRegenerate({
  label,
  field,
  isRegenerating,
  onRegenerate,
  children,
}: {
  label: string;
  field: string;
  isRegenerating: string | null;
  onRegenerate: () => void;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-neutral-700">{label}</label>
        <button
          type="button"
          onClick={onRegenerate}
          disabled={isRegenerating === field}
          className="text-neutral-400 hover:text-neutral-600 disabled:animate-spin"
          title={`Regenerate ${label.toLowerCase()}`}
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="mt-1">{children}</div>
    </div>
  );
}
```

- [ ] **Step 3: Wire modal into Topics page**

In `frontend/src/app/(dashboard)/topics/page.tsx`, add the Create Topic button and modal:

Add imports:

```typescript
import { Plus } from "lucide-react";
import { CreateTopicModal, type CreateTopicData } from "@/components/topics/create-topic-modal";
import { createManualTopic, createResearchSession } from "@/lib/api/trends";
```

Add state for the create modal:

```typescript
const [showCreateModal, setShowCreateModal] = useState(false);
```

Add handlers:

```typescript
  async function handleCreateOnly(data: CreateTopicData) {
    setShowCreateModal(false);
    try {
      const result = await createManualTopic({
        title: data.title,
        description: data.description,
        domain: data.domain,
        keywords: data.keywords,
      });
      if (result.is_duplicate) {
        setToast(`Similar topic already exists: "${result.topic.title}"`);
      } else {
        setToast(`Topic "${data.title}" created.`);
      }
    } catch {
      setToast(`Failed to create topic.`);
    }
    setTimeout(() => setToast(null), 5000);
  }

  async function handleCreateAndGenerate(data: CreateTopicData) {
    setShowCreateModal(false);
    try {
      const result = await createManualTopic({
        title: data.title,
        description: data.description,
        domain: data.domain,
        keywords: data.keywords,
      });
      const topicId = result.duplicate_of || result.topic.id;
      await createResearchSession(topicId, {
        target_audience: data.target_audience,
        content_tone: data.content_tone,
        preferred_angle: data.preferred_angle,
      });
      setToast(`Research started for "${data.title}". Check Research page.`);
    } catch {
      setToast(`Failed to create topic and start research.`);
    }
    setTimeout(() => setToast(null), 5000);
  }
```

Add the Create Topic button next to the New Scan button in the Header (around line 111-119):

```tsx
        <Button
          size="sm"
          variant="outline"
          onClick={() => setShowCreateModal(true)}
        >
          <Plus className="mr-2 h-4 w-4" />
          Create Topic
        </Button>
        <Button
          size="sm"
          className="bg-primary hover:bg-primary/90"
          disabled={isScanning || !hasDomain}
          onClick={() => startScan(filters.domain)}
        >
          <Zap className="mr-2 h-4 w-4" />
          New Scan
        </Button>
```

Add the modal before the toast (around line 162):

```tsx
      <CreateTopicModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreateOnly={handleCreateOnly}
        onCreateAndGenerate={handleCreateAndGenerate}
      />
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/use-topic-analysis.ts frontend/src/components/topics/create-topic-modal.tsx frontend/src/app/\(dashboard\)/topics/page.tsx
git commit -m "feat: add Create Topic modal with LLM-powered auto-fill"
```

---

### Task 8: Frontend — Extend Generate Article Modal with Per-Article Params

**Files:**
- Modify: `frontend/src/components/topics/generate-article-modal.tsx`
- Modify: `frontend/src/app/(dashboard)/topics/page.tsx:84-103`

- [ ] **Step 1: Update GenerateArticleModal component**

Replace `frontend/src/components/topics/generate-article-modal.tsx` with extended version:

```tsx
"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TrendBadge } from "@/components/common/trend-badge";
import { DomainBadge } from "@/components/common/domain-badge";
import type { RankedTopic } from "@/types/api";
import type { ContentTone, ArticleParams } from "@/types/api";

const TONE_OPTIONS: { value: ContentTone; label: string }[] = [
  { value: "technical-authoritative", label: "Technical & Authoritative" },
  { value: "conversational", label: "Conversational" },
  { value: "educational", label: "Educational" },
  { value: "analytical", label: "Analytical" },
  { value: "news-reporting", label: "News Reporting" },
];

interface GenerateArticleModalProps {
  topic: RankedTopic | null;
  onClose: () => void;
  onConfirm: (topic: RankedTopic, articleParams?: ArticleParams) => void;
}

export function GenerateArticleModal({
  topic,
  onClose,
  onConfirm,
}: GenerateArticleModalProps) {
  const [expanded, setExpanded] = useState(false);
  const [audience, setAudience] = useState("");
  const [tone, setTone] = useState<ContentTone>("technical-authoritative");
  const [angle, setAngle] = useState("");

  if (!topic) return null;

  function handleConfirm() {
    const params: ArticleParams | undefined = expanded
      ? {
          target_audience: audience || undefined,
          content_tone: tone,
          preferred_angle: angle || undefined,
        }
      : undefined;
    onConfirm(topic!, params);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        role="dialog"
        className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-heading text-lg font-semibold text-neutral-900">
          Generate Article
        </h2>
        <div className="mt-4 space-y-3">
          <div className="flex items-center gap-2">
            <TrendBadge variant={topic.trend_status} />
            <DomainBadge domain={topic.domain} />
          </div>
          <h3 className="font-heading text-base font-medium text-neutral-900">
            {topic.title}
          </h3>
          <p className="text-sm text-neutral-500">{topic.description}</p>
          <p className="text-sm text-neutral-500">
            Score:{" "}
            <span className="font-semibold text-neutral-900">
              {topic.composite_score}
            </span>
          </p>
        </div>

        {/* Customize Article section */}
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="mt-4 flex w-full items-center justify-between rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-600 hover:bg-neutral-50"
        >
          <span>Customize Article</span>
          {expanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </button>

        {expanded && (
          <div className="mt-3 space-y-3 rounded-md border border-neutral-100 p-3">
            <div>
              <label className="text-xs font-medium text-neutral-500">
                Target Audience
              </label>
              <input
                type="text"
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                placeholder="e.g., Security engineers and CTOs"
                className="mt-1 w-full rounded-md border border-neutral-200 px-3 py-1.5 text-sm focus:border-primary focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-neutral-500">
                Content Tone
              </label>
              <select
                value={tone}
                onChange={(e) => setTone(e.target.value as ContentTone)}
                className="mt-1 w-full rounded-md border border-neutral-200 px-3 py-1.5 text-sm focus:border-primary focus:outline-none"
              >
                {TONE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-neutral-500">
                Preferred Angle
              </label>
              <input
                type="text"
                value={angle}
                onChange={(e) => setAngle(e.target.value)}
                placeholder="e.g., Practical implementation guide"
                className="mt-1 w-full rounded-md border border-neutral-200 px-3 py-1.5 text-sm focus:border-primary focus:outline-none"
              />
            </div>
          </div>
        )}

        <p className="mt-4 text-sm text-neutral-500">
          This will start the content generation pipeline. Estimated time: 2-5
          minutes.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleConfirm}>Generate</Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Update handleConfirm in Topics page**

In `frontend/src/app/(dashboard)/topics/page.tsx`, update `handleConfirm` to pass article params:

```typescript
  async function handleConfirm(topic?: RankedTopic, articleParams?: ArticleParams) {
    const t = topic || modalTopic;
    closeModal();
    if (!t) return;
    if (!t.id) {
      setToast(`Cannot start research — topic has no ID. Try scanning again.`);
      setTimeout(() => setToast(null), 5000);
      return;
    }
    setToast(`Starting research for "${t.title}"...`);
    try {
      await createResearchSession(t.id, articleParams);
      setToast(
        `Research started for "${t.title}". Check Research page for progress.`,
      );
    } catch {
      setToast(`Failed to start research for "${t.title}".`);
    }
    setTimeout(() => setToast(null), 5000);
  }
```

Add the `ArticleParams` import at the top:

```typescript
import type { ArticleParams } from "@/types/api";
```

- [ ] **Step 3: Run frontend tests**

Run: `cd frontend && npx vitest run`
Expected: All tests pass (update any broken tests due to changed modal props)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/topics/generate-article-modal.tsx frontend/src/app/\(dashboard\)/topics/page.tsx
git commit -m "feat: extend Generate Article modal with per-article customization"
```

---

### Task 9: Frontend Tests

**Files:**
- Create: `frontend/src/components/topics/__tests__/create-topic-modal.test.tsx`
- Modify: existing generate-article-modal tests (if any)

- [ ] **Step 1: Write tests for CreateTopicModal**

Create `frontend/src/components/topics/__tests__/create-topic-modal.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CreateTopicModal } from "../create-topic-modal";

// Mock the API
vi.mock("@/lib/api/trends", () => ({
  analyzeTopic: vi.fn(),
}));

import { analyzeTopic } from "@/lib/api/trends";
const mockAnalyze = vi.mocked(analyzeTopic);

describe("CreateTopicModal", () => {
  const defaultProps = {
    open: true,
    onClose: vi.fn(),
    onCreateOnly: vi.fn(),
    onCreateAndGenerate: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when closed", () => {
    const { container } = render(
      <CreateTopicModal {...defaultProps} open={false} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders title input and analyze button", () => {
    render(<CreateTopicModal {...defaultProps} />);
    expect(screen.getByPlaceholderText(/zero trust/i)).toBeInTheDocument();
    expect(screen.getByText("Analyze")).toBeInTheDocument();
  });

  it("disables analyze button when title is too short", () => {
    render(<CreateTopicModal {...defaultProps} />);
    const btn = screen.getByText("Analyze");
    expect(btn).toBeDisabled();
  });

  it("enables analyze button when title has 3+ characters", () => {
    render(<CreateTopicModal {...defaultProps} />);
    const input = screen.getByPlaceholderText(/zero trust/i);
    fireEvent.change(input, { target: { value: "Zero Trust" } });
    expect(screen.getByText("Analyze")).not.toBeDisabled();
  });

  it("shows analysis results after successful analyze", async () => {
    mockAnalyze.mockResolvedValue({
      description: "An exploration of zero trust",
      domain: "cybersecurity",
      keywords: ["zero trust", "cloud"],
      target_audience: "Security engineers",
      content_tone: "technical-authoritative",
      preferred_angle: "Implementation guide",
    });

    render(<CreateTopicModal {...defaultProps} />);
    const input = screen.getByPlaceholderText(/zero trust/i);
    fireEvent.change(input, { target: { value: "Zero Trust Architecture" } });
    fireEvent.click(screen.getByText("Analyze"));

    await waitFor(() => {
      expect(screen.getByText("Create Topic")).toBeInTheDocument();
      expect(screen.getByText("Create & Generate Article")).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run frontend tests**

Run: `cd frontend && npx vitest run`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/topics/__tests__/create-topic-modal.test.tsx
git commit -m "test: add tests for CreateTopicModal component"
```

---

### Task 10: Backend Test Fixes and Integration Test

**Files:**
- Create: `tests/unit/test_topic_analysis_endpoint.py`
- Modify: any existing tests broken by schema changes

- [ ] **Step 1: Write endpoint-level test**

Create `tests/unit/test_topic_analysis_endpoint.py`:

```python
"""Tests for the topic analysis and manual creation endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_analyze_topic_endpoint():
    """POST /topics/analyze returns analysis result."""
    from src.api.schemas.topic_analysis import TopicAnalysisResult

    mock_result = TopicAnalysisResult(
        description="desc",
        domain="cybersecurity",
        keywords=["zero trust"],
        target_audience="Engineers",
        content_tone="technical-authoritative",
        preferred_angle="Guide",
    )

    with patch("src.api.routers.topics.TopicAnalyzer") as MockAnalyzer:
        instance = AsyncMock()
        instance.analyze.return_value = mock_result
        MockAnalyzer.return_value = instance

        from src.api.routers.topics import analyze_topic
        from src.api.schemas.topic_analysis import AnalyzeTopicRequest

        mock_request = MagicMock()
        mock_request.app.state.drafting_llm = MagicMock()
        mock_request.app.state.domain_config_repo = None

        body = AnalyzeTopicRequest(title="Zero Trust Architecture")
        result = await analyze_topic(
            request=mock_request,
            body=body,
            user=MagicMock(),
        )
        assert result.domain == "cybersecurity"
        assert result.target_audience == "Engineers"
```

- [ ] **Step 2: Run all backend tests**

Run: `uv run pytest tests/unit/ -q`
Expected: All tests pass — no regressions from schema changes

- [ ] **Step 3: Run linting**

Run: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`
Expected: No lint errors. If there are, fix with `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/`

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_topic_analysis_endpoint.py
git commit -m "test: add endpoint tests for topic analysis and fix regressions"
```

---

### Task 11: Update Documentation and Progress Tracking

**Files:**
- Modify: `project-management/PROGRESS.md`
- Modify: `project-management/BACKLOG.md`

- [ ] **Step 1: Update PROGRESS.md**

Add a new section for the custom topic entry feature under a new "Feature Enhancements" section:

```markdown
## Feature Enhancements

| Ticket | Title | Status | Branch | Plan | Spec |
| ------ | ----- | ------ | ------ | ---- | ---- |
| CUSTOM-001 | Custom Topic Entry with Auto-Fill | In Progress | `feature/custom-topic-entry` | [plan](../docs/superpowers/plans/2026-03-30-custom-topic-entry.md) | [spec](../docs/superpowers/specs/2026-03-30-custom-topic-entry-design.md) |
```

- [ ] **Step 2: Update BACKLOG.md**

Add the custom topic entry as a new item in the backlog with its acceptance criteria.

- [ ] **Step 3: Commit**

```bash
git add project-management/PROGRESS.md project-management/BACKLOG.md
git commit -m "docs: track custom topic entry feature in progress and backlog"
```
