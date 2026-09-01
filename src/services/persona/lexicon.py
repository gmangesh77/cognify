"""Stylometric lexicon and dimension labels."""

DIM_LABELS: dict[str, str] = {
    "sentence_len_mean": "average sentence length (words)",
    "sentence_len_std": "sentence length variation",
    "fk_grade": "reading grade level",
    "ttr": "vocabulary variety (type-token ratio)",
    "contraction_rate": "contractions per 100 words",
    "hedge_rate": "hedging words per 100 words",
    "booster_rate": "booster words per 100 words",
    "punct_comma_per_1k": "commas per 1,000 words",
    "punct_semicolon_per_1k": "semicolons per 1,000 words",
    "punct_dash_per_1k": "dashes per 1,000 words",
    "punct_question_per_1k": "questions per 1,000 words",
    "paragraph_len_mean": "average paragraph length (words)",
    "first_person_rate": "first-person words per 100 words",
}

_HEDGES = frozenset(
    [
        "maybe",
        "perhaps",
        "possibly",
        "likely",
        "probably",
        "seems",
        "appears",
        "might",
        "could",
        "somewhat",
        "arguably",
        "generally",
        "often",
        "sometimes",
        "tends",
        "suggest",
        "suggests",
    ]
)

_BOOSTERS = frozenset(
    [
        "clearly",
        "obviously",
        "certainly",
        "definitely",
        "absolutely",
        "always",
        "never",
        "undoubtedly",
        "must",
        "essential",
        "critical",
        "crucial",
        "extremely",
        "highly",
        "truly",
    ]
)

_FIRST_PERSON = frozenset(
    [
        "i",
        "i'm",
        "i've",
        "i'd",
        "i'll",
        "me",
        "my",
        "mine",
        "we",
        "we're",
        "we've",
        "we'd",
        "our",
        "ours",
        "us",
    ]
)

__all__ = [
    "DIM_LABELS",
    "_HEDGES",
    "_BOOSTERS",
    "_FIRST_PERSON",
]
