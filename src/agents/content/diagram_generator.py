"""Diagram generation from article section drafts.

LLM proposes Mermaid diagram specs, mmdc CLI renders to PNG.
Best-effort: failures are logged and skipped, never crash the pipeline.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from pydantic import ValidationError

from src.agents.prompts import render_prompt
from src.models.visual import DiagramSpec
from src.utils.llm_json import parse_llm_json

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from src.models.content_pipeline import SectionDraft

logger = structlog.get_logger()

_MMDC_PATH = Path(__file__).parents[3] / "node_modules" / ".bin" / "mmdc"
# Puppeteer launch args for mmdc. Chromium cannot use its setuid sandbox when
# run as a non-root user inside a container, so we pass `--no-sandbox` via this
# config file (see docs/mermaid-cli linux-sandbox-issue). Shipped next to this
# module; absent in environments where mmdc isn't installed (no-op there).
_PUPPETEER_CONFIG = Path(__file__).parent / "puppeteer-config.json"


async def render_mermaid(syntax: str, output_path: Path) -> bool:
    """Render Mermaid syntax to PNG via mmdc CLI. Returns True on success."""
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False) as tmp:
            tmp.write(syntax)
            tmp_path = Path(tmp.name)

        mmdc = str(_MMDC_PATH)
        args = [mmdc, "-i", str(tmp_path), "-o", str(output_path), "-b", "transparent"]
        if _PUPPETEER_CONFIG.exists():
            args += ["-p", str(_PUPPETEER_CONFIG)]
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=15.0)

        tmp_path.unlink(missing_ok=True)

        if process.returncode != 0:
            logger.warning(
                "mermaid_render_failed",
                exit_code=process.returncode,
                stderr=stderr.decode()[:200],
            )
            return False

        logger.info("mermaid_rendered", path=str(output_path))
        return True

    except FileNotFoundError:
        logger.warning("mmdc_not_found", path=str(_MMDC_PATH))
        return False
    except TimeoutError:
        logger.warning("mermaid_render_timeout")
        return False
    except Exception as exc:
        logger.warning("mermaid_render_error", error=str(exc))
        return False


_SPEC_MERMAID_TEMPLATE = (
    "You are a technical diagram expert. The article section below needs a "
    "single Mermaid diagram that visualises this idea:\n"
    '  "{subject}"\n\n'
    "Choose the Mermaid type that best fits (flowchart | sequence | class | "
    "state | er | journey) and write valid, renderable Mermaid code. Use "
    "concise, correctly-spelled node labels drawn from the section so the "
    "diagram is self-explanatory. Do NOT include a title line inside the "
    "diagram (the article shows a caption separately).\n\n"
    "Return ONLY a JSON object with keys:\n"
    '  - "diagram_type": one of the types above\n'
    '  - "mermaid_syntax": valid Mermaid code\n'
    "No prose, no markdown fences.\n\n"
    "## Section: {section_title}\n{section_body}"
)


async def generate_mermaid_for_spec(
    *,
    subject: str,
    section_title: str,
    section_body: str,
    llm: BaseChatModel,
) -> tuple[str, str] | None:
    """Generate one Mermaid diagram for a planned structural spec.

    Returns ``(mermaid_syntax, diagram_type)`` or ``None`` on failure.
    Best-effort — the caller falls back to a diffusion render when this
    returns None.
    """
    prompt = _SPEC_MERMAID_TEMPLATE.format(
        subject=subject,
        section_title=section_title,
        section_body=section_body,
    )
    try:
        response = await llm.ainvoke(prompt)
        raw = parse_llm_json(response.content)
    except (json.JSONDecodeError, AttributeError, TypeError) as exc:
        logger.warning("spec_mermaid_parse_failed", error=str(exc))
        return None
    if not isinstance(raw, dict):
        return None
    syntax = raw.get("mermaid_syntax")
    diagram_type = raw.get("diagram_type") or "flowchart"
    if not isinstance(syntax, str) or not syntax.strip():
        return None
    return syntax.strip(), str(diagram_type)


def _build_prompt(section_drafts: list[SectionDraft]) -> str:
    sections_text = "\n\n".join(
        f"### {d.title}\n{d.body_markdown}" for d in section_drafts
    )
    return render_prompt("content_diagrams.prompt", sections_text=sections_text)


async def propose_diagrams(
    section_drafts: list[SectionDraft],
    llm: BaseChatModel,
) -> list[DiagramSpec]:
    """Ask LLM to propose up to 5 diagram specs from section drafts.

    Returned specs may include an overview diagram with
    ``source_section_index == -1`` which should render above the article body.
    """
    prompt = _build_prompt(section_drafts)
    try:
        response = await llm.ainvoke(prompt)
        raw = parse_llm_json(response.content)
    except (json.JSONDecodeError, AttributeError, TypeError) as exc:
        logger.warning("diagram_proposal_parse_failed", error=str(exc))
        return []

    if not isinstance(raw, list):
        logger.warning("diagram_proposal_not_list", type=type(raw).__name__)
        return []

    specs: list[DiagramSpec] = []
    for item in raw[:5]:
        try:
            spec = DiagramSpec.model_validate(item)
            if spec.source_section_index >= len(section_drafts):
                logger.warning("diagram_spec_section_out_of_range", title=spec.title)
                continue
            specs.append(spec)
        except (ValidationError, TypeError) as exc:
            logger.warning("diagram_spec_invalid", error=str(exc))
    return specs
