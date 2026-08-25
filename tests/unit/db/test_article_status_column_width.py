"""Regression: every article status must fit `canonical_articles.status`.

Mirror of test_session_status_column_width.py — unit tests run on
`create_all` against SQLite, which does not enforce VARCHAR lengths, so a
too-narrow column only fails live against Postgres (AUTHOR-002 lesson).
"""

from src.db.tables import CanonicalArticleRow
from src.models.content import ArticleStatus

KNOWN_ARTICLE_STATUSES = tuple(s.value for s in ArticleStatus)


def test_status_values_are_the_four_editorial_states() -> None:
    assert KNOWN_ARTICLE_STATUSES == ("draft", "in_review", "approved", "published")


def test_all_known_statuses_fit_the_column() -> None:
    length = CanonicalArticleRow.__table__.c.status.type.length
    assert length is not None
    too_long = [s for s in KNOWN_ARTICLE_STATUSES if len(s) > length]
    assert too_long == [], f"status column is VARCHAR({length}); too long: {too_long}"


def test_column_defaults_to_draft() -> None:
    default = CanonicalArticleRow.__table__.c.status.server_default
    assert default is not None
    assert getattr(default.arg, "text", default.arg) in ("draft", "'draft'")
