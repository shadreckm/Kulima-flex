"""Strip document-format metadata so it never appears as research findings.

PDF byte-decode fallbacks and some Tavily PDF hits leak headers such as
``%PDF-1.4``, ``/Creator``, ``CreationDate``, and Mozilla/Skia producer
strings. Those are not research evidence.
"""

from __future__ import annotations

import re

_METADATA_LINE_RE = re.compile(
    r"^(?:"
    r"%PDF-|"
    r"%%EOF|"
    r"\d+\s+\d+\s+obj\b|"
    r"endobj|endstream|^stream$|^xref$|^trailer$|^startxref$|"
    r"/(?:Type|Subtype|Filter|Length|Creator|Producer|CreationDate|ModDate|"
    r"Title|Author|Keywords|Subject|Trapped|Pages|Count|Kids|Parent|"
    r"MediaBox|CropBox|Resources|Font|ProcSet|Contents|Root|Info|ID|Size|Prev)\b|"
    r"D:\d{8,}"
    r")",
    re.IGNORECASE,
)

_POLLUTION_TOKEN_RE = re.compile(
    r"%PDF-\d(?:\.\d)?|/Creator\b|/Producer\b|/CreationDate\b|/ModDate\b|"
    r"\bendobj\b|\bendstream\b|obj\s*<<|Skia/PDF|Mozilla Firefox|"
    r"Chromium|LibreOffice|Microsoft®?\s*Word",
    re.IGNORECASE,
)


def is_metadata_pollution(text: str) -> bool:
    """True when a snippet is document metadata rather than readable evidence."""
    sample = " ".join((text or "").split())
    if not sample:
        return True
    if sample.startswith("%PDF"):
        return True
    hits = len(_POLLUTION_TOKEN_RE.findall(sample[:2000]))
    letters = sum(1 for ch in sample if ch.isalpha())
    if letters < 20 and hits:
        return True
    if hits >= 2 and letters < 80:
        return True
    return False


def sanitize_extracted_text(text: str) -> str:
    """Drop PDF/XREF metadata lines and return remaining prose."""
    if not text:
        return ""
    kept: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _METADATA_LINE_RE.match(line):
            continue
        if _POLLUTION_TOKEN_RE.search(line) and sum(ch.isalpha() for ch in line) < 40:
            continue
        kept.append(raw_line)
    cleaned = "\n".join(kept)
    compact = " ".join(cleaned.split())
    if is_metadata_pollution(compact):
        return ""
    return cleaned.strip()


def sanitize_snippet(text: str, max_chars: int = 520) -> str:
    """Sanitize then compact a source snippet for research display."""
    cleaned = sanitize_extracted_text(text)
    if not cleaned:
        return ""
    compact = " ".join(cleaned.split())
    if is_metadata_pollution(compact):
        return ""
    if len(compact) > max_chars:
        return compact[:max_chars].rstrip() + "…"
    return compact
