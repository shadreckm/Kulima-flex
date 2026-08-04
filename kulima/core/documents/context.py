"""Document context utilities for Ask-OS / Ask IC integrations.

Phase 3C: Build a compact, document-aware context section that can be
spliced into existing Ask IC / Ask OS prompts without changing any
backend recommendation or scoring logic.

This module is vertical-agnostic: it only depends on founder/startup
identifiers and the DocumentRepository; it does not require FLEX
specific models.
"""

from __future__ import annotations

from typing import List

from kulima.core.documents.repository import DocumentRepository
from kulima.core.documents.models import DocumentChunk


def _clip_text(value: str, limit: int = 400) -> str:
    """Collapse whitespace and truncate to a safe character limit."""

    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _summarise_chunks(chunks: List[DocumentChunk], max_chars: int = 600) -> str:
    """Build a short summary from the first few chunks of a document.

    Phase 3C uses a naive concatenation-and-truncate strategy. Later
    phases may replace this with a dedicated summarisation agent.
    """

    if not chunks:
        return ""
    pieces: list[str] = []
    running = 0
    for ch in chunks:
        if not ch.text.strip():
            continue
        snippet = _clip_text(ch.text, 300)
        if not snippet:
            continue
        if running + len(snippet) > max_chars:
            break
        pieces.append(snippet)
        running += len(snippet) + 1
        if running >= max_chars:
            break
    return " ".join(pieces)


def build_document_context_for_subject(
    founder: str,
    startup: str,
    *,
    max_documents: int = 3,
    max_chars: int = 1600,
    user_id: str | None = None,
) -> str:
    """Return a compact [DOCUMENTS] section for the given subject.

    Documents are ordered by upload time and truncated to keep the
    resulting context efficient. Each document receives a [D#] label,
    filename, and a short summary assembled from its first chunks.
    """

    repo = DocumentRepository()
    docs = repo.get_documents_for_subject(
        founder.strip(),
        (startup or "").strip(),
        user_id=user_id,
    )
    if not docs:
        return ""

    docs = docs[:max_documents]
    lines: list[str] = ["[DOCUMENTS]"]

    for idx, doc in enumerate(docs, 1):
        label = f"D{idx}"
        chunks = repo.get_chunks_for_document(doc.id)
        summary = _summarise_chunks(chunks, max_chars=max_chars // max_documents)
        doc_type = getattr(doc.doc_type, "value", str(doc.doc_type))
        lines.append(f"[{label}] {doc.filename} (type: {doc_type})")
        if summary:
            lines.append("Summary:")
            lines.append(summary)
        lines.append("")  # blank line between documents

    out = "\n".join(lines).strip()
    if len(out) > max_chars:
        return out[: max_chars - 1].rstrip() + "…"
    return out
