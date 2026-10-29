"""Evidence Normalization Layer (Phase 1) + per-response trust (Phase 4).

Turns a set of normalised responses into (a) one CSV document, (b) one
deterministic digest, (c) per-response trust fields. The CSV is what enters the
existing evidence pipeline; the digest is what the signals layer reads (the
pipeline stores ``raw_summary`` per evidence record and the corpus builders read
that summary, not the file on disk).

Trust arithmetic for a single response — deliberately small, fully explainable,
and capped at the self-reported ceiling:

    trust = 40                         # a response exists and is timestamped
          + 35 × completeness          # answered / expected questions
          + 15 × identified respondent # the form recorded who answered
          + 10 × consistent            # no straightlining / no duplicate signal
    clamped to [10, 79]

79 is not decoration: it keeps self-reported data below the VERIFIED threshold
(80) that the document trust engine applies, however many responses arrive.
"""

from __future__ import annotations

import csv
import io
import re
import statistics
from datetime import datetime, timezone
from typing import Iterable, Sequence

from .mapping import detect_respondent_type, identifier_titles, is_numeric
from .models import (
    CollectionDigest,
    CollectedAnswer,
    CollectedResponse,
    EvidenceClass,
    FormQuestion,
)

RESPONSE_TRUST_CEILING = 79.0
RESPONSE_TRUST_FLOOR = 10.0

CONSISTENT = "CONSISTENT"
REVIEW = "REVIEW"
NOT_MEASURED = "NOT MEASURED"

_SLUG = re.compile(r"[^a-z0-9]+")

#: Leading columns of the materialised CSV. Question titles follow.
FIXED_COLUMNS = (
    "kulima_response_id",
    "submitted_at",
    "respondent_type",
    "respondent_ref",
    "completeness_pct",
    "consistency",
    "verification_status",
    "response_trust_score",
)


def slugify(text: str, fallback: str = "collection") -> str:
    slug = _SLUG.sub("-", (text or "").lower()).strip("-")
    return (slug[:48] or fallback).rstrip("-") or fallback


