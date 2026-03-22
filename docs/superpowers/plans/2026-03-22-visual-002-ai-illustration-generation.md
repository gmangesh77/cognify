# VISUAL-002: AI Illustration Generation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate one hero image per article using OpenAI DALL-E 3 behind a provider-agnostic ImageGenerator protocol, following the VISUAL-001 chart generation pattern.

**Architecture:** LLM generates a DALL-E prompt from article title/summary/domain. OpenAI API produces the image. Pipeline node saves to local filesystem and returns an `ImageAsset`. Best-effort: failures skip illustration, pipeline continues.

**Tech Stack:** Python 3.12, OpenAI API (DALL-E 3), Pydantic, LangGraph, pytest

**Spec:** [`docs/superpowers/specs/2026-03-22-visual-002-ai-illustration-generation-design.md`](../specs/2026-03-22-visual-002-ai-illustration-generation-design.md)

**Worktree:** `D:/Workbench/github/cognify-visual-002` (branch: `feature/VISUAL-002-ai-illustration-generation`)

**Baseline:** 794 backend tests passing (1 pre-existing pytrends error), 236 frontend tests passing.

---

## Task 1: Add OpenAI dependency and settings

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/config/settings.py:91-92`

- [ ] **Step 1: Add openai dependency**

In `pyproject.toml`, add `"openai>=1.30.0"` to the `dependencies` list.

- [ ] **Step 2: Add settings**

In `src/config/settings.py`, after the `chart_output_dir` line (line 92), add:

```python
    # AI illustration generation (OpenAI DALL-E)
    openai_api_key: str = ""
    illustration_output_dir: str = "generated_assets/illustrations"
    dalle_model: str = "dall-e-3"
    illustration_timeout: float = 30.0
```

- [ ] **Step 3: Install and verify**

Run: `cd D:/Workbench/github/cognify-visual-002 && uv sync --dev`
Verify: `cd D:/Workbench/github/cognify-visual-002 && uv run python -c "import openai; print(openai.__version__)"`

- [ ] **Step 4: Add mypy override if needed**

Run: `cd D:/Workbench/github/cognify-visual-002 && uv run mypy src/config/settings.py --strict`
If `openai` module has missing stubs, add to `pyproject.toml`:
```toml
[[tool.mypy.overrides]]
module = "openai.*"
ignore_missing_imports = true
```

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-visual-002
git add pyproject.toml uv.lock src/config/settings.py
git commit -m "chore: add openai dependency and illustration settings"
```

---

## Task 2: ImageGenerator protocol and OpenAI implementation

**Files:**
- Create: `src/agents/content/illustration_generator.py`
- Test: `tests/unit/agents/content/test_illustration_generator.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/agents/content/test_illustration_generator.py`:

```python
"""Tests for illustration generation: ImageGenerator protocol and prompt crafting."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.content.illustration_generator import (
    OpenAIDalleGenerator,
    generate_illustration_prompt,
)
from src.models.research import TopicInput


class TestOpenAIDalleGenerator:
    @pytest.mark.asyncio
    async def test_returns_bytes_on_success(self) -> None:
        fake_image = b"fake-png-bytes"
        b64_image = base64.b64encode(fake_image).decode()
        mock_client = AsyncMock()
        mock_client.images.generate.return_value = MagicMock(
            data=[MagicMock(b64_json=b64_image)]
        )
        generator = OpenAIDalleGenerator.__new__(OpenAIDalleGenerator)
        generator._client = mock_client
        generator._model = "dall-e-3"
        result = await generator.generate("a cybersecurity illustration", (1024, 1024))
        assert result == fake_image

    @pytest.mark.asyncio
    async def test_returns_none_on_api_error(self) -> None:
        mock_client = AsyncMock()
        mock_client.images.generate.side_effect = Exception("API rate limit")
        generator = OpenAIDalleGenerator.__new__(OpenAIDalleGenerator)
        generator._client = mock_client
        generator._model = "dall-e-3"
        result = await generator.generate("test prompt", (1024, 1024))
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_response(self) -> None:
        mock_client = AsyncMock()
        mock_client.images.generate.return_value = MagicMock(data=[])
        generator = OpenAIDalleGenerator.__new__(OpenAIDalleGenerator)
        generator._client = mock_client
        generator._model = "dall-e-3"
        result = await generator.generate("test prompt", (1024, 1024))
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-visual-002 && uv run pytest tests/unit/agents/content/test_illustration_generator.py::TestOpenAIDalleGenerator -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement ImageGenerator protocol and OpenAIDalleGenerator**

Create `src/agents/content/illustration_generator.py`:

```python
"""AI illustration generation for article hero images.

Defines ImageGenerator protocol and OpenAI DALL-E implementation.
Best-effort: failures are logged and skipped, never crash the pipeline.
"""

