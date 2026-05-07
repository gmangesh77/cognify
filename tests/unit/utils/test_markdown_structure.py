"""Tests for the structure-aware markdown parser (CONTENT-007)."""

from __future__ import annotations

from src.utils.markdown_structure import (
    extract_humanizable_text,
    humanizable_blocks,
    parse_markdown_blocks,
    reassemble,
    replace_humanized_text,
    restore_inline_markdown,
    strip_inline_markdown,
)


class TestParseMarkdownBlocks:
    def test_classifies_paragraph(self) -> None:
        blocks = parse_markdown_blocks("Just a paragraph.")
        assert len(blocks) == 1
        assert blocks[0].kind == "content"

    def test_classifies_heading(self) -> None:
        blocks = parse_markdown_blocks("# Title\n\nbody")
        kinds = [b.kind for b in blocks]
        assert kinds == ["heading", "content"]

    def test_classifies_image(self) -> None:
        blocks = parse_markdown_blocks("![alt](http://x.com/y.png)")
        assert blocks[0].kind == "image"

    def test_classifies_hr(self) -> None:
        blocks = parse_markdown_blocks("---")
        assert blocks[0].kind == "hr"

    def test_classifies_code_block(self) -> None:
        md = "```python\nprint('hi')\n```"
        blocks = parse_markdown_blocks(md)
        assert blocks[0].kind == "code_block"
        assert "print('hi')" in blocks[0].raw

    def test_classifies_blockquote(self) -> None:
        blocks = parse_markdown_blocks("> a quote\n> two lines")
        assert blocks[0].kind == "blockquote"

    def test_classifies_bullet_list(self) -> None:
        blocks = parse_markdown_blocks("- item one\n- item two")
        assert blocks[0].kind == "bullet_list"
        assert blocks[0].texts == ["item one", "item two"]

    def test_classifies_numbered_list(self) -> None:
        blocks = parse_markdown_blocks("1. first\n2. second")
        assert blocks[0].kind == "numbered_list"
        assert blocks[0].prefixes == ["1.", "2."]

    def test_classifies_table(self) -> None:
        md = "| a | b |\n|---|---|\n| 1 | 2 |"
        blocks = parse_markdown_blocks(md)
        assert blocks[0].kind == "table"


class TestExtractHumanizableText:
    def test_paragraph_returns_text(self) -> None:
        block = parse_markdown_blocks("hello **bold** world")[0]
        assert extract_humanizable_text(block) == "hello bold world"

    def test_heading_returns_none(self) -> None:
        block = parse_markdown_blocks("# Title")[0]
        assert extract_humanizable_text(block) is None

    def test_code_block_returns_none(self) -> None:
        block = parse_markdown_blocks("```\nx=1\n```")[0]
        assert extract_humanizable_text(block) is None

    def test_image_returns_none(self) -> None:
        block = parse_markdown_blocks("![a](b)")[0]
        assert extract_humanizable_text(block) is None


class TestHumanizableBlocks:
    def test_skips_non_prose(self) -> None:
        md = "# Title\n\nprose body\n\n![img](u)\n\n- a\n- b"
        blocks = parse_markdown_blocks(md)
        rewritable = humanizable_blocks(blocks)
        kinds = {blocks[i].kind for i, _ in rewritable}
        assert "heading" not in kinds
        assert "image" not in kinds
        assert kinds == {"content", "bullet_list"}


class TestRoundTrip:
    def test_reassemble_after_replace_keeps_structure(self) -> None:
        md = "# Heading\n\nFirst paragraph.\n\n![img](u)\n\n- one\n- two"
        blocks = parse_markdown_blocks(md)
        # Rewrite the paragraph and the list.
        para_idx = next(i for i, b in enumerate(blocks) if b.kind == "content")
        list_idx = next(i for i, b in enumerate(blocks) if b.kind == "bullet_list")
        blocks[para_idx] = replace_humanized_text(
            blocks[para_idx], "Rewritten paragraph."
        )
        blocks[list_idx] = replace_humanized_text(blocks[list_idx], "alpha\nbeta")
        out = reassemble(blocks)
        # Heading + image preserved verbatim
        assert "# Heading" in out
        assert "![img](u)" in out
        # Rewritten content present
        assert "Rewritten paragraph." in out
        assert "- alpha" in out
        assert "- beta" in out


class TestInlineMarkers:
    def test_strip_and_restore_round_trip(self) -> None:
        cleaned, markers = strip_inline_markdown("hi **bold** and *italic*")
        assert cleaned == "hi bold and italic"
        restored = restore_inline_markdown(cleaned, markers)
        assert "**bold**" in restored
        assert "*italic*" in restored
