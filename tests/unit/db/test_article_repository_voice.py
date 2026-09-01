"""Unit tests for PgArticleRepository._to_model voice-field mapping (AUTHOR-011).

Pure mapping tests — no database involved. InMemoryArticleRepository just
stores the model as-is (trivially true round trip), so the real gap is in
the PG row <-> model mapping, tested here directly against `_to_model`.
"""

from datetime import UTC, datetime
from uuid import uuid4

from src.db.repositories import PgArticleRepository
from src.db.tables import CanonicalArticleRow


def _row(**overrides: object) -> CanonicalArticleRow:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "title": "Title",
        "subtitle": None,
        "body_markdown": "## Intro\n\nBody.\n",
        "summary": "Summary.",
        "content_type": "article",
        "domain": "cybersecurity",
        "ai_generated": True,
        "status": "draft",
        "generated_at": datetime.now(UTC),
        "key_claims": [],
        "seo": {
            "title": "T",
            "description": "D",
            "keywords": [],
            "canonical_url": None,
            "structured_data": None,
        },
        "citations": [],
        "visuals": [],
        "provenance": {
            "research_session_id": str(uuid4()),
            "brief_id": None,
            "primary_model": "claude-opus-4-5",
            "drafting_model": "claude-sonnet-4-5",
            "embedding_model": "all-MiniLM-L6-v2",
            "embedding_version": "1.0.0",
        },
        "authors": ["Cognify"],
        "audience_persona": None,
        "voice_persona_id": None,
        "voice_match_score": None,
        "voice_scores_by_section": None,
        "few_shot_sample_ids": [],
    }
    defaults.update(overrides)
    return CanonicalArticleRow(**defaults)


def test_to_model_maps_audience_persona() -> None:
    row = _row(audience_persona="general_business")
    article = PgArticleRepository._to_model(row)
    assert article.audience_persona == "general_business"


def test_to_model_defaults_voice_fields_to_none_and_empty() -> None:
    row = _row()
    article = PgArticleRepository._to_model(row)
    assert article.voice_persona_id is None
    assert article.voice_match_score is None
    assert article.voice_scores_by_section is None
    assert article.few_shot_sample_ids == []


def test_to_model_maps_voice_persona_id() -> None:
    persona_id = uuid4()
    row = _row(voice_persona_id=persona_id)
    article = PgArticleRepository._to_model(row)
    assert article.voice_persona_id == persona_id


def test_to_model_maps_voice_match_score_as_int() -> None:
    row = _row(voice_match_score=87.0)
    article = PgArticleRepository._to_model(row)
    assert article.voice_match_score == 87
    assert isinstance(article.voice_match_score, int)


def test_to_model_maps_voice_scores_by_section() -> None:
    row = _row(voice_scores_by_section={"0": 88, "1": 72})
    article = PgArticleRepository._to_model(row)
    assert article.voice_scores_by_section == {"0": 88, "1": 72}


def test_to_model_maps_few_shot_sample_ids_from_strings_to_uuids() -> None:
    s1, s2 = uuid4(), uuid4()
    row = _row(few_shot_sample_ids=[str(s1), str(s2)])
    article = PgArticleRepository._to_model(row)
    assert article.few_shot_sample_ids == [s1, s2]
