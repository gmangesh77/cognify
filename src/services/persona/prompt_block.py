"""Confidence-gated voice block for the drafter / fixer (spec §4.4)."""

from __future__ import annotations

from src.agents.prompts import render_prompt
from src.models.persona import DimStat, PersonaSample, VoiceFingerprint
from src.services.persona.few_shot import excerpt
from src.services.persona.fingerprint import DIM_LABELS
from src.services.persona.scoring import MIN_CONFIDENCE


def _dim_line(dim: str, stat: DimStat) -> str:
    return "- " + render_prompt(
        "voice.dim_line",
        label=DIM_LABELS.get(dim, dim),
        target=f"{stat.mean:.1f}",
        low=f"{max(stat.mean - stat.stddev, 0.0):.1f}",
        high=f"{stat.mean + stat.stddev:.1f}",
    )


def build_voice_block(fp: VoiceFingerprint, samples: list[PersonaSample]) -> str:
    """Intro + one line per confident dimension + few-shot excerpts."""
    lines = [render_prompt("voice.block_intro")]
    lines += [
        _dim_line(d, s) for d, s in fp.dims.items() if s.confidence >= MIN_CONFIDENCE
    ]
    if samples:
        lines.append("")
        lines.append(render_prompt("voice.samples_intro"))
        for i, sample in enumerate(samples, 1):
            lines.append(f"Sample {i}:\n{excerpt(sample.text)}")
    return "\n".join(lines)
