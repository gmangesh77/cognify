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

from src.models.visual import DiagramSpec

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from src.models.content_pipeline import SectionDraft

logger = structlog.get_logger()

_MMDC_PATH = Path(__file__).parents[3] / "node_modules" / ".bin" / "mmdc"

_PROMPT_TEMPLATE = (
    "You are a technical diagram expert. "
    "Read the article sections below and propose 0-2 diagrams.\n\n"
    "Supported types: flowchart, sequence.\n\n"
    "For each diagram, provide:\n"
    '- diagram_type: "flowchart" or "sequence"\n'
    "- title: diagram title (max 120 chars)\n"
    "- mermaid_syntax: valid Mermaid diagram code\n"
    "- caption: one-sentence description for the article\n"
    "- source_section_index: which section (0-indexed) the diagram illustrates\n\n"
    "Only propose diagrams where a process flow or interaction sequence "
    "is described in the text. Return an empty array [] if nothing is diagrammable.\n\n"
    "Return ONLY a JSON array. No explanation.\n\n"
    "## Article Sections\n{sections_text}"
)


async def render_mermaid(syntax: str, output_path: Path) -> bool:
    """Render Mermaid syntax to PNG via mmdc CLI. Returns True on success."""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mmd", delete=False
        ) as tmp:
            tmp.write(syntax)
            tmp_path = Path(tmp.name)

        mmdc = str(_MMDC_PATH)
        process = await asyncio.create_subprocess_exec(
            mmdc,
            "-i", str(tmp_path),
            "-o", str(output_path),
            "-b", "transparent",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(), timeout=15.0
        )

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


async def propose_diagrams(
    section_drafts: list[SectionDraft],
    llm: BaseChatModel,
) -> list[DiagramSpec]:
    """Ask LLM to propose 0-2 diagram specs from section drafts."""
    sections_text = "\n\n".join(
        f"### {d.title}\n{d.body_markdown}" for d in section_drafts
    )
    prompt = _PROMPT_TEMPLATE.format(sections_text=sections_text)
    try:
        response = await llm.ainvoke(prompt)
        raw = json.loads(response.content)
    except (json.JSONDecodeError, AttributeError, TypeError) as exc:
        logger.warning("diagram_proposal_parse_failed", error=str(exc))
        return []

    if not isinstance(raw, list):
        logger.warning("diagram_proposal_not_list", type=type(raw).__name__)
        return []

    specs: list[DiagramSpec] = []
    for item in raw[:2]:
        try:
            spec = DiagramSpec.model_validate(item)
            if spec.source_section_index >= len(section_drafts):
                logger.warning(
                    "diagram_spec_section_out_of_range", title=spec.title
                )
                continue
            specs.append(spec)
        except (ValidationError, TypeError) as exc:
            logger.warning("diagram_spec_invalid", error=str(exc))
    return specs
