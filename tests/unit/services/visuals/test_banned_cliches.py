"""Tests for the banned-cliché block + per-style register reinforcement."""

from __future__ import annotations

from src.services.visuals.banned_cliches import (
    BANNED_CLICHES_BLOCK,
    cliche_block_for_style,
)

REQUIRED_RULES = (
    "no glowing AI brain",
    "no stock-photo handshakes",
    "no flat-design illustrations when a photo style",
    "no motivational poster",
    "no tight close-ups of identifiable faces",
    "no fake or garbled text",
    "no datacentre rack-light",
    "no podium-keynote",
    "no cyber-blue Matrix-code",
    "no overly-staged group meeting",
)


def test_block_starts_with_header() -> None:
    assert BANNED_CLICHES_BLOCK.startswith("BANNED CLICHES")


def test_every_required_rule_present() -> None:
    for rule in REQUIRED_RULES:
        assert rule in BANNED_CLICHES_BLOCK, f"missing rule: {rule}"


def test_rules_are_bullet_prefixed() -> None:
    bullets = [
        line for line in BANNED_CLICHES_BLOCK.splitlines() if line.startswith("- ")
    ]
    assert len(bullets) >= len(REQUIRED_RULES)


def test_cliche_block_for_photo_style_appends_photo_reinforcement() -> None:
    block = cliche_block_for_style("lifestyle_photo")
    assert block.startswith(BANNED_CLICHES_BLOCK)
    assert "photographic register" in block
    assert "no vector or flat-design output" in block


def test_cliche_block_for_illustration_style_appends_illustration_reinforcement() -> (
    None
):
    block = cliche_block_for_style("isometric_3d")
    assert block.startswith(BANNED_CLICHES_BLOCK)
    assert "illustrated register" in block
    assert "no photorealistic output" in block


def test_cliche_block_for_technical_style_appends_technical_reinforcement() -> None:
    block = cliche_block_for_style("blueprint")
    assert "technical/schematic register" in block


def test_cliche_block_for_editorial_style_appends_editorial_reinforcement() -> None:
    block = cliche_block_for_style("editorial")
    assert "editorial register" in block


def test_cliche_block_for_unknown_style_returns_base_block() -> None:
    assert cliche_block_for_style("does_not_exist") == BANNED_CLICHES_BLOCK


def test_cliche_block_for_none_returns_base_block() -> None:
    assert cliche_block_for_style(None) == BANNED_CLICHES_BLOCK
