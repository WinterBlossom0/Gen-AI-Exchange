from __future__ import annotations

from typing import List


def chunk_by_words(text: str, chunk_tokens: int = 45000, overlap_tokens: int = 500) -> List[str]:
    """
    Approximate token-based chunking using whitespace-separated words.
    - Splits text by whitespace into "tokens" (words)
    - Emits chunks of up to `chunk_tokens` words
    - Overlaps consecutive chunks by `overlap_tokens` words

    Note: This is an approximation and not model-token aware. It trades exactness
    for zero dependencies and speed.
    """
    if not text:
        return [""]
    if chunk_tokens <= 0:
        return [text]
    if overlap_tokens < 0:
        overlap_tokens = 0

    tokens = text.split()
    n = len(tokens)
    if n <= chunk_tokens:
        return [text]

    chunks: List[str] = []
    start = 0
    while start < n:
        end = min(start + chunk_tokens, n)
        chunk = " ".join(tokens[start:end])
        chunks.append(chunk)
        if end >= n:
            break
        start = max(0, end - overlap_tokens)
    return chunks
