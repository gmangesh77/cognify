"""Persona → visual register map for the image planner.

Each register is *guidance* (not a hard rule) that nudges the planner
toward visuals fitting that audience. The page-wide art direction and
the banned-cliché block always trump the persona register, so an editor
can override stereotype risk by setting their own direction.
"""

from __future__ import annotations

DEFAULT_PERSONA = "general_business"

PERSONA_VISUAL_DIRECTIONS: dict[str, str] = {
    "general_business": (
        "Audience leans toward technical-but-business-savvy readers. Favour "
        "authentic workspace settings, real device screens (no mocked UIs), "
        "and uncluttered editorial composition. Avoid stock-photo handshakes "
        "and overly-staged group shots."
    ),
    "cto": (
        "Audience is hands-on technical leadership. Favour real code on "
        "screens (Python or TypeScript fragments are fine — no fake "
        "gibberish), distributed-system whiteboards, and editorial "
        "composition over heroic-builder tropes. Avoid datacentre cliches "
        "(rack lights, glowing wires)."
    ),
    "ceo": (
        "Audience is senior executive. Favour decision-making moments, "
        "board-table editorial composition, and considered architectural "
        "environments. Avoid podium-keynote stock and pointing-at-charts "
        "shots."
    ),
    "marketer": (
        "Audience is creative and data-aware. Favour layered editorial "
        "composition, real campaign artefacts (printed page proofs, "
        "sticky-note clusters), and natural collaboration moments. Avoid "
        "laptop-with-graph stock and forced enthusiasm."
    ),
    "hr": (
        "Audience values authentic culture. Favour candid moments in real "
        "workspaces, diverse and natural group composition, and considered "
        "editorial framing. Avoid handshakes, jumping-pose celebrations, "
        "and overly-styled meeting room shots."
    ),
    "developer": (
        "Audience is engineering-focused. Favour real keyboards, terminal "
        "screens, soldered hardware where relevant, and the considered mess "
        "of actual desks. Avoid 'hacker in hoodie' tropes, glowing matrix "
        "code rain, and cyber-blue colour casts."
    ),
    "gtm": (
        "Audience is sales/marketing/RevOps. Favour pipeline whiteboards, "
        "real CRM-like screens, and collaborative editorial moments. Avoid "
        "pointing-at-deck stock and forced cold-call composition."
    ),
    "data_scientist": (
        "Audience is quantitatively rigorous. Favour real notebook screens "
        "(matplotlib output is fine), considered desk composition, and "
        "editorial framing. Avoid 'AI brain' glowing illustrations and "
        "stock-photo data-streams."
    ),
}


def get_persona_register(persona: str | None) -> str:
    """Return the visual register for `persona`, falling back to default."""
    if persona is None:
        return PERSONA_VISUAL_DIRECTIONS[DEFAULT_PERSONA]
    return PERSONA_VISUAL_DIRECTIONS.get(
        persona, PERSONA_VISUAL_DIRECTIONS[DEFAULT_PERSONA]
    )


def available_personas() -> list[str]:
    """Sorted list of registered persona keys."""
    return sorted(PERSONA_VISUAL_DIRECTIONS.keys())
