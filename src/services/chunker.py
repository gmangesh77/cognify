"""Token-aware document chunker.

Splits text into chunks of a configurable token size with overlap.
Uses tiktoken (cl100k_base) for token counting. Pure logic — no I/O.

Note: tiktoken uses cl100k_base (GPT-4 family) while the embedding
model (all-MiniLM-L6-v2) uses WordPiece. Token counts diverge ~10-20%.
The embedding model truncates silently at its sequence limit — this is
an accepted trade-off for consistent, predictable chunk sizes.
"""

import tiktoken

from src.models.research import ChunkMetadata, DocumentChunk


class TokenChunker:
    """Splits text into token-aware chunks with overlap."""

    def __init__(self, chunk_size: int = 512, overlap: int = 50) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._enc = tiktoken.get_encoding("cl100k_base")

    def chunk(self, text: str, metadata: ChunkMetadata) -> list[DocumentChunk]:
        """Split text into chunks. Returns empty list for empty text."""
        stripped = text.strip()
        if not stripped:
            return []

        tokens = self._enc.encode(stripped)
        if len(tokens) <= self._chunk_size:
            return [self._make_chunk(stripped, metadata, 0)]

        return self._split_tokens(tokens, metadata)

    def _split_tokens(
        self, tokens: list[int], metadata: ChunkMetadata
    ) -> list[DocumentChunk]:
        """Sliding window split with overlap."""
        chunks: list[DocumentChunk] = []
        step = self._chunk_size - self._overlap
        start = 0
        index = 0

        while start < len(tokens):
            end = min(start + self._chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            text = self._enc.decode(chunk_tokens)
            chunks.append(self._make_chunk(text, metadata, index))
            index += 1
            start += step
            if end == len(tokens):
                break

        return chunks

    def _make_chunk(
        self, text: str, metadata: ChunkMetadata, index: int
    ) -> DocumentChunk:
        """Create a DocumentChunk with metadata."""
        return DocumentChunk(
            text=text,
            source_url=metadata.source_url,
            source_title=metadata.source_title,
            topic_id=metadata.topic_id,
            session_id=metadata.session_id,
            chunk_index=index,
            published_at=metadata.published_at,
            author=metadata.author,
        )
