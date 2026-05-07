"""Word-level diff helper used by VISUAL-011 prose editing.

Single source of truth for diff visualisation across image refine, HTML
refine, and prose rewrite (per plan §17.2). The renderer in the frontend
consumes the same `WordDiffOp` shape so we never need a second tokenizer.

Implementation is intentionally tiny — `difflib.SequenceMatcher` over a
whitespace-and-punctuation-aware tokeniser. We do not pull in a third
party diff lib; the slop-pattern scorer already proved this stdlib path
is sufficient for editorial diffs.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from typing import Literal

WordDiffKind = Literal["equal", "insert", "delete", "replace"]

_TOKEN_RE = re.compile(r"\s+|[^\w\s]+|\w+", flags=re.UNICODE)


@dataclass(frozen=True)
class WordDiffOp:
    """One contiguous diff operation between two pieces of prose."""

    kind: WordDiffKind
    before: str
    after: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def tokenize(text: str) -> list[str]:
    """Split prose into word + whitespace + punctuation tokens.

    Keeping whitespace as its own token lets us reconstruct the original
    string from the token stream, so the rendered diff doesn't drop
    spacing the editor cares about.
    """
    return _TOKEN_RE.findall(text)


def diff_words(before: str, after: str) -> list[WordDiffOp]:
    """Return a sequence of word-level diff operations.

    Adjacent operations of the same `kind` are coalesced so the renderer
    doesn't have to do that itself.
    """
    before_tokens = tokenize(before)
    after_tokens = tokenize(after)
    matcher = SequenceMatcher(a=before_tokens, b=after_tokens, autojunk=False)
    ops: list[WordDiffOp] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        before_chunk = "".join(before_tokens[i1:i2])
        after_chunk = "".join(after_tokens[j1:j2])
        if tag == "equal":
            ops.append(WordDiffOp("equal", before_chunk, before_chunk))
        elif tag == "insert":
            ops.append(WordDiffOp("insert", "", after_chunk))
        elif tag == "delete":
            ops.append(WordDiffOp("delete", before_chunk, ""))
        elif tag == "replace":
            ops.append(WordDiffOp("replace", before_chunk, after_chunk))
    return _coalesce(ops)


def _coalesce(ops: list[WordDiffOp]) -> list[WordDiffOp]:
    """Merge runs of same-kind ops to reduce frontend render cost."""
    if not ops:
        return ops
    merged: list[WordDiffOp] = [ops[0]]
    for op in ops[1:]:
        last = merged[-1]
        if op.kind == last.kind:
            merged[-1] = WordDiffOp(
                kind=last.kind,
                before=last.before + op.before,
                after=last.after + op.after,
            )
        else:
            merged.append(op)
    return merged


__all__ = ["WordDiffKind", "WordDiffOp", "diff_words", "tokenize"]
