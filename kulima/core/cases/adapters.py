"""Adapters between FLEX InvestmentBrief and generic Kulima OS Case.

Phase 4A: provide lossless conversions without changing FLEX behaviour.

- from_investment_brief: wraps an InvestmentBrief in a Case envelope.
- to_investment_brief: reconstructs the InvestmentBrief from a Case
  previously built by from_investment_brief.

These helpers do not touch the database or orchestrator public APIs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from kulima.core.cases.models import Case, CaseSubject, CaseType
from kulima.models import InvestmentBrief


def from_investment_brief(
    brief: InvestmentBrief,
    *,
    case_id: str,
    created_at: datetime | None = None,
    created_by: str | None = None,
) -> Case:
    """Wrap an InvestmentBrief in a Case envelope.

    The conversion is intentionally lossless: the full InvestmentBrief
    JSON representation is stored in Case.payload["investment_brief"].
    All existing InvestmentBrief fields are preserved.
    """

    subject = CaseSubject(
        id=None,
        kind="startup",
        name=brief.startup_name,
        secondary_name=brief.founder_name,
        region=brief.geography or None,
        sector=brief.sector or None,
    )

    payload: dict[str, Any] = {
        "investment_brief": brief.model_dump(mode="json"),
    }

    return Case(
        id=case_id,
        case_type=CaseType.INVESTMENT,
        subject=subject,
        created_at=created_at or datetime.utcnow(),
        created_by=created_by,
        sources=list(brief.sources),
        evidence_integrity=brief.evidence_integrity,
        trust_graph=brief.trust_graph,
        document_ids=[],
        payload=payload,
    )


def to_investment_brief(case: Case) -> InvestmentBrief:
    """Reconstruct an InvestmentBrief from a Case created by from_investment_brief.

    This is a lossless round-trip provided that the Case was created by
    from_investment_brief and still contains a serialised
    InvestmentBrief under payload["investment_brief"].
    """

    if case.case_type != CaseType.INVESTMENT:
        raise ValueError("Case is not of type INVESTMENT and cannot be converted to InvestmentBrief")

    data = case.payload.get("investment_brief")
    if not isinstance(data, dict):
        raise ValueError("Case payload does not contain an 'investment_brief' object")

    brief = InvestmentBrief.model_validate(data)

    # Re-attach shared evidence surfaces from the Case, in case they were
    # updated independently of the payload.
    brief.sources = list(case.sources)
    brief.evidence_integrity = case.evidence_integrity
    brief.trust_graph = case.trust_graph

    return brief