def batch_filename(form_title: str, response_count: int, moment: datetime | None = None) -> str:
    """One file per sync batch. Never one file per response.

    ``.csv`` matters: the ingestion service maps ``.csv``/``.xlsx`` to
    ``DocumentType.DATA_EXPORT`` and the trust ladder already treats that as
    survey-grade (source reliability 70).
    """
    stamp = (moment or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M")
    return f"{slugify(form_title, 'responses')}-{stamp}-{response_count}responses.csv"


# ── Per-response trust ───────────────────────────────────────────────────────

def _expected_questions(questions: Sequence[FormQuestion]) -> int:
    return max(len({q.title for q in questions}), 1)


def score_consistency(response: CollectedResponse, all_responses: Sequence[CollectedResponse]) -> tuple[str, list[str]]:
    """Deterministic consistency checks only. No model, no guessing.

    ``NOT MEASURED`` is returned when there is not enough structure to judge —
    it is never silently upgraded to ``CONSISTENT``.
    """
    notes: list[str] = []
    scale_values = [
        a.value.strip()
        for a in response.answers
        if a.answer_type in {"linear scale", "rating", "single choice", "dropdown"} and a.value.strip()
    ]
    if len(scale_values) >= 4 and len(set(scale_values)) == 1:
        notes.append(f"Identical answer given across {len(scale_values)} scale questions (possible straightlining).")

    numeric = [a.value for a in response.answers if is_numeric(a.value)]
    negative = [v for v in numeric if v.startswith("-")]
    if negative:
        notes.append(f"{len(negative)} numeric answer(s) are negative and may need review.")

    if response.respondent_ref:
        siblings = [
            r for r in all_responses
            if r.respondent_ref and r.respondent_ref == response.respondent_ref and r.response_id != response.response_id
        ]
        if siblings:
            notes.append(f"Same respondent marker appears in {len(siblings)} other response(s).")

    if notes:
        return REVIEW, notes
    if not response.answers:
        return NOT_MEASURED, ["No answers recorded — completeness cannot be judged."]
    if len(scale_values) < 2 and not numeric:
        return NOT_MEASURED, ["No scale or numeric answers to cross-check."]
    return CONSISTENT, []


def score_response_trust(
    response: CollectedResponse,
    expected_count: int,
    consistency: str,
) -> float:
    answered = len([a for a in response.answers if a.value])
    completeness = min(1.0, answered / max(expected_count, 1))
    response.answered_count = answered
    response.expected_count = expected_count
    response.completeness_pct = round(completeness * 100.0, 1)

    trust = 40.0
    trust += 35.0 * completeness
    if response.respondent_type and response.respondent_type != "Unidentified respondent":
        trust += 15.0
    if consistency == CONSISTENT:
        trust += 10.0
    return round(max(RESPONSE_TRUST_FLOOR, min(RESPONSE_TRUST_CEILING, trust)), 1)


def annotate_responses(
    responses: Sequence[CollectedResponse],
    questions: Sequence[FormQuestion],
) -> list[CollectedResponse]:
    """Fill the Phase 4 fields for every response (idempotent, pure)."""
    expected = _expected_questions(questions)
    enriched: list[CollectedResponse] = []
    for r in responses:
        r.respondent_type, r.respondent_ref = detect_respondent_type(r.answers)
        r.verification_status = "SELF_REPORTED"
        r.consistency, r.consistency_notes = score_consistency(r, responses)
        r.trust_score = score_response_trust(r, expected, r.consistency)
        enriched.append(r)
    return enriched


# ── CSV materialisation ──────────────────────────────────────────────────────

def _answer_by_title(response: CollectedResponse) -> dict[str, str]:
    merged: dict[str, str] = {}
    for a in response.answers:
        title = a.question_title or a.question_key
        if title in merged and merged[title]:
            merged[title] = f"{merged[title]}; {a.value}" if a.value else merged[title]
        else:
            merged[title] = a.value
    return merged


def to_csv_bytes(responses: Sequence[CollectedResponse], questions: Sequence[FormQuestion]) -> bytes:
    """Deterministic CSV of the batch. Contact-type answers are redacted."""
    titles: list[str] = []
    for q in questions:
        if q.title and q.title not in titles:
            titles.append(q.title)
    for r in responses:
        for a in r.answers:
            if a.question_title and a.question_title not in titles:
                titles.append(a.question_title)
    redacted = {t for r in responses for t in identifier_titles(r.answers)}

    buf = io.StringIO(newline="")
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(list(FIXED_COLUMNS) + titles)
    for r in responses:
        answers = _answer_by_title(r)
        row = [
            r.response_id,
            r.submitted_at,
            r.respondent_type,
            r.respondent_ref or "anonymous",
            f"{r.completeness_pct:.1f}",
            r.consistency,
            r.verification_status,
            f"{r.trust_score:.1f}",
        ]
        for title in titles:
            row.append("[REDACTED — identifier]" if title in redacted else answers.get(title, ""))
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


# ── Digest ───────────────────────────────────────────────────────────────────

def build_digest(
    form_title: str,
    responses: Sequence[CollectedResponse],
    *,
    source_kind: str,
    purpose: str,
    evidence_class: str = EvidenceClass.FORM.value,
    max_verbatim: int = 14,
) -> CollectionDigest:
    """Summary the signals layer can match terms against, plus honest counts.

    Verbatim lines are copied from respondent answers (truncated), never
    paraphrased. Nothing is asserted about what a theme "means".
    """
    stamps = sorted(r.submitted_at for r in responses if r.submitted_at)
    mix: dict[str, int] = {}
    for r in responses:
        mix[r.respondent_type] = mix.get(r.respondent_type, 0) + 1
    flagged = sum(1 for r in responses if r.consistency == REVIEW)
    scores = [r.trust_score for r in responses] or [0.0]
    completeness = [r.completeness_pct for r in responses] or [0.0]

    verbatim: list[str] = []
    seen: set[str] = set()
    ranked = sorted(
        (
            (a.value, r.respondent_type, a.question_title)
            for r in responses
            for a in r.answers
            if a.value and len(a.value.strip()) > 12 and not is_numeric(a.value)
        ),
        key=lambda t: -len(t[0]),
    )
    for value, respondent, title in ranked:
        clean = " ".join(value.split())[:180]
        if clean.lower() in seen:
            continue
        seen.add(clean.lower())
        verbatim.append(f'"{clean}" — {respondent} ({title})'[:220])
        if len(verbatim) >= max_verbatim:
            break

    themes = sorted({r.respondent_type for r in responses})
    lines = [
        f"Collection batch: {form_title} ({source_kind.replace('_', ' ')})",
        f"Purpose: {purpose.replace('_', ' ')} · Evidence class: {evidence_class}",
        f"Responses in batch: {len(responses)}",
    ]
    if stamps:
        lines.append(f"Response window: {stamps[0]} to {stamps[-1]}")
    lines.append(
        f"Median completeness: {statistics.median(completeness):.0f}% · "
        f"Median response trust: {statistics.median(scores):.1f}/100 (self-reported, capped at {RESPONSE_TRUST_CEILING:.0f})"
    )
    lines.append("Respondent mix: " + ", ".join(f"{k} {v}" for k, v in sorted(mix.items(), key=lambda kv: -kv[1])))
    lines.append(
        f"Verification status: SELF_REPORTED — collected by the assessed entity, not independently verified."
    )
    if flagged:
        lines.append(f"Responses flagged for review (consistency): {flagged}")
    if verbatim:
        lines.append("Respondent statements (verbatim, truncated):")
        lines.extend(f"- {v}" for v in verbatim)
    lines.append(
        "Corroboration rule: repeated syncs of this instrument count as one source; "
        "independent instruments and documents are what corroborate."
    )

    return CollectionDigest(
        form_title=form_title,
        source_kind=source_kind,
        purpose=purpose,
        response_count=len(responses),
        window_start=stamps[0] if stamps else "",
        window_end=stamps[-1] if stamps else "",
        median_completeness_pct=round(float(statistics.median(completeness)), 1),
        median_trust_score=round(float(statistics.median(scores)), 1),
        respondent_mix=mix,
        consistency_flagged=flagged,
        themes=themes,
        verbatim_lines=verbatim,
        evidence_class=evidence_class,
        text="\n".join(lines),
    )


def digest_from_rows(
    form_title: str,
    rows: Iterable[CollectedResponse],
    *,
    source_kind: str,
    purpose: str,
    evidence_class: str = EvidenceClass.FORM.value,
) -> CollectionDigest:
    return build_digest(
        form_title,
        list(rows),
        source_kind=source_kind,
        purpose=purpose,
        evidence_class=evidence_class,
    )


def parse_timestamp(raw: str) -> str:
    """Normalise an ISO-8601 submission stamp (Google returns Z-suffixed)."""
    text = (raw or "").strip()
    if not text:
        return ""
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text[:32]
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()
