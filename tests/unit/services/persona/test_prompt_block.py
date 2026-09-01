"""AUTHOR-011 — confidence-gated voice block + registry keys."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from src.agents.prompts import DEFAULT_PROMPTS, bind_prompt_overrides
from src.models.persona import DimStat, PersonaSample, VoiceFingerprint
from src.services.persona.fingerprint import DIMENSIONS
from src.services.persona.prompt_block import build_voice_block


def _fp(conf_len: float, conf_hedge: float) -> VoiceFingerprint:
    dims = {name: DimStat(mean=1.0, stddev=0.1, confidence=0.0) for name in DIMENSIONS}
    dims["sentence_len_mean"] = DimStat(mean=17.0, stddev=4.0, confidence=conf_len)
    dims["hedge_rate"] = DimStat(mean=2.0, stddev=0.5, confidence=conf_hedge)
    return VoiceFingerprint(dims=dims, sample_count=6)


def _sample(text: str) -> PersonaSample:
    return PersonaSample(
        persona_id=uuid4(),
        text=text,
        word_count=len(text.split()),
        created_at=datetime.now(UTC),
    )


class TestBuildVoiceBlock:
    def test_only_confident_dimensions_are_listed(self) -> None:
        block = build_voice_block(_fp(0.9, 0.2), [])
        assert "average sentence length" in block and "17.0" in block
        assert "hedging" not in block

    def test_targets_carry_low_and_high(self) -> None:
        block = build_voice_block(_fp(0.9, 0.9), [])
        assert "13.0" in block and "21.0" in block  # 17 ± 4

    def test_samples_are_appended_as_excerpts(self) -> None:
        block = build_voice_block(
            _fp(0.9, 0.9), [_sample("Sample prose here. It reads well.")]
        )
        assert "Sample 1" in block and "Sample prose here." in block

    def test_registry_override_changes_intro(self) -> None:
        with bind_prompt_overrides({"voice.block_intro": "VOICE-OVERRIDE"}):
            assert build_voice_block(_fp(0.9, 0.9), []).startswith("VOICE-OVERRIDE")

    def test_keys_registered(self) -> None:
        for key in (
            "voice.block_intro",
            "voice.dim_line",
            "voice.samples_intro",
            "voice.fix.system",
            "voice.fix.user",
        ):
            assert key in DEFAULT_PROMPTS
        assert DEFAULT_PROMPTS["voice.fix.user"].variables == frozenset(
            {"voice_block", "deviations", "section_text"}
        )
