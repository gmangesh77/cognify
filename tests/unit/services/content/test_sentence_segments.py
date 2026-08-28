"""AUTHOR-009 — sentence-level segments between original and humanized text."""

from src.services.content.sentence_segments import (
    Segment,
    resolve_segments,
    segment_sentences,
    tokenize_sentences,
)


def _ids(segs: list[Segment], kind: str) -> set[str]:
    return {s.id for s in segs if s.kind == kind}


class TestTokenizeSentences:
    def test_splits_on_terminal_punctuation_and_keeps_whitespace(self) -> None:
        toks = tokenize_sentences("One. Two!  Three?")
        assert "".join(toks) == "One. Two!  Three?"
        assert [t for t in toks if t.strip()] == ["One.", "Two!", "Three?"]

    def test_newlines_are_their_own_tokens(self) -> None:
        toks = tokenize_sentences("## Heading\n\nBody one. Body two.")
        assert "".join(toks) == "## Heading\n\nBody one. Body two."
        assert "## Heading" in toks
        assert "\n\n" in toks


class TestSegmentSentences:
    def test_identical_text_is_one_equal_segment(self) -> None:
        segs = segment_sentences("A. B.", "A. B.")
        assert [s.kind for s in segs] == ["equal"]
        assert segs[0].before == "A. B." and segs[0].after == "A. B."

    def test_changed_sentence_becomes_a_change_segment(self) -> None:
        before = "Keep this. Delve into the topic. Keep that."
        after = "Keep this. Explore the topic. Keep that."
        segs = segment_sentences(before, after)
        changes = [s for s in segs if s.kind == "change"]
        assert len(changes) == 1
        assert changes[0].before == "Delve into the topic."
        assert changes[0].after == "Explore the topic."
        assert changes[0].ops, "change segments carry a word diff"
        assert "".join(s.before for s in segs) == before
        assert "".join(s.after for s in segs) == after

    def test_headings_and_markers_stay_in_equal_segments(self) -> None:
        before = '## Title\n\n<span data-spec-id="x"></span>\n\nDelve deeply. Fine.'
        after = '## Title\n\n<span data-spec-id="x"></span>\n\nDig in. Fine.'
        segs = segment_sentences(before, after)
        equal_text = "".join(s.before for s in segs if s.kind == "equal")
        assert "## Title" in equal_text
        assert 'data-spec-id="x"' in equal_text

    def test_insert_and_delete_segments(self) -> None:
        segs = segment_sentences("A. B.", "A. New. B.")
        inserted = [s for s in segs if s.kind == "change" and s.before == ""]
        assert inserted and inserted[0].after.strip() == "New."
        segs2 = segment_sentences("A. Gone. B.", "A. B.")
        deleted = [s for s in segs2 if s.kind == "change" and s.after == ""]
        assert deleted and deleted[0].before.strip() == "Gone."

    def test_ids_are_positional_and_unique(self) -> None:
        segs = segment_sentences("A. B. C.", "A. X. C.")
        assert [s.id for s in segs] == [f"s{i}" for i in range(len(segs))]

    def test_to_dict_is_json_shaped(self) -> None:
        seg = segment_sentences("A.", "B.")[0]
        d = seg.to_dict()
        assert set(d) == {"id", "kind", "before", "after", "ops"}
        assert isinstance(d["ops"], list) and all(isinstance(o, dict) for o in d["ops"])


class TestResolveSegments:
    def test_no_rejections_yields_final_text(self) -> None:
        before, after = "A. Old. C.", "A. New. C."
        segs = segment_sentences(before, after)
        assert resolve_segments(segs, set()) == after

    def test_rejecting_every_change_yields_original(self) -> None:
        before, after = "A. Old. C. Older.", "A. New. C. Newer."
        segs = segment_sentences(before, after)
        assert resolve_segments(segs, _ids(segs, "change")) == before

    def test_partial_rejection_mixes(self) -> None:
        before, after = "A. Old. C. Older.", "A. New. C. Newer."
        segs = segment_sentences(before, after)
        first_change = sorted(_ids(segs, "change"))[0]
        out = resolve_segments(segs, {first_change})
        assert "Old." in out and "Newer." in out
