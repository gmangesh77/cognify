"""AUTHOR-009 — sentence-level segments between original and humanized text.

`segment_sentences` tokenises both texts into sentence / whitespace /
newline tokens and aligns them with `difflib`. Every character of both
inputs lands in exactly one segment, so the client (or `resolve_segments`)
can rebuild the markdown from per-segment accept/reject decisions without
a second API call. Newlines are their own tokens, so headings, code
fences, list items and `data-spec-id` markers never merge into a prose
sentence and — being unchanged by the humanizer — always come back as
`equal` segments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

from src.services.content.word_diff import WordDiffOp, diff_words

SegmentKind = Literal["equal", "change"]

# A sentence runs up to terminal punctuation followed by whitespace / end
# of line; whitespace runs and newlines are separate tokens so joins are
# lossless.
_SENTENCE_TOKEN_RE = re.compile(r"\n+|[ \t]+|[^\n]+?(?:[.!?](?=[ \t\n]|$)|(?=\n)|$)")


@dataclass(frozen=True)
class Segment:
    id: str
    kind: SegmentKind
    before: str
    after: str
    ops: list[WordDiffOp]

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "before": self.before,
            "after": self.after,
            "ops": [op.to_dict() for op in self.ops],
        }


def tokenize_sentences(text: str) -> list[str]:
    """Split into sentence / whitespace / newline tokens; ``"".join`` round-trips."""
    return [t for t in _SENTENCE_TOKEN_RE.findall(text) if t]


def segment_sentences(before: str, after: str) -> list[Segment]:
    """Align sentences of `before` and `after` into ordered, gap-free segments."""
    a, b = tokenize_sentences(before), tokenize_sentences(after)
    matcher = SequenceMatcher(a=a, b=b, autojunk=False)
    segments: list[Segment] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old, new = "".join(a[i1:i2]), "".join(b[j1:j2])
        kind: SegmentKind = "equal" if tag == "equal" else "change"
        ops = [] if kind == "equal" else diff_words(old, new)
        segments.append(Segment(f"s{len(segments)}", kind, old, new, ops))
    return segments


def resolve_segments(segments: list[Segment], rejected: set[str]) -> str:
    """Rebuild text: rejected change segments keep `before`, everything else `after`."""
    return "".join(
        s.before if (s.kind == "change" and s.id in rejected) else s.after
        for s in segments
    )


__all__ = [
    "Segment",
    "SegmentKind",
    "resolve_segments",
    "segment_sentences",
    "tokenize_sentences",
]
