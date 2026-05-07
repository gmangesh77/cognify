"""Markdown helpers for VISUAL-011 section operations.

The active article body lives on `CanonicalArticle.body_markdown`. We
need to address one section by integer index for read / replace cycles
without forking the document model. Sections are delimited by H2
headings (`## …`); content above the first H2 is the implicit
"section 0 prelude" and is preserved verbatim across edits.

These helpers stay lossless: `split_sections(body)` followed by
`replace_section(body, i, body)` returns the original byte-for-byte.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(##\s.+)$", flags=re.MULTILINE)


@dataclass(frozen=True)
class MarkdownSection:
    """One contiguous chunk of markdown bounded by H2 headings."""

    index: int
    heading: str | None
    body: str

    @property
    def text(self) -> str:
        if self.heading is None:
            return self.body
        return f"{self.heading}\n{self.body}" if self.body else self.heading


def split_sections(body_markdown: str) -> list[MarkdownSection]:
    """Split `body_markdown` on H2 headings, preserving leading prelude.

    Section 0 is everything from the start of the document up to (but
    not including) the first H2 heading. Subsequent sections are one H2
    plus its body until the next H2 (or end of document).
    """
    matches = list(_HEADING_RE.finditer(body_markdown))
    if not matches:
        return [MarkdownSection(index=0, heading=None, body=body_markdown)]

    sections: list[MarkdownSection] = []
    prelude = body_markdown[: matches[0].start()]
    sections.append(MarkdownSection(index=0, heading=None, body=prelude))
    for idx, match in enumerate(matches, start=1):
        heading = match.group(1).rstrip("\n")
        body_start = match.end()
        body_end = matches[idx].start() if idx < len(matches) else len(body_markdown)
        body = body_markdown[body_start:body_end]
        body = body.lstrip("\n")
        sections.append(MarkdownSection(index=idx, heading=heading, body=body))
    return sections


def get_section(body_markdown: str, section_index: int) -> MarkdownSection | None:
    sections = split_sections(body_markdown)
    if section_index < 0 or section_index >= len(sections):
        return None
    return sections[section_index]


def replace_section(
    body_markdown: str,
    section_index: int,
    new_section_markdown: str,
) -> str:
    """Return `body_markdown` with section N replaced.

    `new_section_markdown` is treated as the *full* section text — heading
    plus body. The caller is responsible for keeping the H2 heading in
    place when editing scope is "section"; the anchor validator catches
    drops at the API layer.
    """
    sections = split_sections(body_markdown)
    if section_index < 0 or section_index >= len(sections):
        raise IndexError(
            f"section_index {section_index} out of range "
            f"(article has {len(sections)} sections)"
        )
    rebuilt: list[str] = []
    for section in sections:
        if section.index == section_index:
            rebuilt.append(new_section_markdown.rstrip("\n"))
        else:
            rebuilt.append(section.text.rstrip("\n"))
    # Original document either ended with a newline or not — preserve.
    trailing = "\n" if body_markdown.endswith("\n") else ""
    return "\n\n".join(p for p in rebuilt if p) + trailing


__all__ = [
    "MarkdownSection",
    "get_section",
    "replace_section",
    "split_sections",
]
