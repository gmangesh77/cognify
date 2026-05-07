"""Tests for the word-level diff helper used by VISUAL-011."""

from __future__ import annotations

from src.services.content.word_diff import diff_words, tokenize


class TestTokenize:
    def test_tokenize_preserves_whitespace(self) -> None:
        tokens = tokenize("a b  c")
        assert "".join(tokens) == "a b  c"

    def test_tokenize_splits_punctuation(self) -> None:
        tokens = tokenize("hello, world!")
        assert "hello" in tokens
        assert "," in tokens
        assert "world" in tokens
        assert "!" in tokens


class TestDiffWords:
    def test_diff_identical_returns_single_equal(self) -> None:
        ops = diff_words("the quick fox", "the quick fox")
        assert len(ops) == 1
        assert ops[0].kind == "equal"
        assert ops[0].before == "the quick fox"
        assert ops[0].after == "the quick fox"

    def test_diff_pure_insert_emits_insert_op(self) -> None:
        ops = diff_words("the quick fox", "the very quick fox")
        kinds = [o.kind for o in ops]
        assert "insert" in kinds

    def test_diff_pure_delete_emits_delete_op(self) -> None:
        ops = diff_words("the very quick fox", "the quick fox")
        kinds = [o.kind for o in ops]
        assert "delete" in kinds

    def test_diff_replace_emits_replace_op(self) -> None:
        ops = diff_words("the quick fox", "the brown fox")
        replace_ops = [o for o in ops if o.kind == "replace"]
        assert replace_ops, "expected at least one replace op"
        assert any("brown" in o.after for o in replace_ops)

    def test_diff_coalesces_adjacent_same_kind_ops(self) -> None:
        # When two consecutive tokens are both inserts (no equal tokens in
        # between), the coalescer should merge them into a single op.
        ops = diff_words("hello world", "hello big bright world")
        insert_ops = [o for o in ops if o.kind == "insert"]
        # "big bright " is one contiguous insert run.
        assert len(insert_ops) == 1
        assert "big" in insert_ops[0].after and "bright" in insert_ops[0].after

    def test_diff_to_dict_round_trip(self) -> None:
        ops = diff_words("hello", "world")
        for op in ops:
            payload = op.to_dict()
            assert set(payload.keys()) == {"kind", "before", "after"}
