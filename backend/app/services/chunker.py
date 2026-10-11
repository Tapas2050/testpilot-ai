"""Text chunking utility for RAG indexing."""

import re
from typing import List


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> List[str]:
    """Split text into overlapping semantic or size-bounded chunks.

    Args:
        text: Raw document string to chunk.
        chunk_size: Maximum character length target for each chunk.
        overlap: Character overlap between consecutive chunks.

    Returns:
        List of non-empty text chunks.
    """
    if not text or not text.strip():
        return []

    # First split on natural paragraphs or Markdown section boundaries
    paragraphs = re.split(r"\n\s*\n", text.strip())
    chunks: List[str] = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If a single paragraph is longer than chunk_size, split by sentences/newlines
        if len(para) > chunk_size:
            # First flush current chunk if present
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""

            sub_parts = re.split(r"(?<=[.!?])\s+|\n+", para)
            for part in sub_parts:
                part = part.strip()
                if not part:
                    continue
                if len(current_chunk) + len(part) + 1 <= chunk_size:
                    current_chunk = f"{current_chunk}\n{part}" if current_chunk else part
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                        # Carry over overlap if possible
                        has_overlap = len(current_chunk) > overlap
                        overlap_text = current_chunk[-overlap:] if has_overlap else current_chunk
                        current_chunk = f"{overlap_text}\n{part}" if overlap_text else part
                    else:
                        # Single sentence longer than chunk_size: chunk by hard slice
                        while len(part) > chunk_size:
                            chunks.append(part[:chunk_size])
                            part = part[chunk_size - overlap :]
                        current_chunk = part
        else:
            if len(current_chunk) + len(para) + 2 <= chunk_size:
                current_chunk = f"{current_chunk}\n\n{para}" if current_chunk else para
            else:
                chunks.append(current_chunk)
                has_overlap = len(current_chunk) > overlap
                overlap_text = current_chunk[-overlap:] if has_overlap else current_chunk
                current_chunk = f"{overlap_text}\n\n{para}" if overlap_text else para

    if current_chunk and current_chunk.strip():
        chunks.append(current_chunk.strip())

    return [c.strip() for c in chunks if c.strip()]
