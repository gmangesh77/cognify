"""Persona voice engine (AUTHOR-011): fingerprint → block → score → fix."""

from src.services.persona.few_shot import PickResult, excerpt, pick_samples
from src.services.persona.fingerprint import (
    DIMENSIONS,
    InsufficientSamples,
    build_fingerprint,
    count_words,
    text_features,
)
from src.services.persona.lexicon import DIM_LABELS
from src.services.persona.prompt_block import build_voice_block
from src.services.persona.scoring import (
    DEVIATION_Z,
    MIN_CONFIDENCE,
    SHORT_SECTION_WORDS,
    band_for,
    score_sections,
    score_text,
)

__all__ = [
    "DEVIATION_Z",
    "DIMENSIONS",
    "DIM_LABELS",
    "MIN_CONFIDENCE",
    "InsufficientSamples",
    "PickResult",
    "SHORT_SECTION_WORDS",
    "band_for",
    "build_fingerprint",
    "build_voice_block",
    "count_words",
    "excerpt",
    "pick_samples",
    "score_sections",
    "score_text",
    "text_features",
]