from __future__ import annotations

import base64
from typing import Protocol

import structlog
from openai import AsyncOpenAI

logger = structlog.get_logger()


class ImageGenerator(Protocol):
    """Provider-agnostic image generation protocol."""

    async def generate(
        self, prompt: str, size: tuple[int, int]
    ) -> bytes | None: ...


class OpenAIDalleGenerator:
    """OpenAI DALL-E 3 image generator."""

    def __init__(self, api_key: str, model: str = "dall-e-3", timeout: float = 30.0) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self._model = model

    async def generate(
        self, prompt: str, size: tuple[int, int]
    ) -> bytes | None:
        """Generate an image. Returns bytes on success, None on failure."""
        size_str = f"{size[0]}x{size[1]}"
        try:
            response = await self._client.images.generate(
                model=self._model,
                prompt=prompt,
                size=size_str,
                response_format="b64_json",
                n=1,
            )
            if not response.data:
                logger.warning("dalle_empty_response")
                return None
            b64_data = response.data[0].b64_json
            if not b64_data:
                logger.warning("dalle_no_b64_data")
                return None
            return base64.b64decode(b64_data)
        except Exception as exc:
            logger.warning("dalle_generation_failed", error=str(exc))
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Workbench/github/cognify-visual-002 && uv run pytest tests/unit/agents/content/test_illustration_generator.py::TestOpenAIDalleGenerator -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-visual-002
git add src/agents/content/illustration_generator.py tests/unit/agents/content/test_illustration_generator.py
git commit -m "feat(visual): add ImageGenerator protocol and OpenAI DALL-E implementation"
```

---

## Task 3: Prompt generation function

**Files:**
- Modify: `src/agents/content/illustration_generator.py`
- Test: `tests/unit/agents/content/test_illustration_generator.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/agents/content/test_illustration_generator.py`:

```python
from uuid import uuid4


class TestGenerateIllustrationPrompt:
    @pytest.mark.asyncio
    async def test_returns_prompt_string(self) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content="A futuristic digital shield protecting a network of connected devices"
        )
        topic = TopicInput(
            id=uuid4(), title="AI Security Trends", description="Emerging threats", domain="cybersecurity"
        )
        result = await generate_illustration_prompt(topic, "Summary of AI security trends in 2026", llm)
        assert result is not None
        assert len(result) > 10

    @pytest.mark.asyncio
    async def test_returns_none_on_llm_failure(self) -> None:
        llm = AsyncMock()
        llm.ainvoke.side_effect = Exception("LLM unavailable")
        topic = TopicInput(
            id=uuid4(), title="Test", description="Desc", domain="tech"
        )
        result = await generate_illustration_prompt(topic, "Summary", llm)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_response(self) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="")
        topic = TopicInput(
            id=uuid4(), title="Test", description="Desc", domain="tech"
        )
        result = await generate_illustration_prompt(topic, "", llm)
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-visual-002 && uv run pytest tests/unit/agents/content/test_illustration_generator.py::TestGenerateIllustrationPrompt -v`
Expected: FAIL — function not defined.

- [ ] **Step 3: Implement generate_illustration_prompt**

Add to `src/agents/content/illustration_generator.py`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from src.models.research import TopicInput

_PROMPT_TEMPLATE = (
    "You are an expert art director. Write a detailed image generation prompt "
    "for a professional article hero image.\n\n"
    "Article title: {title}\n"
    "Domain: {domain}\n"
    "Summary: {summary}\n\n"
    "Requirements:\n"
    "- Professional, editorial-style illustration\n"
    "- NO text, words, or letters in the image\n"
    "- NO photorealistic human faces\n"
    "- Clean composition, modern aesthetic\n"
    "- Relevant to the article's domain and topic\n"
    "- Suitable as an article header/cover image\n\n"
    "Write ONLY the image prompt (100-200 words). No explanation."
)


async def generate_illustration_prompt(
    topic: "TopicInput",
    summary: str,
    llm: "BaseChatModel",
) -> str | None:
    """Generate a DALL-E prompt from article metadata. Returns None on failure."""
    prompt = _PROMPT_TEMPLATE.format(
        title=topic.title,
        domain=topic.domain,
        summary=summary or topic.description,
    )
    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip() if hasattr(response, "content") else ""
        if not content:
            logger.warning("illustration_prompt_empty")
            return None
        return content
    except Exception as exc:
        logger.warning("illustration_prompt_failed", error=str(exc))
        return None
```

- [ ] **Step 4: Run tests**

Run: `cd D:/Workbench/github/cognify-visual-002 && uv run pytest tests/unit/agents/content/test_illustration_generator.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-visual-002
git add src/agents/content/illustration_generator.py tests/unit/agents/content/test_illustration_generator.py
git commit -m "feat(visual): add LLM-powered illustration prompt generation"
```

