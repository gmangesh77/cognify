"""Banned-cliché block appended verbatim to every planner and prompt call.

This is the single most important defence against the user's
"not good and meaningful" complaint about the legacy hero-only stack.
The block targets the recurring failure modes of multimodal image
models in business contexts: glowing AI brains, stock handshakes,
forced collaboration tropes, and so on.
"""

from __future__ import annotations

from src.services.visuals.visual_styles import VISUAL_STYLES

_BASE_RULES: tuple[str, ...] = (
    "no glowing AI brain or neural-network glow effects",
    "no stock-photo handshakes or jumping-celebration poses",
    "no flat-design illustrations when a photo style is selected "
    "(and vice versa — keep the chosen register)",
    "no motivational poster or heroic-builder vibes",
    "no tight close-ups of identifiable faces",
    "no fake or garbled text on screens, signs, or whiteboards "
    "(use real fragments or none)",
    "no datacentre rack-light cliché",
    "no podium-keynote or pointing-at-chart staging",
    "no cyber-blue Matrix-code rain or digital-rain backgrounds",
    "no overly-staged group meeting shots with everyone laughing at a laptop",
)

_BLOCK_HEADER = "BANNED CLICHES (do not generate any of these):"

BANNED_CLICHES_BLOCK: str = "\n".join(
    [_BLOCK_HEADER, *(f"- {rule}" for rule in _BASE_RULES)]
)

_PHOTO_REINFORCEMENT = (
    "Reinforce: photographic register — no vector or flat-design output."
)
_ILLUSTRATION_REINFORCEMENT = (
    "Reinforce: illustrated register — no photorealistic output."
)
_TECHNICAL_REINFORCEMENT = (
    "Reinforce: technical/schematic register — no decorative illustration "
    "or photorealistic textures."
)
_EDITORIAL_REINFORCEMENT = (
    "Reinforce: editorial register — composition over decoration, "
    "considered negative space."
)

_REINFORCEMENT_BY_CATEGORY: dict[str, str] = {
    "photo": _PHOTO_REINFORCEMENT,
    "illustration": _ILLUSTRATION_REINFORCEMENT,
    "technical": _TECHNICAL_REINFORCEMENT,
    "editorial": _EDITORIAL_REINFORCEMENT,
}


def cliche_block_for_style(style_key: str | None) -> str:
    """Return the banned-cliché block, optionally with a register reinforcement.

    When `style_key` resolves to a known catalogue entry, append a
    reinforcement line tied to the entry's category. When it does not,
    return the base block unchanged.
    """
    if style_key is None:
        return BANNED_CLICHES_BLOCK
    entry = VISUAL_STYLES.get(style_key)
    if entry is None:
        return BANNED_CLICHES_BLOCK
    reinforcement = _REINFORCEMENT_BY_CATEGORY.get(entry["category"])
    if reinforcement is None:
        return BANNED_CLICHES_BLOCK
    return f"{BANNED_CLICHES_BLOCK}\n{reinforcement}"
