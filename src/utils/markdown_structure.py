"""Structure-aware markdown parser (CONTENT-007).

Splits a section's markdown into typed blocks so the humanizer (and
any other prose-rewriter) can hand only the prose blocks to the LLM
and restore the rest verbatim. Without this, the LLM tends to garble
bullet structure, table pipes, code fences, and image references.

Ported from ImpactAI's `markdown_structure.py` and tightened: typed
blocks (`MarkdownBlock` discriminated union via `kind`), explicit
inline-marker dataclass with index hints so we don't accidentally
re-bold an unrelated occurrence, and `extract_humanizable_text`
returns `None` for non-prose blocks instead of an empty string.

Block kinds:

- `content`        — paragraph prose
- `bullet_list`    — `-`/`*`/`+` lists
- `numbered_list`  — `1.` / `2.` lists
- `blockquote`     — `>` blocks
- `heading`        — `#`..`######` headings
- `image`          — `![alt](url)` standalone lines
- `code_block`     — fenced ``` code ```
- `hr`             — horizontal rules
- `table`          — pipe tables with the `|---|` separator
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

BlockKind = Literal[
    "content",
    "bullet_list",
    "numbered_list",
    "blockquote",
    "heading",
    "image",
    "code_block",
    "hr",
    "table",
]

InlineFormat = Literal["bold", "italic"]

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_IMG_RE = re.compile(r"^!\[.*\]\(.*\)")
_HR_RE = re.compile(r"^[\s]*([-*_])\s*\1\s*\1[\s\-*_]*$")
_FENCE_RE = re.compile(r"^```")
_BLOCKQUOTE_RE = re.compile(r"^>\s?")
_BULLET_RE = re.compile(r"^(\s*[-*+])\s+(.*)")
_NUMBERED_RE = re.compile(r"^(\s*\d+\.)\s+(.*)")
_TABLE_SEP_RE = re.compile(r"^\|?[\s:-]+(\|[\s:-]+)+\|?\s*$")

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+?)\*(?!\*)")


@dataclass
class InlineMarker:
    """One bold/italic span lifted out of the raw text."""

    text: str
    fmt: InlineFormat


@dataclass
class MarkdownBlock:
    """One contiguous block of markdown classified by `kind`."""

    kind: BlockKind
    raw: str
    lines: list[str]
    # Lists carry their per-item text + bullet/numbering prefix so the
    # humanizer can rewrite items individually.
    texts: list[str] = field(default_factory=list)
    prefixes: list[str] = field(default_factory=list)


def parse_markdown_blocks(text: str) -> list[MarkdownBlock]:
    """Split `text` into typed blocks, preserving order and raw bytes."""
    lines = text.split("\n")
    blocks: list[MarkdownBlock] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        consumed, block = _parse_one_block(lines, i)
        i = consumed
        if block is not None:
            blocks.append(block)
    return blocks


def _parse_one_block(lines: list[str], i: int) -> tuple[int, MarkdownBlock | None]:
    line = lines[i]
    stripped = line.strip()

    if _FENCE_RE.match(stripped):
        return _consume_code_fence(lines, i)
    if _HEADING_RE.match(stripped):
        return i + 1, MarkdownBlock(kind="heading", raw=line, lines=[line])
    if _IMG_RE.match(stripped):
        return i + 1, MarkdownBlock(kind="image", raw=line, lines=[line])
    if _HR_RE.match(stripped):
        return i + 1, MarkdownBlock(kind="hr", raw=line, lines=[line])
    if _BLOCKQUOTE_RE.match(stripped):
        return _consume_blockquote(lines, i)
    if (
        "|" in stripped
        and i + 1 < len(lines)
        and _TABLE_SEP_RE.match(lines[i + 1].strip())
    ):
        return _consume_table(lines, i)
    if _BULLET_RE.match(line):
        return _consume_list(lines, i, _BULLET_RE, "bullet_list")
    if _NUMBERED_RE.match(line):
        return _consume_list(lines, i, _NUMBERED_RE, "numbered_list")
    return _consume_paragraph(lines, i)


def _consume_code_fence(lines: list[str], i: int) -> tuple[int, MarkdownBlock]:
    code_lines = [lines[i]]
    i += 1
    while i < len(lines):
        code_lines.append(lines[i])
        if _FENCE_RE.match(lines[i].strip()) and len(code_lines) > 1:
            i += 1
            break
        i += 1
    return i, MarkdownBlock(
        kind="code_block",
        raw="\n".join(code_lines),
        lines=code_lines,
    )


def _consume_blockquote(lines: list[str], i: int) -> tuple[int, MarkdownBlock]:
    bq_lines: list[str] = []
    while (
        i < len(lines) and lines[i].strip() and _BLOCKQUOTE_RE.match(lines[i].strip())
    ):
        bq_lines.append(lines[i])
        i += 1
    return i, MarkdownBlock(
        kind="blockquote",
        raw="\n".join(bq_lines),
        lines=bq_lines,
    )


def _consume_table(lines: list[str], i: int) -> tuple[int, MarkdownBlock]:
    tbl_lines: list[str] = []
    while i < len(lines) and "|" in lines[i]:
        tbl_lines.append(lines[i])
        i += 1
    return i, MarkdownBlock(
        kind="table",
        raw="\n".join(tbl_lines),
        lines=tbl_lines,
    )


def _consume_list(
    lines: list[str],
    i: int,
    pattern: re.Pattern[str],
    kind: BlockKind,
) -> tuple[int, MarkdownBlock]:
    list_lines: list[str] = []
    list_texts: list[str] = []
    prefixes: list[str] = []
    while i < len(lines):
        m = pattern.match(lines[i])
        if m:
            list_lines.append(lines[i])
            prefixes.append(m.group(1))
            list_texts.append(m.group(2))
            i += 1
            continue
        if lines[i].strip() == "":
            break
        break
    return i, MarkdownBlock(
        kind=kind,
        raw="\n".join(list_lines),
        lines=list_lines,
        texts=list_texts,
        prefixes=prefixes,
    )


def _consume_paragraph(lines: list[str], i: int) -> tuple[int, MarkdownBlock | None]:
    para_lines: list[str] = []
    while i < len(lines):
        ln = lines[i].strip()
        if not ln:
            i += 1
            break
        if (
            _HEADING_RE.match(ln)
            or _IMG_RE.match(ln)
            or _HR_RE.match(ln)
            or _FENCE_RE.match(ln)
        ):
            break
        if _BULLET_RE.match(lines[i]) or _NUMBERED_RE.match(lines[i]):
            break
        if (
            "|" in ln
            and i + 1 < len(lines)
            and _TABLE_SEP_RE.match(lines[i + 1].strip())
        ):
            break
        para_lines.append(lines[i])
        i += 1
    if not para_lines:
        return i, None
    return i, MarkdownBlock(
        kind="content",
        raw="\n".join(para_lines),
        lines=para_lines,
    )


def strip_inline_markdown(text: str) -> tuple[str, list[InlineMarker]]:
    """Lift bold/italic markers out, return cleaned text + the markers."""
    markers: list[InlineMarker] = [
        InlineMarker(text=m.group(1), fmt="bold") for m in _BOLD_RE.finditer(text)
    ]
    markers.extend(
        InlineMarker(text=m.group(1), fmt="italic") for m in _ITALIC_RE.finditer(text)
    )
    cleaned = _BOLD_RE.sub(r"\1", text)
    cleaned = _ITALIC_RE.sub(r"\1", cleaned)
    cleaned = cleaned.replace("*", "")
    return cleaned, markers


def restore_inline_markdown(text: str, markers: list[InlineMarker]) -> str:
    """Re-wrap surviving marker substrings in their original `**`/`*`."""
    bold_markers = sorted(
        (m for m in markers if m.fmt == "bold"),
        key=lambda m: len(m.text),
        reverse=True,
    )
    italic_markers = sorted(
        (m for m in markers if m.fmt == "italic"),
        key=lambda m: len(m.text),
        reverse=True,
    )
    for m in bold_markers:
        if m.text in text:
            text = text.replace(m.text, f"**{m.text}**", 1)
    for m in italic_markers:
        if m.text in text and f"**{m.text}**" not in text:
            text = text.replace(m.text, f"*{m.text}*", 1)
    return text


def extract_humanizable_text(block: MarkdownBlock) -> str | None:
    """Return the prose payload of a block, or None for non-prose kinds."""
    if block.kind == "content":
        text, _ = strip_inline_markdown(block.raw)
        return text
    if block.kind in ("bullet_list", "numbered_list"):
        cleaned: list[str] = []
        for t in block.texts:
            c, _ = strip_inline_markdown(t)
            cleaned.append(c)
        return "\n".join(cleaned)
    if block.kind == "blockquote":
        raw = "\n".join(_BLOCKQUOTE_RE.sub("", ln) for ln in block.lines)
        text, _ = strip_inline_markdown(raw)
        return text
    return None


def replace_humanized_text(
    block: MarkdownBlock,
    new_text: str,
    markers: list[InlineMarker] | None = None,
) -> MarkdownBlock:
    """Build a new block with `new_text` slotted back into the original shape."""
    if markers:
        new_text = restore_inline_markdown(new_text, markers)
    if block.kind == "content":
        return MarkdownBlock(
            kind="content",
            raw=new_text,
            lines=new_text.split("\n"),
        )
    if block.kind in ("bullet_list", "numbered_list"):
        new_items = new_text.split("\n")
        rebuilt: list[str] = []
        for idx, _orig in enumerate(block.lines):
            prefix = (
                block.prefixes[idx]
                if idx < len(block.prefixes)
                else ("-" if block.kind == "bullet_list" else f"{idx + 1}.")
            )
            item_text = (
                new_items[idx]
                if idx < len(new_items)
                else (block.texts[idx] if idx < len(block.texts) else "")
            )
            rebuilt.append(f"{prefix} {item_text}")
        return MarkdownBlock(
            kind=block.kind,
            raw="\n".join(rebuilt),
            lines=rebuilt,
            texts=block.texts,
            prefixes=block.prefixes,
        )
    if block.kind == "blockquote":
        new_lines = new_text.split("\n")
        return MarkdownBlock(
            kind="blockquote",
            raw="\n".join(f"> {ln}" for ln in new_lines),
            lines=[f"> {ln}" for ln in new_lines],
        )
    return block


def reassemble(blocks: list[MarkdownBlock]) -> str:
    """Join blocks back into a single markdown document, blank-line separated."""
    return "\n\n".join(block.raw for block in blocks)


def humanizable_blocks(
    blocks: list[MarkdownBlock],
) -> list[tuple[int, MarkdownBlock]]:
    """Yield (index, block) for blocks the LLM may rewrite."""
    return [
        (i, b) for i, b in enumerate(blocks) if extract_humanizable_text(b) is not None
    ]


__all__ = [
    "BlockKind",
    "InlineFormat",
    "InlineMarker",
    "MarkdownBlock",
    "extract_humanizable_text",
    "humanizable_blocks",
    "parse_markdown_blocks",
    "reassemble",
    "replace_humanized_text",
    "restore_inline_markdown",
    "strip_inline_markdown",
]
