"""Evidence Integrity Engine — deterministic claim extraction and consistency analysis.

Architecture (six classes):

    ClaimExtractor       — one LLM call → list[Claim] (fails gracefully to [])
    ClaimNormaliser      — pure deterministic normalisation of values
    FreshnessEvaluator   — staleness classification from date signals in sources
    ContradictionDetector — detects GENUINE / TEMPORAL_DRIFT / CURRENCY_ARTEFACT
    SupportEvaluator     — detects expected claims absent from the corpus
    IntegrityScoreCalculator — scores the corpus; computes grade, depth, consistency
    EvidenceIntegrityEngine  — top-level orchestrator; returns EvidenceIntegrityReport

Non-negotiable constraints (from evidence-integrity-review.md Part VI):
  - Never modifies overall_score, trust_score, founder_score, startup_score,
    market_score, risk_score, or InvestmentBrief.recommendation
  - Only adjusts InvestmentBrief.confidence (via confidence_delta on the report)
  - Sparse evidence corpus (< 5 sources or < 2 high-authority) cannot produce
    grade worse than C through absence penalties alone
  - EIE failure → EvidenceIntegrityReport with extraction_notes set; no exception
    propagates to the caller
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from itertools import combinations
from typing import Any

from kulima.errors import EvidenceIntegrityError
from kulima.models import (
    Claim,
    ClaimType,
    ConsistencyStatus,
    Contradiction,
    ContradictionSeverity,
    EvidenceDepth,
    EvidenceIntegrityReport,
    IgnoredConflict,
    IntegrityGrade,
    StaleClaim,
    StalenessT,
    SourceAttribution,
    UnsupportedClaim,
)

_log = logging.getLogger(__name__)

# ── Authority domain sets ──────────────────────────────────────────────────────
# Extended per evidence-integrity-review.md Rule 5 — Africa authority expansion
_HIGH_AUTHORITY_DOMAINS: frozenset[str] = frozenset({
    # Global high-authority
    "crunchbase.com", "techcrunch.com", "bloomberg.com", "reuters.com",
    "ft.com", "theinformation.com", "linkedin.com", "ycombinator.com",
    "cbinsights.com", "pitchbook.com",
    # Africa-specific high-authority (original 4)
    "africabusinesscommunities.com", "disrupt-africa.com",
    "techcabal.com", "restofworld.org",
    # Africa-specific high-authority (Rule 5 expansion)
    "geekco.africa", "weetracker.com", "theafricantechchannel.com",
    "techpoint.africa", "ventureburn.com", "magnitt.com",
    "businessdayonline.com", "thisdaylive.com", "naijapreneur.com",
    "businessamlive.com", "kenyanwallstreet.com", "techbuild.africa",
    "theafricanexponent.com",
    # Government / regulatory (.gov domains handled programmatically)
})

# Africa currencies whose values should not be directly compared to USD
_AFRICA_CURRENCIES: frozenset[str] = frozenset({"ngn", "₦", "kes", "ksh", "ghs", "ghs", "etb", "xof", "xaf"})

# Stage tier normalisation map — Africa-aware (Rule 6)
_STAGE_TIERS: dict[str, int] = {
    "pre-seed": 0, "idea": 0, "concept": 0, "grant-funded startup": 0,
    "seed": 1, "post-seed": 1, "seed+": 1, "pre-series a": 1,
    "pre-series-a": 1, "bridge": 1, "accelerator-funded": 1,
    "bootstrapped but investor-ready": 1, "first institutional round": 1,
    "series a": 2, "series-a": 2, "series_a": 2,
    "series b": 3, "series-b": 3, "series_b": 3,
    "series c": 4, "series-c": 4, "series_c": 4,
    "growth": 4, "late stage": 4, "pre-ipo": 5, "ipo": 5,
}

# Deduction table per evidence-integrity-review.md Part V, Table: Revised Deduction Table
_DEDUCTIONS: dict[str, float] = {
    "CRITICAL_GENUINE": 15.0,   # cap at 30
    "HIGH_GENUINE": 8.0,        # cap at 16
    "MEDIUM_GENUINE": 4.0,      # cap at 10
    "LOW_GENUINE": 1.0,         # cap at 4
    "CRITICAL_UNSUPPORTED": 8.0,  # full corpus only; cap at 16
    "HIGH_UNSUPPORTED": 4.0,      # full corpus only; cap at 8
    "STALE_CRITICAL": 2.0,      # cap at 4
    "AGING_CRITICAL": 1.0,      # cap at 2
    "UNKNOWN_HIGH_IMPACT": 1.0, # full corpus only; cap at 3
}

# Confidence modifier per grade (evidence-integrity-review.md Table in Part V)
_CONFIDENCE_DELTA: dict[IntegrityGrade, float] = {
    IntegrityGrade.A: 0.0,
    IntegrityGrade.B: -0.02,
    IntegrityGrade.C: -0.05,
    IntegrityGrade.D: -0.10,
    IntegrityGrade.F: -0.15,
}

# SPARSE_EVIDENCE_MODE confidence modifier (applied on top of grade modifier)
_SPARSE_CONFIDENCE_DELTA: float = -0.03


# ═══════════════════════════════════════════════════════════════════════════════
# 1 — ClaimExtractor
# ═══════════════════════════════════════════════════════════════════════════════

class ClaimExtractor:
    """Extracts structured Claim objects from a research source corpus.

    Makes exactly one LLM call per ``evaluate()`` invocation.  On any
    exception the method returns ``[]`` — the pipeline continues with
    zero claims (graceful degradation path).
    """

    _SYSTEM = (
        "You are a fact-extraction system for an investment intelligence platform. "
        "Given a corpus of web source snippets about a company, extract structured "
        "factual claims. Return ONLY a JSON object with a single key 'claims' whose "
        "value is a list. Each element must have these fields:\n"
        "  claim_type: one of funding_amount | founding_year | employee_count | stage | "
        "geography | investor_identity | revenue | valuation | product_description | "
        "team_composition | legal_status | regulatory_status | partnership | market_size | "
        "growth_metric | customer_count | other\n"
        "  value_raw: verbatim text from the source\n"
        "  source_url: URL of the source\n"
        "  source_title: title of the source\n"
        "  snippet: short excerpt (max 120 chars) containing the claim\n"
        "  source_authority: 'high_authority_web' | 'web' | 'social' | 'blog'\n\n"
        "Rules:\n"
        "- Only extract material claims (funding, founding year, team size, stage, geography, "
        "investors, revenue, regulatory status).\n"
        "- Skip generic marketing language.\n"
        "- If a source contributes multiple claim types, emit one entry per claim.\n"
        "- If you cannot find any material claims, return {\"claims\": []}.\n"
        "- Do NOT infer or hallucinate. Only extract what is explicitly stated."
    )

    def __init__(self, llm: Any) -> None:
        self._llm = llm

    def extract(
        self,
        sources: list[SourceAttribution],
        founder: str,
        startup: str,
    ) -> list[Claim]:
        """Return a list of Claim objects extracted from the source corpus.

        Returns ``[]`` on any failure — the engine continues without claims.
        """
        if not sources:
            return []
        corpus = self._build_corpus(sources, founder, startup)
        try:
            raw = self._llm.complete(
                system=self._SYSTEM,
                user=corpus,
                temperature=0.0,
            )
            return self._parse_response(raw, sources)
        except Exception as exc:
            _log.warning("ClaimExtractor.extract failed: %s", exc)
            return []

    def _build_corpus(
        self,
        sources: list[SourceAttribution],
        founder: str,
        startup: str,
    ) -> str:
        lines = [f"Company: {startup}  |  Founder: {founder}\n"]
        for i, src in enumerate(sources[:20], 1):  # cap at 20 to stay within context
            lines.append(
                f"[S{i}] Title: {src.title}\n"
                f"     URL: {src.url}\n"
                f"     Authority: {src.source_type}\n"
                f"     Snippet: {src.snippet[:400]}\n"
            )
        return "\n".join(lines)

    def _parse_response(
        self,
        raw: str,
        sources: list[SourceAttribution],
    ) -> list[Claim]:
        """Parse LLM JSON response into typed Claim objects.

        Invalid or missing fields are filled with safe defaults.
        """
        try:
            text = raw.strip()
            # Strip markdown fences if present
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            data = json.loads(text)
            if not isinstance(data, dict):
                return []
            raw_claims = data.get("claims", [])
            if not isinstance(raw_claims, list):
                return []
        except (json.JSONDecodeError, ValueError):
            return []

        # Build a URL→source_type lookup for authority override
        url_authority: dict[str, str] = {s.url: s.source_type for s in sources}

        claims: list[Claim] = []
        for i, item in enumerate(raw_claims):
            if not isinstance(item, dict):
                continue
            try:
                raw_type = str(item.get("claim_type", "other")).lower()
                try:
                    ct = ClaimType(raw_type)
                except ValueError:
                    ct = ClaimType.OTHER

                url = str(item.get("source_url", ""))
                # Use the actual source authority we know; fallback to what LLM says
                authority = url_authority.get(url) or str(item.get("source_authority", "web"))

                claims.append(Claim(
                    claim_id=f"c{i + 1}",
                    claim_type=ct,
                    value_raw=str(item.get("value_raw", ""))[:500],
                    source_url=url,
                    source_authority=authority,
                    source_title=str(item.get("source_title", ""))[:200],
                    snippet=str(item.get("snippet", ""))[:200],
                    staleness=StalenessT.UNKNOWN,  # set by FreshnessEvaluator
                ))
            except Exception:
                continue  # skip malformed individual claim

        return claims


# ═══════════════════════════════════════════════════════════════════════════════
# 2 — ClaimNormaliser
# ═══════════════════════════════════════════════════════════════════════════════

class ClaimNormaliser:
    """Converts raw claim values into comparable normalised forms.

    Africa-specific rules:
    - _normalise_funding: returns None for Africa local currencies (no USD conversion
      because the conversion rate at the time of publication is unknowable)
    - _normalise_stage: uses the Africa-aware tier map (Rule 6)
    - _normalise_year: accepts 4-digit years in text
    """

    def normalise(self, claims: list[Claim]) -> list[Claim]:
        result: list[Claim] = []
        for claim in claims:
            normalised: str | None = None
            if claim.claim_type == ClaimType.FUNDING_AMOUNT:
                val = self._normalise_funding(claim.value_raw)
                normalised = str(val) if val is not None else None
            elif claim.claim_type == ClaimType.FOUNDING_YEAR:
                val = self._normalise_year(claim.value_raw)
                normalised = str(val) if val is not None else None
            elif claim.claim_type == ClaimType.STAGE:
                normalised = self._normalise_stage(claim.value_raw)
            elif claim.claim_type == ClaimType.EMPLOYEE_COUNT:
                val = self._normalise_count(claim.value_raw)
                normalised = str(val) if val is not None else None
            elif claim.claim_type == ClaimType.GEOGRAPHY:
                normalised = self._normalise_geography(claim.value_raw)
            else:
                normalised = claim.value_raw.strip().lower() if claim.value_raw else None
            result.append(claim.model_copy(update={"value_normalised": normalised}))
        return result

    # ── funding ──────────────────────────────────────────────────────────────

    def _normalise_funding(self, raw: str) -> float | None:
        """Return USD float or None.

        Returns None for Africa local currencies — we cannot reliably
        convert to USD without knowing the publication date and rate.
        """
        if not raw:
            return None
        text = raw.lower().strip()

        # Detect Africa local currencies first — return None without conversion
        for token in _AFRICA_CURRENCIES:
            if token in text:
                return None
        # Also detect naira sign ₦ directly
        if "₦" in raw:
            return None

        # Strip currency symbols
        text = re.sub(r"[€£¥\$usd\s,]", "", text)

        # Extract multiplier suffixes
        multiplier = 1.0
        if text.endswith("b") or "billion" in text:
            multiplier = 1_000_000_000
            text = re.sub(r"b(?:illion)?", "", text).strip()
        elif text.endswith("m") or "million" in text:
            multiplier = 1_000_000
            text = re.sub(r"m(?:illion)?", "", text).strip()
        elif text.endswith("k") or "thousand" in text:
            multiplier = 1_000
            text = re.sub(r"k(?:thousand)?", "", text).strip()

        # Extract numeric value
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        if not match:
            return None
        try:
            return float(match.group(1)) * multiplier
        except ValueError:
            return None

    # ── founding year ──────────────────────────────────────────────────────

    def _normalise_year(self, raw: str) -> int | None:
        """Extract a 4-digit year from free text."""
        if not raw:
            return None
        match = re.search(r"\b(19[0-9]{2}|20[0-2][0-9])\b", raw)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    # ── stage ─────────────────────────────────────────────────────────────

    def _normalise_stage(self, raw: str) -> str | None:
        """Map stage label to a canonical tier string."""
        if not raw:
            return None
        normalised = raw.lower().strip()
        # Look up in tier map; return canonical name for the tier integer
        tier = _STAGE_TIERS.get(normalised)
        if tier is not None:
            return normalised  # return the normalised key itself
        # Try partial match
        for key in _STAGE_TIERS:
            if key in normalised or normalised in key:
                return key
        return normalised  # return as-is — comparison will be done by tier lookup

    # ── employee count ────────────────────────────────────────────────────

    def _normalise_count(self, raw: str) -> int | None:
        """Extract a headcount integer from free text."""
        if not raw:
            return None
        # Look for first integer
        match = re.search(r"\b(\d+)\b", raw)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    # ── geography ────────────────────────────────────────────────────────

    def _normalise_geography(self, raw: str) -> str | None:
        """Return lowercase stripped geography string."""
        if not raw:
            return None
        return raw.strip().lower()

    # ── stage tier helper ─────────────────────────────────────────────────

    @staticmethod
    def stage_tier(normalised_stage: str) -> int | None:
        """Return the numeric tier for a normalised stage label, or None."""
        return _STAGE_TIERS.get(normalised_stage.lower().strip())


# ═══════════════════════════════════════════════════════════════════════════════
# 3 — FreshnessEvaluator
# ═══════════════════════════════════════════════════════════════════════════════

class FreshnessEvaluator:
    """Assigns a StalenessT to each Claim based on date signals in the source."""

    # Boundaries in months
    _FRESH_MONTHS = 12
    _AGING_MONTHS = 24
    _STALE_MONTHS = 48

    def evaluate(self, claims: list[Claim], sources: list[SourceAttribution]) -> list[Claim]:
        """Return claims with staleness field populated."""
        # Build URL → staleness lookup from sources
        url_staleness: dict[str, StalenessT] = {}
        for src in sources:
            st = self._from_source(src)
            url_staleness[src.url] = st

        result: list[Claim] = []
        for claim in claims:
            # Try to get staleness from URL match first
            st = url_staleness.get(claim.source_url)
            if st is None:
                # Fall back to snippet-level date extraction
                st = self._from_text(claim.snippet) or StalenessT.UNKNOWN
            result.append(claim.model_copy(update={"staleness": st}))
        return result

    def _from_source(self, src: SourceAttribution) -> StalenessT:
        """Derive staleness from both URL and snippet of a source."""
        st = self._from_text(src.snippet)
        if st is not None:
            return st
        st = self._from_url(src.url)
        return st or StalenessT.UNKNOWN

    def _from_url(self, url: str) -> StalenessT | None:
        """Extract date from URL path patterns like /2022/03/15/ or /2022-03/."""
        if not url:
            return None
        # Match YYYY/MM/DD or YYYY/MM or YYYY-MM-DD or YYYY-MM
        match = re.search(r"/(\d{4})[/\-](\d{2})", url)
        if match:
            return self._date_to_staleness(int(match.group(1)), int(match.group(2)))
        # Match ?date=YYYY-MM-DD
        match = re.search(r"date=(\d{4})-(\d{2})", url)
        if match:
            return self._date_to_staleness(int(match.group(1)), int(match.group(2)))
        return None

    def _from_text(self, text: str) -> StalenessT | None:
        """Extract date signals from snippet text."""
        if not text:
            return None
        # Match "January 2024", "Jan 2024", "2024-01-15", "2024/01/15"
        month_names = (
            "january|february|march|april|may|june|july|august|"
            "september|october|november|december|"
            "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
        )
        match = re.search(
            rf"(?:{month_names})\s+(\d{{4}})",
            text,
            re.IGNORECASE,
        )
        if match:
            year = int(match.group(1))
            # Use approximate month 6 (mid-year) since we only have the year
            return self._date_to_staleness(year, 6)

        # ISO date
        match = re.search(r"\b(\d{4})[/\-](\d{2})[/\-]\d{2}\b", text)
        if match:
            return self._date_to_staleness(int(match.group(1)), int(match.group(2)))

        # Plain year mention in context (e.g. "In 2022, the company...")
        match = re.search(r"\bIn (\d{4})\b", text)
        if match:
            return self._date_to_staleness(int(match.group(1)), 6)

        return None

    def _date_to_staleness(self, year: int, month: int) -> StalenessT:
        now = datetime.now(timezone.utc)
        try:
            pub = datetime(year, max(1, min(month, 12)), 1, tzinfo=timezone.utc)
        except ValueError:
            return StalenessT.UNKNOWN
        months_ago = (now.year - pub.year) * 12 + (now.month - pub.month)
        if months_ago <= self._FRESH_MONTHS:
            return StalenessT.FRESH
        if months_ago <= self._AGING_MONTHS:
            return StalenessT.AGING
        if months_ago <= self._STALE_MONTHS:
            return StalenessT.STALE
        return StalenessT.VERY_STALE


# ═══════════════════════════════════════════════════════════════════════════════
# 4 — ContradictionDetector
# ═══════════════════════════════════════════════════════════════════════════════

class ContradictionDetector:
    """Compares pairs of same-type claims and classifies conflicts.

    Three subtypes per evidence-integrity-review.md Part IV Change 3:
      GENUINE_CONTRADICTION  — deduction applied
      TEMPORAL_DRIFT         — stored as IgnoredConflict, no deduction
      CURRENCY_ARTEFACT      — stored as IgnoredConflict, no deduction
    """

    def detect(
        self,
        claims: list[Claim],
    ) -> tuple[list[Contradiction], list[IgnoredConflict]]:
        contradictions: list[Contradiction] = []
        ignored: list[IgnoredConflict] = []

        # Group by claim_type
        by_type: dict[ClaimType, list[Claim]] = {}
        for claim in claims:
            by_type.setdefault(claim.claim_type, []).append(claim)

        for ct, group in by_type.items():
            # Only compare claims from different sources
            for a, b in combinations(group, 2):
                if a.source_url == b.source_url:
                    continue
                result = self._compare(ct, a, b)
                if result is None:
                    continue
                if isinstance(result, Contradiction):
                    contradictions.append(result)
                else:
                    ignored.append(result)

        return contradictions, ignored

    # ── dispatcher ────────────────────────────────────────────────────────

    def _compare(
        self, ct: ClaimType, a: Claim, b: Claim
    ) -> Contradiction | IgnoredConflict | None:
        if ct == ClaimType.FUNDING_AMOUNT:
            return self._compare_funding(a, b)
        if ct == ClaimType.FOUNDING_YEAR:
            return self._compare_founding_year(a, b)
        if ct == ClaimType.STAGE:
            return self._compare_stage(a, b)
        if ct == ClaimType.EMPLOYEE_COUNT:
            return self._compare_employee_count(a, b)
        if ct == ClaimType.GEOGRAPHY:
            return self._compare_geography(a, b)
        if ct == ClaimType.INVESTOR_IDENTITY:
            return self._compare_categorical_exact(a, b, ClaimType.INVESTOR_IDENTITY)
        # All other types: no automatic contradiction detection
        return None

    # ── funding amount ────────────────────────────────────────────────────

    def _compare_funding(self, a: Claim, b: Claim) -> Contradiction | IgnoredConflict | None:
        val_a = self._parse_float(a.value_normalised)
        val_b = self._parse_float(b.value_normalised)

        # If either value is None, normalisation failed (likely a local currency)
        # — this is a CURRENCY_ARTEFACT by definition
        if val_a is None or val_b is None:
            return IgnoredConflict(
                claim_a=a, claim_b=b,
                reason="CURRENCY_ARTEFACT",
                subtype="CURRENCY_ARTEFACT",
                description=(
                    "One or both funding figures use a local Africa currency "
                    "(NGN/KES/GHS/ETB). Direct comparison not possible without "
                    "publication-date FX rate."
                ),
            )

        if val_a == 0 or val_b == 0:
            return None

        larger = max(val_a, val_b)
        smaller = min(val_a, val_b)
        ratio = larger / smaller  # always >= 1

        # Within 20% → no contradiction
        if ratio <= 1.20:
            return None

        # Check for TEMPORAL_DRIFT: claims from very different staleness periods
        if self._is_temporal_drift(a, b):
            return IgnoredConflict(
                claim_a=a, claim_b=b,
                reason="TEMPORAL_DRIFT",
                subtype="TEMPORAL_DRIFT",
                description=(
                    f"Funding figures differ by {(ratio - 1) * 100:.0f}% but "
                    "sources are from different time periods — consistent with "
                    "a rolling round or additional close."
                ),
            )

        # Check for FX artefact (heuristic: delta in 30–70% range → may be FX)
        if 1.20 < ratio <= 1.70:
            return IgnoredConflict(
                claim_a=a, claim_b=b,
                reason="CURRENCY_ARTEFACT",
                subtype="CURRENCY_ARTEFACT",
                description=(
                    f"Funding gap of {(ratio - 1) * 100:.0f}% is within the "
                    "range of historical Africa currency FX movements — "
                    "possible translation artefact."
                ),
            )

        # GENUINE contradiction
        severity = self._funding_severity(ratio)
        return Contradiction(
            contradiction_id=str(uuid.uuid4())[:8],
            claim_a=a, claim_b=b,
            severity=severity,
            subtype="GENUINE_CONTRADICTION",
            description=(
                f"Funding figures disagree by {(ratio - 1) * 100:.0f}%: "
                f"{a.value_raw!r} vs {b.value_raw!r}."
            ),
            recommended_action="Verify funding amount directly with founder or cap table.",
        )

    def _funding_severity(self, ratio: float) -> ContradictionSeverity:
        if ratio >= 3.0:
            return ContradictionSeverity.CRITICAL
        if ratio >= 2.0:
            return ContradictionSeverity.HIGH
        if ratio >= 1.50:
            return ContradictionSeverity.MEDIUM
        return ContradictionSeverity.LOW

    # ── founding year ─────────────────────────────────────────────────────

    def _compare_founding_year(self, a: Claim, b: Claim) -> Contradiction | IgnoredConflict | None:
        yr_a = self._parse_int(a.value_normalised)
        yr_b = self._parse_int(b.value_normalised)
        if yr_a is None or yr_b is None:
            return None

        gap = abs(yr_a - yr_b)
        if gap == 0:
            return None

        # Africa tolerance: ≤ 2 years → IgnoredConflict (Rule 3)
        if gap <= 2:
            return IgnoredConflict(
                claim_a=a, claim_b=b,
                reason="FOUNDING_YEAR_TOLERANCE",
                subtype="TEMPORAL_DRIFT",
                description=(
                    f"Founding years differ by {gap} year(s) — within Africa "
                    "tolerance for operational start vs. legal incorporation lag."
                ),
            )

        severity = ContradictionSeverity.CRITICAL if gap > 3 else ContradictionSeverity.HIGH
        return Contradiction(
            contradiction_id=str(uuid.uuid4())[:8],
            claim_a=a, claim_b=b,
            severity=severity,
            subtype="GENUINE_CONTRADICTION",
            description=f"Founding year discrepancy of {gap} years: {yr_a} vs {yr_b}.",
            recommended_action="Confirm founding year from registration documents.",
        )

    # ── stage ──────────────────────────────────────────────────────────────

    def _compare_stage(self, a: Claim, b: Claim) -> Contradiction | IgnoredConflict | None:
        if not a.value_normalised or not b.value_normalised:
            return None
        tier_a = ClaimNormaliser.stage_tier(a.value_normalised)
        tier_b = ClaimNormaliser.stage_tier(b.value_normalised)

        if tier_a is None or tier_b is None:
            return None  # unknown tier — cannot compare
        if tier_a == tier_b:
            return None  # same tier — no contradiction

        gap = abs(tier_a - tier_b)
        # Adjacent tier difference (e.g. seed vs series-a) — minor
        if gap == 1:
            return IgnoredConflict(
                claim_a=a, claim_b=b,
                reason="STAGE_VOCABULARY",
                subtype="TEMPORAL_DRIFT",
                description=(
                    f"Stage labels {a.value_raw!r} and {b.value_raw!r} are "
                    "in adjacent tiers — likely timing or vocabulary difference."
                ),
            )
        severity = ContradictionSeverity.HIGH if gap >= 2 else ContradictionSeverity.MEDIUM
        return Contradiction(
            contradiction_id=str(uuid.uuid4())[:8],
            claim_a=a, claim_b=b,
            severity=severity,
            subtype="GENUINE_CONTRADICTION",
            description=f"Stage labels span {gap} tiers: {a.value_raw!r} vs {b.value_raw!r}.",
            recommended_action="Clarify current funding stage with founder.",
        )

    # ── employee count ────────────────────────────────────────────────────

    def _compare_employee_count(self, a: Claim, b: Claim) -> Contradiction | IgnoredConflict | None:
        # Rule 4: different terminology → no contradiction
        text_a = (a.value_raw or "").lower()
        text_b = (b.value_raw or "").lower()
        team_words = {"team", "staff", "employees", "agents", "members", "founders"}
        types_a = {w for w in team_words if w in text_a}
        types_b = {w for w in team_words if w in text_b}
        if types_a and types_b and not (types_a & types_b):
            # Different terminology — suppress
            return IgnoredConflict(
                claim_a=a, claim_b=b,
                reason="EMPLOYEE_TERMINOLOGY",
                subtype="TEMPORAL_DRIFT",
                description=(
                    "Sources use different employee terminology. "
                    "Africa staffing models distinguish core team from agents/contractors."
                ),
            )

        count_a = self._parse_int(a.value_normalised)
        count_b = self._parse_int(b.value_normalised)
        if count_a is None or count_b is None:
            return None

        larger = max(count_a, count_b)
        smaller = min(count_a, count_b)
        if smaller == 0:
            return None
        ratio = larger / smaller

        # < 100% gap or either used different terminology → ignore
        if ratio <= 2.0:
            return None

        return Contradiction(
            contradiction_id=str(uuid.uuid4())[:8],
            claim_a=a, claim_b=b,
            severity=ContradictionSeverity.MEDIUM,
            subtype="GENUINE_CONTRADICTION",
            description=f"Employee count discrepancy: {count_a} vs {count_b} (>{int((ratio-1)*100)}% gap).",
            recommended_action="Request current org chart from founder.",
        )

    # ── geography ────────────────────────────────────────────────────────

    def _compare_geography(self, a: Claim, b: Claim) -> Contradiction | IgnoredConflict | None:
        if not a.value_normalised or not b.value_normalised:
            return None
        va = a.value_normalised.lower().strip()
        vb = b.value_normalised.lower().strip()
        if va == vb:
            return None
        # Partial match (e.g. "Lagos, Nigeria" vs "Nigeria")
        if va in vb or vb in va:
            return None
        return Contradiction(
            contradiction_id=str(uuid.uuid4())[:8],
            claim_a=a, claim_b=b,
            severity=ContradictionSeverity.HIGH,
            subtype="GENUINE_CONTRADICTION",
            description=f"Geography conflict: {a.value_raw!r} vs {b.value_raw!r}.",
            recommended_action="Confirm headquarters location from incorporation documents.",
        )

    # ── categorical exact match ───────────────────────────────────────────

    def _compare_categorical_exact(
        self, a: Claim, b: Claim, ct: ClaimType
    ) -> Contradiction | IgnoredConflict | None:
        if not a.value_normalised or not b.value_normalised:
            return None
        va = a.value_normalised.lower().strip()
        vb = b.value_normalised.lower().strip()
        if va == vb:
            return None
        return Contradiction(
            contradiction_id=str(uuid.uuid4())[:8],
            claim_a=a, claim_b=b,
            severity=ContradictionSeverity.CRITICAL
            if ct == ClaimType.INVESTOR_IDENTITY
            else ContradictionSeverity.HIGH,
            subtype="GENUINE_CONTRADICTION",
            description=f"{ct.value} conflict: {a.value_raw!r} vs {b.value_raw!r}.",
            recommended_action=f"Verify {ct.value} with primary source.",
        )

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _parse_float(val: str | None) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_int(val: str | None) -> int | None:
        if val is None:
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _is_temporal_drift(a: Claim, b: Claim) -> bool:
        """Return True if staleness gap between two claims indicates different periods."""
        staleness_order = {
            StalenessT.FRESH: 0, StalenessT.AGING: 1,
            StalenessT.STALE: 2, StalenessT.VERY_STALE: 3,
            StalenessT.UNKNOWN: -1,
        }
        order_a = staleness_order.get(a.staleness, -1)
        order_b = staleness_order.get(b.staleness, -1)
        if order_a == -1 or order_b == -1:
            return False
        return abs(order_a - order_b) >= 2  # 2+ tiers apart → different time periods


# ═══════════════════════════════════════════════════════════════════════════════
# 5 — SupportEvaluator
# ═══════════════════════════════════════════════════════════════════════════════

class SupportEvaluator:
    """Identifies claim types expected for a sector that are absent from the corpus.

    In SPARSE_EVIDENCE_MODE all findings are informational — no deductions.
    In full-corpus mode CRITICAL and HIGH unsupported claims carry deductions.
    """

    # Base tier: expected for every company
    _BASE_REQUIRED: list[tuple[ClaimType, ContradictionSeverity]] = [
        (ClaimType.FOUNDING_YEAR, ContradictionSeverity.HIGH),
        (ClaimType.GEOGRAPHY, ContradictionSeverity.HIGH),
        (ClaimType.STAGE, ContradictionSeverity.MEDIUM),
        (ClaimType.FUNDING_AMOUNT, ContradictionSeverity.HIGH),
    ]

    # Sector-conditional additions
    _FINTECH_REQUIRED: list[tuple[ClaimType, ContradictionSeverity]] = [
        (ClaimType.REGULATORY_STATUS, ContradictionSeverity.CRITICAL),
    ]
    _HEALTHTECH_REQUIRED: list[tuple[ClaimType, ContradictionSeverity]] = [
        (ClaimType.REGULATORY_STATUS, ContradictionSeverity.HIGH),
    ]

    def evaluate(
        self, claims: list[Claim], sector: str
    ) -> list[UnsupportedClaim]:
        """Return unsupported claim findings for the given sector."""
        present = {c.claim_type for c in claims}
        required = list(self._BASE_REQUIRED)
        sec = sector.lower()
        if "fintech" in sec or "finance" in sec or "payment" in sec or "banking" in sec:
            required.extend(self._FINTECH_REQUIRED)
        elif "health" in sec or "medtech" in sec:
            required.extend(self._HEALTHTECH_REQUIRED)

        result: list[UnsupportedClaim] = []
        for ct, severity in required:
            if ct not in present:
                result.append(UnsupportedClaim(
                    claim_type=ct,
                    description=f"{ct.value.replace('_', ' ').title()} not found in open sources.",
                    severity=severity,
                    recommended_action=f"Request {ct.value.replace('_', ' ')} from founder.",
                ))
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# 6 — IntegrityScoreCalculator
# ═══════════════════════════════════════════════════════════════════════════════

class IntegrityScoreCalculator:
    """Computes the final integrity score, grade, depth and consistency status.

    Scoring rules per evidence-integrity-review.md Part V Revised Deduction Table:
      - Start at 100
      - Apply deductions for GENUINE contradictions (only in full corpus)
      - Apply deductions for unsupported critical claims (only in full corpus)
      - Apply deductions for stale critical claims (only in full corpus)
      - Apply corroboration bonuses
      - If sparse mode: floor at 65
      - Map score → IntegrityGrade
    """

    def calculate(
        self,
        contradictions: list[Contradiction],
        unsupported: list[UnsupportedClaim],
        stale: list[StaleClaim],
        sources: list[SourceAttribution],
        claims: list[Claim],
        sparse_mode: bool,
    ) -> tuple[float, IntegrityGrade, EvidenceDepth, ConsistencyStatus, float]:
        """Return (score, grade, depth, consistency, corroboration_bonus)."""
        score = 100.0
        corroboration_bonus = 0.0

        # ── contradiction deductions ──────────────────────────────────────
        deduction_totals: dict[str, float] = {k: 0.0 for k in _DEDUCTIONS}
        caps: dict[str, float] = {
            "CRITICAL_GENUINE": 30.0,
            "HIGH_GENUINE": 16.0,
            "MEDIUM_GENUINE": 10.0,
            "LOW_GENUINE": 4.0,
        }
        for con in contradictions:
            key = f"{con.severity.value.upper()}_GENUINE"
            cap = caps.get(key, 10.0)
            current = deduction_totals.get(key, 0.0)
            deduction = _DEDUCTIONS.get(key, 0.0)
            deduction_totals[key] = min(current + deduction, cap)

        for key, total in deduction_totals.items():
            score -= total

        # ── unsupported claim deductions (full corpus only) ───────────────
        if not sparse_mode:
            unsupported_totals: dict[str, float] = {}
            unsupported_caps = {"CRITICAL_UNSUPPORTED": 16.0, "HIGH_UNSUPPORTED": 8.0}
            for uc in unsupported:
                key = f"{uc.severity.value.upper()}_UNSUPPORTED"
                if key not in ("CRITICAL_UNSUPPORTED", "HIGH_UNSUPPORTED"):
                    continue
                cap = unsupported_caps.get(key, 8.0)
                current = unsupported_totals.get(key, 0.0)
                deduction = _DEDUCTIONS.get(key, 0.0)
                unsupported_totals[key] = min(current + deduction, cap)
            for _, total in unsupported_totals.items():
                score -= total

        # ── staleness deductions (full corpus only) ───────────────────────
        if not sparse_mode:
            stale_critical_total = 0.0
            aging_critical_total = 0.0
            unknown_high_total = 0.0
            for sc in stale:
                if sc.staleness == StalenessT.STALE:
                    stale_critical_total = min(
                        stale_critical_total + _DEDUCTIONS["STALE_CRITICAL"],
                        4.0,
                    )
                elif sc.staleness == StalenessT.AGING:
                    aging_critical_total = min(
                        aging_critical_total + _DEDUCTIONS["AGING_CRITICAL"],
                        2.0,
                    )
                elif sc.staleness == StalenessT.UNKNOWN:
                    unknown_high_total = min(
                        unknown_high_total + _DEDUCTIONS["UNKNOWN_HIGH_IMPACT"],
                        3.0,
                    )
            score -= stale_critical_total + aging_critical_total + unknown_high_total

        # ── corroboration bonuses ─────────────────────────────────────────
        corroboration_bonus = self._compute_corroboration_bonus(claims, sources)
        score += corroboration_bonus

        # ── sparse floor ──────────────────────────────────────────────────
        if sparse_mode:
            score = max(score, 65.0)

        # ── clamp ─────────────────────────────────────────────────────────
        score = max(0.0, min(100.0, score))

        grade = self._grade_from_score(score)
        depth = self._depth_from_sources(sources, len(claims))
        consistency = self._consistency_from_contradictions(contradictions)

        return score, grade, depth, consistency, corroboration_bonus

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _is_sparse(sources: list[SourceAttribution]) -> bool:
        """Return True when corpus is below the Africa sparsity threshold."""
        high_auth = sum(
            1 for s in sources if s.source_type == "high_authority_web"
        )
        return len(sources) < 5 or high_auth < 2

    @staticmethod
    def _grade_from_score(score: float) -> IntegrityGrade:
        if score >= 90:
            return IntegrityGrade.A
        if score >= 75:
            return IntegrityGrade.B
        if score >= 60:
            return IntegrityGrade.C
        if score >= 45:
            return IntegrityGrade.D
        return IntegrityGrade.F

    @staticmethod
    def _depth_from_sources(
        sources: list[SourceAttribution], claim_count: int
    ) -> EvidenceDepth:
        n = len(sources)
        if n <= 2:
            return EvidenceDepth.THIN
        if n <= 4:
            return EvidenceDepth.LIMITED
        if n <= 7:
            return EvidenceDepth.MODERATE
        if n <= 11:
            return EvidenceDepth.RICH
        return EvidenceDepth.COMPREHENSIVE

    @staticmethod
    def _consistency_from_contradictions(
        contradictions: list[Contradiction],
    ) -> ConsistencyStatus:
        n = len(contradictions)
        if n == 0:
            return ConsistencyStatus.CLEAN
        if n == 1:
            return ConsistencyStatus.MINOR_DIFFERENCES
        if n < 3:
            return ConsistencyStatus.CONFLICTS
        return ConsistencyStatus.MAJOR_CONFLICTS

    @staticmethod
    def _compute_corroboration_bonus(
        claims: list[Claim], sources: list[SourceAttribution]
    ) -> float:
        """Award bonus points for well-corroborated critical claims."""
        bonus = 0.0
        cap = 16.0  # total bonus cap

        # Group claims by type and count distinct source URLs
        by_type: dict[ClaimType, set[str]] = {}
        for c in claims:
            by_type.setdefault(c.claim_type, set()).add(c.source_url)

        # Bonus: 3+ independent sources corroborating FUNDING_AMOUNT → +5
        if len(by_type.get(ClaimType.FUNDING_AMOUNT, set())) >= 3:
            bonus += 5.0
        # Bonus: high-authority corroboration of FUNDING_AMOUNT → +5
        funding_high = sum(
            1 for c in claims
            if c.claim_type == ClaimType.FUNDING_AMOUNT
            and c.source_authority == "high_authority_web"
        )
        if funding_high >= 2:
            bonus += 5.0
        # Bonus: regulatory licence confirmed via .gov domain → +8
        gov_domains = [s for s in sources if ".gov" in s.url.lower()]
        reg_claims = [c for c in claims if c.claim_type == ClaimType.REGULATORY_STATUS]
        if gov_domains and reg_claims:
            bonus += 8.0
        # Bonus: 3+ corroborating sources for any critical claim type → +3
        critical_types = {
            ClaimType.FOUNDING_YEAR, ClaimType.GEOGRAPHY, ClaimType.INVESTOR_IDENTITY
        }
        for ct in critical_types:
            if len(by_type.get(ct, set())) >= 3:
                bonus += 3.0

        return min(bonus, cap)


# ═══════════════════════════════════════════════════════════════════════════════
# 7 — EvidenceIntegrityEngine  (top-level orchestrator)
# ═══════════════════════════════════════════════════════════════════════════════

class EvidenceIntegrityEngine:
    """Orchestrates all sub-components and returns an EvidenceIntegrityReport.

    Usage::

        engine = EvidenceIntegrityEngine(llm=some_llm_client)
        report = engine.evaluate(sources, founder, startup, sector)

    The outer ``evaluate()`` method is wrapped in a blanket try/except.
    Any unhandled exception returns a safe minimal report with
    ``extraction_notes`` set — the pipeline never crashes.
    """

    def __init__(self, llm: Any | None = None) -> None:
        self._llm = llm
        self._extractor = ClaimExtractor(llm) if llm is not None else None
        self._normaliser = ClaimNormaliser()
        self._freshness = FreshnessEvaluator()
        self._detector = ContradictionDetector()
        self._support = SupportEvaluator()
        self._scorer = IntegrityScoreCalculator()

    def evaluate(
        self,
        sources: list[SourceAttribution],
        founder: str,
        startup: str,
        sector: str = "",
    ) -> EvidenceIntegrityReport:
        """Run the full EIE pipeline and return a structured report.

        Never raises.  On failure returns a minimal safe report.
        """
        try:
            return self._evaluate_inner(sources, founder, startup, sector)
        except Exception as exc:
            _log.error("EvidenceIntegrityEngine.evaluate failed: %s", exc, exc_info=True)
            return self._safe_report(
                sources=sources,
                note=f"Engine evaluation failed: {type(exc).__name__}: {exc}",
            )

    def _evaluate_inner(
        self,
        sources: list[SourceAttribution],
        founder: str,
        startup: str,
        sector: str,
    ) -> EvidenceIntegrityReport:
        source_count = len(sources)
        high_auth_count = sum(
            1 for s in sources if s.source_type == "high_authority_web"
        )
        sparse_mode = IntegrityScoreCalculator._is_sparse(sources)

        # ── 1. Claim extraction ───────────────────────────────────────────
        extraction_notes = ""
        if self._extractor is None:
            claims_raw: list[Claim] = []
            extraction_notes = "No LLM client provided — claim extraction skipped."
        else:
            claims_raw = self._extractor.extract(sources, founder, startup)
            if not claims_raw:
                extraction_notes = (
                    "Claim extraction returned no claims — "
                    "no contradiction analysis available."
                )

        # ── 2. Normalisation ─────────────────────────────────────────────
        claims_norm = self._normaliser.normalise(claims_raw)

        # ── 3. Freshness ─────────────────────────────────────────────────
        claims_fresh = self._freshness.evaluate(claims_norm, sources)

        # ── 4. Contradiction detection ───────────────────────────────────
        contradictions, ignored = self._detector.detect(claims_fresh)

        # ── 5. Unsupported claims ─────────────────────────────────────────
        unsupported = self._support.evaluate(claims_fresh, sector)

        # ── 6. Stale claims (high-impact only) ───────────────────────────
        stale_claims = self._build_stale_list(claims_fresh)

        # ── 7. Score calculation ─────────────────────────────────────────
        score, grade, depth, consistency, bonus = self._scorer.calculate(
            contradictions=contradictions,
            unsupported=unsupported,
            stale=stale_claims,
            sources=sources,
            claims=claims_fresh,
            sparse_mode=sparse_mode,
        )

        # ── 8. Confidence delta ───────────────────────────────────────────
        confidence_delta = _CONFIDENCE_DELTA[grade]
        if sparse_mode:
            confidence_delta += _SPARSE_CONFIDENCE_DELTA

        # ── 9. Two-axis quadrant label ────────────────────────────────────
        two_axis_label = self._two_axis_label(depth, consistency)

        # ── 10. Verification checklist ────────────────────────────────────
        checklist = self._build_checklist(contradictions, unsupported, sparse_mode)

        # ── 11. Plain-English summary ─────────────────────────────────────
        summary = self._build_summary(
            score, grade, depth, consistency, contradictions,
            unsupported, sparse_mode, source_count
        )

        return EvidenceIntegrityReport(
            integrity_score=round(score, 1),
            integrity_grade=grade,
            evidence_depth=depth,
            consistency_status=consistency,
            sparse_mode=sparse_mode,
            claim_count=len(claims_fresh),
            source_count=source_count,
            high_authority_count=high_auth_count,
            contradictions=contradictions,
            ignored_conflicts=ignored,
            unsupported_claims=unsupported,
            stale_claims=stale_claims,
            corroboration_bonus=round(bonus, 1),
            integrity_summary=summary,
            extraction_notes=extraction_notes,
            confidence_adjusted=max(0.0, min(1.0, 0.75 + confidence_delta)),
            confidence_delta=round(confidence_delta, 3),
            two_axis_label=two_axis_label,
            verification_checklist=checklist,
            generated_at=datetime.now(timezone.utc),
        )

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _build_stale_list(claims: list[Claim]) -> list[StaleClaim]:
        """Return StaleClaim objects for high-impact claims that are stale."""
        high_impact = {
            ClaimType.FUNDING_AMOUNT, ClaimType.FOUNDING_YEAR,
            ClaimType.INVESTOR_IDENTITY, ClaimType.REGULATORY_STATUS,
            ClaimType.REVENUE,
        }
        stale_staleness = {StalenessT.STALE, StalenessT.VERY_STALE, StalenessT.AGING}
        result: list[StaleClaim] = []
        for c in claims:
            if c.claim_type in high_impact and c.staleness in stale_staleness:
                result.append(StaleClaim(
                    claim=c,
                    staleness=c.staleness,
                    source_url=c.source_url,
                    recommended_action=f"Verify current {c.claim_type.value.replace('_', ' ')} with founder.",
                ))
        return result

    @staticmethod
    def _two_axis_label(depth: EvidenceDepth, consistency: ConsistencyStatus) -> str:
        """Map (depth, consistency) → quadrant label A/B/C/D.

        Per evidence-integrity-review.md Part V The Two-Axis Trust Model:
          B = High integrity + High confidence (RICH/COMPREHENSIVE + CLEAN/MINOR)
          A = High integrity + Low confidence  (THIN/LIMITED + CLEAN/MINOR)
          D = Low integrity  + High confidence (RICH/COMPREHENSIVE + CONFLICTS/MAJOR)
          C = Low integrity  + Low confidence  (THIN/LIMITED + CONFLICTS/MAJOR)
        """
        high_depth = depth in (EvidenceDepth.RICH, EvidenceDepth.COMPREHENSIVE)
        high_consistency = consistency in (ConsistencyStatus.CLEAN, ConsistencyStatus.MINOR_DIFFERENCES)

        if high_depth and high_consistency:
            return "B"
        if not high_depth and high_consistency:
            return "A"
        if high_depth and not high_consistency:
            return "D"
        return "C"

    @staticmethod
    def _build_checklist(
        contradictions: list[Contradiction],
        unsupported: list[UnsupportedClaim],
        sparse_mode: bool,
    ) -> list[str]:
        items: list[str] = []
        for i, c in enumerate(contradictions, 1):
            items.append(f"[C{i}] Resolve conflict: {c.description[:120]}")
        if sparse_mode:
            items.append("Collect primary data — limited OSINT available for this company.")
        for i, u in enumerate(unsupported, 1):
            items.append(f"[U{i}] {u.recommended_action}")
        return items

    @staticmethod
    def _build_summary(
        score: float,
        grade: IntegrityGrade,
        depth: EvidenceDepth,
        consistency: ConsistencyStatus,
        contradictions: list[Contradiction],
        unsupported: list[UnsupportedClaim],
        sparse_mode: bool,
        source_count: int,
    ) -> str:
        parts: list[str] = []
        if sparse_mode:
            parts.append(
                "SPARSE EVIDENCE CORPUS — Limited OSINT available for this company. "
                "Primary data collection recommended before IC."
            )
        depth_label = depth.value.title()
        parts.append(f"{depth_label} evidence base ({source_count} source(s) reviewed).")
        if not contradictions:
            parts.append("No material conflicts detected.")
        else:
            n = len(contradictions)
            parts.append(
                f"{n} material conflict(s) detected — "
                "recommend verification before IC presentation."
            )
        if unsupported and not sparse_mode:
            n = len(unsupported)
            parts.append(f"{n} expected claim type(s) not found in open sources.")
        return " ".join(parts)

    @staticmethod
    def _safe_report(
        sources: list[SourceAttribution],
        note: str,
    ) -> EvidenceIntegrityReport:
        """Return a minimal safe report used when the engine fails."""
        sparse_mode = IntegrityScoreCalculator._is_sparse(sources)
        return EvidenceIntegrityReport(
            integrity_score=100.0,
            integrity_grade=IntegrityGrade.A,
            evidence_depth=EvidenceDepth.THIN,
            consistency_status=ConsistencyStatus.CLEAN,
            sparse_mode=sparse_mode,
            source_count=len(sources),
            high_authority_count=sum(
                1 for s in sources if s.source_type == "high_authority_web"
            ),
            extraction_notes=note,
            generated_at=datetime.now(timezone.utc),
        )