---

## Task 4: Illustration pipeline node

**Files:**
- Modify: `src/agents/content/nodes.py`
- Create: `tests/unit/agents/content/test_illustration_node.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/agents/content/test_illustration_node.py`:

```python
"""Tests for illustration generation pipeline node."""

import base64
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.agents.content.nodes import make_illustration_node
from src.models.content import ImageAsset
from src.models.content_pipeline import SEOResult
from src.models.research import TopicInput


def _make_mock_generator(image_bytes: bytes | None = b"fake-png") -> AsyncMock:
    gen = AsyncMock()
    gen.generate.return_value = image_bytes
    return gen


def _make_state(
    topic_title: str = "AI Security",
    summary: str = "Summary of trends",
    existing_visuals: list | None = None,
) -> dict:
    return {
        "topic": TopicInput(
            id=uuid4(), title=topic_title, description="Desc", domain="cybersecurity"
        ),
        "session_id": uuid4(),
        "seo_result": SEOResult(
            summary=summary,
            key_claims=["claim"],
            meta_title="Meta",
            meta_description="Desc",
            primary_keyword="security",
        ),
        "visuals": existing_visuals or [],
    }


class TestIllustrationNode:
    @pytest.mark.asyncio
    async def test_produces_hero_image(self, tmp_path) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="A glowing digital shield")
        gen = _make_mock_generator()
        node = make_illustration_node(llm, gen, str(tmp_path))
        state = _make_state()
        result = await node(state)
        assert len(result["visuals"]) == 1
        asset = result["visuals"][0]
        assert isinstance(asset, ImageAsset)
        assert asset.metadata["type"] == "hero"
        assert asset.metadata["generator"] == "dall-e-3"

    @pytest.mark.asyncio
    async def test_preserves_existing_chart_visuals(self, tmp_path) -> None:
        existing = ImageAsset(url="/charts/foo.png", caption="Chart")
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="A prompt")
        gen = _make_mock_generator()
        node = make_illustration_node(llm, gen, str(tmp_path))
        state = _make_state(existing_visuals=[existing])
        result = await node(state)
        assert len(result["visuals"]) == 2
        assert result["visuals"][0] == existing
        assert result["visuals"][1].metadata["type"] == "hero"

    @pytest.mark.asyncio
    async def test_returns_existing_visuals_on_prompt_failure(self, tmp_path) -> None:
        existing = ImageAsset(url="/charts/foo.png", caption="Chart")
        llm = AsyncMock()
        llm.ainvoke.side_effect = Exception("LLM down")
        gen = _make_mock_generator()
        node = make_illustration_node(llm, gen, str(tmp_path))
        state = _make_state(existing_visuals=[existing])
        result = await node(state)
        assert result["visuals"] == [existing]

    @pytest.mark.asyncio
    async def test_returns_existing_visuals_on_generator_failure(self, tmp_path) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="A prompt")
        gen = _make_mock_generator(image_bytes=None)
        node = make_illustration_node(llm, gen, str(tmp_path))
        state = _make_state()
        result = await node(state)
        assert result["visuals"] == []

    @pytest.mark.asyncio
    async def test_falls_back_to_topic_description_when_no_seo(self, tmp_path) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="A prompt")
        gen = _make_mock_generator()
        node = make_illustration_node(llm, gen, str(tmp_path))
        state = {
            "topic": TopicInput(
                id=uuid4(), title="Test", description="Topic description", domain="tech"
            ),
            "session_id": uuid4(),
        }
        result = await node(state)
        assert len(result["visuals"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-visual-002 && uv run pytest tests/unit/agents/content/test_illustration_node.py -v`
Expected: FAIL — `make_illustration_node` not defined.

- [ ] **Step 3: Implement make_illustration_node**

In `src/agents/content/nodes.py`, add import at the top:

```python
from src.agents.content.illustration_generator import (
    ImageGenerator,
    generate_illustration_prompt,
)
```

Add the factory function after `make_chart_node`:

