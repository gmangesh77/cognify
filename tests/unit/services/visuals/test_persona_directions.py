"""Tests for the persona → visual register map."""

from __future__ import annotations

from src.services.visuals.persona_directions import (
    DEFAULT_PERSONA,
    PERSONA_VISUAL_DIRECTIONS,
    available_personas,
    get_persona_register,
)

EXPECTED_PERSONAS = {
    "general_business",
    "cto",
    "ceo",
    "marketer",
    "hr",
    "developer",
    "gtm",
    "data_scientist",
}


def test_all_personas_present() -> None:
    assert set(PERSONA_VISUAL_DIRECTIONS.keys()) == EXPECTED_PERSONAS


def test_default_persona_is_general_business() -> None:
    assert DEFAULT_PERSONA == "general_business"
    assert DEFAULT_PERSONA in PERSONA_VISUAL_DIRECTIONS


def test_get_persona_register_known() -> None:
    cto_register = get_persona_register("cto")
    assert "code on" in cto_register or "technical" in cto_register


def test_get_persona_register_none_returns_default() -> None:
    assert get_persona_register(None) == PERSONA_VISUAL_DIRECTIONS[DEFAULT_PERSONA]


def test_get_persona_register_unknown_returns_default() -> None:
    assert (
        get_persona_register("unknown_persona")
        == PERSONA_VISUAL_DIRECTIONS[DEFAULT_PERSONA]
    )


def test_available_personas_returns_sorted() -> None:
    personas = available_personas()
    assert personas == sorted(personas)
    assert set(personas) == EXPECTED_PERSONAS


def test_each_register_is_substantive() -> None:
    for persona, register in PERSONA_VISUAL_DIRECTIONS.items():
        assert len(register) >= 100, f"{persona} register is too short"
        assert "Avoid" in register, f"{persona} should call out anti-patterns"
