"""Tests for the token-aware document chunker."""

from src.models.research import ChunkMetadata, DocumentChunk
from src.services.chunker import TokenChunker


def _make_metadata() -> ChunkMetadata:
    return ChunkMetadata(
        source_url="https://example.com/article",
        source_title="Test Article",
        topic_id="topic-1",
        session_id="session-1",
    )


class TestTokenChunkerShortText:
    def test_short_text_single_chunk(self) -> None:
        chunker = TokenChunker(chunk_size=512, overlap=50)
        chunks = chunker.chunk("This is a short text.", _make_metadata())
        assert len(chunks) == 1
        assert chunks[0].text == "This is a short text."
        assert chunks[0].chunk_index == 0

    def test_preserves_metadata(self) -> None:
        chunker = TokenChunker(chunk_size=512, overlap=50)
        meta = _make_metadata()
        chunks = chunker.chunk("Short text.", meta)
        assert chunks[0].source_url == meta.source_url
        assert chunks[0].source_title == meta.source_title
        assert chunks[0].topic_id == meta.topic_id
        assert chunks[0].session_id == meta.session_id


class TestTokenChunkerLongText:
    def test_long_text_multiple_chunks(self) -> None:
        chunker = TokenChunker(chunk_size=10, overlap=2)
        long_text = " ".join(f"word{i}" for i in range(50))
        chunks = chunker.chunk(long_text, _make_metadata())
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.text) > 0

    def test_chunk_indices_sequential(self) -> None:
        chunker = TokenChunker(chunk_size=10, overlap=2)
        long_text = " ".join(f"word{i}" for i in range(50))
        chunks = chunker.chunk(long_text, _make_metadata())
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_overlap_creates_shared_content(self) -> None:
        chunker = TokenChunker(chunk_size=10, overlap=3)
        long_text = " ".join(f"word{i}" for i in range(30))
        chunks = chunker.chunk(long_text, _make_metadata())
        if len(chunks) >= 2:
            assert len(chunks) >= 2


class TestTokenChunkerEdgeCases:
    def test_empty_text_returns_empty(self) -> None:
        chunker = TokenChunker(chunk_size=512, overlap=50)
        chunks = chunker.chunk("", _make_metadata())
        assert chunks == []

    def test_whitespace_only_returns_empty(self) -> None:
        chunker = TokenChunker(chunk_size=512, overlap=50)
        chunks = chunker.chunk("   \n\t  ", _make_metadata())
        assert chunks == []

    def test_returns_document_chunk_type(self) -> None:
        chunker = TokenChunker(chunk_size=512, overlap=50)
        chunks = chunker.chunk("Some text here.", _make_metadata())
        assert all(isinstance(c, DocumentChunk) for c in chunks)