```python
def make_illustration_node(
    llm: BaseChatModel,
    generator: "ImageGenerator",
    output_dir: str,
) -> Any:  # noqa: ANN401
    """Factory for the AI illustration generation node."""

    async def illustration_node(state: ContentState) -> dict[str, object]:
        existing = list(state.get("visuals", []))
        topic = _coerce_topic(state)
        seo = state.get("seo_result")
        summary = seo.summary if seo and hasattr(seo, "summary") else ""
        session_id: UUID = state["session_id"]

        prompt = await generate_illustration_prompt(topic, summary, llm)
        if not prompt:
            return {"visuals": existing}

        try:
            image_bytes = await generator.generate(prompt, (1024, 1024))
        except Exception as exc:
            logger.warning("illustration_generator_error", error=str(exc))
            return {"visuals": existing}

        if not image_bytes:
            return {"visuals": existing}

        path = await asyncio.to_thread(
            _save_illustration, image_bytes, output_dir, session_id
        )
        asset = ImageAsset(
            url=str(path),
            caption=topic.title,
            alt_text=prompt[:200],
            metadata={"generator": "dall-e-3", "type": "hero"},
        )
        logger.info("illustration_generation_complete", path=str(path))
        return {"visuals": existing + [asset]}

    return illustration_node


def _save_illustration(
    image_bytes: bytes, output_dir: str, session_id: UUID
) -> Path:
    """Save illustration bytes to disk. Runs in thread."""
    from pathlib import Path

    out_path = Path(output_dir) / str(session_id)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / "hero.png"
    file_path.write_bytes(image_bytes)
    return file_path
```

Add `Path` import at top of file if not present. Also add `ImageGenerator` to the TYPE_CHECKING block if needed.

- [ ] **Step 4: Run tests**

Run: `cd D:/Workbench/github/cognify-visual-002 && uv run pytest tests/unit/agents/content/test_illustration_node.py -v`
Expected: All PASS.

- [ ] **Step 5: Run all content tests to verify no regressions**

Run: `cd D:/Workbench/github/cognify-visual-002 && uv run pytest tests/unit/agents/content/ -v --tb=short`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
cd D:/Workbench/github/cognify-visual-002
git add src/agents/content/nodes.py tests/unit/agents/content/test_illustration_node.py
git commit -m "feat(visual): add illustration pipeline node with visual accumulation"
```

---

## Task 5: Wire illustration node into content pipeline

**Files:**
- Modify: `src/agents/content/pipeline.py:58-98`

- [ ] **Step 1: Write the failing test**

Add to an existing pipeline test file or create inline test:

Run: `cd D:/Workbench/github/cognify-visual-002 && uv run pytest tests/unit/agents/content/ -k "pipeline" -v --tb=short`
to identify existing pipeline tests. Then verify that a test for the new node wiring can be added.

- [ ] **Step 2: Wire the illustration node in `build_content_graph`**

In `src/agents/content/pipeline.py`:

Add imports:
```python
from src.agents.content.illustration_generator import OpenAIDalleGenerator
from src.agents.content.nodes import make_illustration_node
```

(Note: `make_illustration_node` import is already covered if you add it to the existing `from src.agents.content.nodes import ...` block.)

In `build_content_graph()`, after the chart node setup (line 79), add:

```python
    # Illustration node — only if OpenAI key is configured
    _settings = settings or Settings()
    if _settings.openai_api_key:
        generator = OpenAIDalleGenerator(
            api_key=_settings.openai_api_key,
            model=_settings.dalle_model,
            timeout=_settings.illustration_timeout,
        )
        illust_dir = _settings.illustration_output_dir
        graph.add_node(
            "generate_illustrations",
            make_illustration_node(llm, generator, illust_dir),
        )
        graph.add_edge("generate_charts", "generate_illustrations")
        graph.add_edge("generate_illustrations", END)
    else:
        graph.add_edge("generate_charts", END)
```

Remove the existing `graph.add_edge("generate_charts", END)` line (line 96) — it's replaced by the conditional above.

- [ ] **Step 3: Run all content tests**

Run: `cd D:/Workbench/github/cognify-visual-002 && uv run pytest tests/unit/agents/content/ -v --tb=short`
Expected: All PASS. Existing tests run without `openai_api_key` set, so the illustration node is skipped — no regressions.

- [ ] **Step 4: Run full backend test suite**

Run: `cd D:/Workbench/github/cognify-visual-002 && uv run pytest tests/ -q --tb=no`
Expected: 794+ passed, 1 pre-existing error.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-visual-002
git add src/agents/content/pipeline.py
git commit -m "feat(visual): wire illustration node into content pipeline graph"
```

---

## Task 6: Lint, verify, and update PROGRESS.md

- [ ] **Step 1: Run linter**

Run: `cd D:/Workbench/github/cognify-visual-002 && uv tool run ruff check src/`
Fix any issues.

- [ ] **Step 2: Run full backend test suite**

Run: `cd D:/Workbench/github/cognify-visual-002 && uv run pytest tests/ -q --tb=no`
Expected: 794+ passed, 1 pre-existing error.

- [ ] **Step 3: Run frontend tests**

Run: `cd D:/Workbench/github/cognify-visual-002/frontend && npx vitest run`
Expected: 236 passed.

- [ ] **Step 4: Update PROGRESS.md with plan/spec links**

Update VISUAL-002 row in `project-management/PROGRESS.md` with plan and spec links.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-visual-002
git add -A
git commit -m "docs: update PROGRESS.md with VISUAL-002 plan and spec links"
```
