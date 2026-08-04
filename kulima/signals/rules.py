"""Rule-based SIGNALS generation from Evidence Integrity and Trust Graph.

Phase 5C: Deterministic, LLM-free rules that derive Signal objects from
existing Kulima OS core outputs for a given Case.
"""

from __future__ import annotations

from typing import List

from kulima.core.cases.models import Case
from kulima.models import EvidenceIntegrityReport, TrustGraph
from kulima.signals.models import (
    Signal,
    SignalCategory,
    SignalLevel,
)


def _governance_signals(case: Case, ei: EvidenceIntegrityReport | None) -> List[Signal]:
    signals: List[Signal] = []
    if ei is None:
        return signals

    # HIGH Governance Risk when contradictions exceed threshold.
    # Threshold: 2 or more material contradictions.
    if len(ei.contradictions) >= 2:
        evid_refs = [f"C{i+1}" for i in range(min(3, len(ei.contradictions)))]
        signals.append(
            Signal(
                id=f"{case.id}-gov-contradictions",
                case_id=case.id,
                level=SignalLevel.HIGH,
                category=SignalCategory.GOVERNANCE,
                title="High governance risk: conflicting evidence",
                description=(
                    "Multiple material conflicts detected in available evidence. "
                    "Key facts about the case are not consistently reported "
                    "across sources."
                ),
                direction="risk",
                evidence_refs=evid_refs,
                evidence_summary=(
                    f"{len(ei.contradictions)} contradictions identified in the "
                    "Evidence Integrity analysis."
                ),
                recommended_action=(
                    "Resolve the top conflicts before major funding or "
                    "program decisions; escalate unresolved items to governance "
                    "and risk committees."
                ),
                time_horizon="short-term",
                confidence=0.8,
            )
        )

    return signals


def _impact_signals(case: Case, ei: EvidenceIntegrityReport | None) -> List[Signal]:
    signals: List[Signal] = []
    if ei is None:
        return signals

    # HIGH Impact Risk when unsupported claims exceed threshold.
    # Threshold: 2 or more unsupported high-impact claims.
    if len(ei.unsupported_claims) >= 2 and not ei.sparse_mode:
        evid_refs = [f"U{i+1}" for i in range(min(3, len(ei.unsupported_claims)))]
        signals.append(
            Signal(
                id=f"{case.id}-impact-unsupported",
                case_id=case.id,
                level=SignalLevel.HIGH,
                category=SignalCategory.IMPACT,
                title="High impact risk: weak outcome evidence",
                description=(
                    "Several high-impact outcome or reach claims are not "
                    "supported by the current evidence corpus."
                ),
                direction="risk",
                evidence_refs=evid_refs,
                evidence_summary=(
                    f"{len(ei.unsupported_claims)} expected fact categories "
                    "were not found in open evidence."
                ),
                recommended_action=(
                    "Request additional monitoring and evaluation data or "
                    "independent verification before claiming results."
                ),
                time_horizon="medium-term",
                confidence=0.75,
            )
        )

    return signals


def _trust_signals(case: Case, graph: TrustGraph | None) -> List[Signal]:
    signals: List[Signal] = []
    if graph is None:
        return signals

    # MEDIUM Trust Risk when trust score is below threshold.
    if graph.trust_score < 50:
        signals.append(
            Signal(
                id=f"{case.id}-trust-low",
                case_id=case.id,
                level=SignalLevel.MEDIUM,
                category=SignalCategory.GOVERNANCE,
                title="Medium trust risk: thin ecosystem footprint",
                description=(
                    "Trust graph shows a thin or weak ecosystem footprint for "
                    "this case. Connections to trusted institutions and "
                    "investors are limited."
                ),
                direction="risk",
                evidence_refs=["TRUST_GRAPH"],
                evidence_summary=(
                    f"Trust score {graph.trust_score:.0f}/100 with "
                    f"{len(graph.nodes)} nodes and {len(graph.edges)} relations."
                ),
                recommended_action=(
                    "Strengthen relationships with reputable partners, "
                    "auditors, or institutional anchors before scaling "
                    "commitments."
                ),
                time_horizon="medium-term",
                confidence=0.7,
            )
        )

    # LOW Opportunity when trust graph shows strong partner network.
    # Heuristic: 3+ partner-type nodes with any edges and trust_score >= 60.
    partner_types = {"investor", "institution", "company", "university", "foundation", "government"}
    partner_ids = {
        n.id for n in graph.nodes
        if getattr(n, "node_type", "").lower() in partner_types
    }
    connected_partner_ids: set[str] = set()
    for e in graph.edges:
        if e.source in partner_ids or e.target in partner_ids:
            connected_partner_ids.add(e.source)
            connected_partner_ids.add(e.target)

    partner_count = len(partner_ids & connected_partner_ids)
    if partner_count >= 3 and graph.trust_score >= 60:
        signals.append(
            Signal(
                id=f"{case.id}-opportunity-network",
                case_id=case.id,
                level=SignalLevel.LOW,
                category=SignalCategory.IMPACT,
                title="Opportunity: strong partner network",
                description=(
                    "Trust graph indicates a strong network of partners and "
                    "institutions that could support additional pilots or "
                    "scale-up."
                ),
                direction="opportunity",
                evidence_refs=["TRUST_GRAPH"],
                evidence_summary=(
                    f"Trust graph includes {partner_count} connected partner-"
                    "type entities with trust score "
                    f"{graph.trust_score:.0f}/100."
                ),
                recommended_action=(
                    "Explore co-designed interventions or expansions that "
                    "leverage the existing partner network."
                ),
                time_horizon="medium-term",
                confidence=0.7,
            )
        )

    return signals


def generate_signals_from_case(
    case: Case,
    ei: EvidenceIntegrityReport | None,
    graph: TrustGraph | None,
) -> List[Signal]:
    """Generate deterministic Signals from a Case + core OS outputs.

    This function is LLM-free and purely rule-based for Phase 5C.
    """

    signals: List[Signal] = []
    signals.extend(_governance_signals(case, ei))
    signals.extend(_impact_signals(case, ei))
    signals.extend(_trust_signals(case, graph))
    return signals
