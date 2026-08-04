"""SignalsOrchestrator — derive Signals for a Case from core OS outputs.

Phase 5C: Lightweight wrapper that pulls EvidenceIntegrityReport and
TrustGraph from a Case and uses the rule-based engine in
kulima.signals.rules to generate a list of Signal objects.

FLEX, Ask IC, and UI remain unchanged.
"""

from __future__ import annotations



from kulima.core.cases.models import Case
from kulima.models import EvidenceIntegrityReport, TrustGraph
from kulima.signals.models import Signal
from kulima.signals.rules import generate_signals_from_case
from kulima.signals.signals_summary import highest_priority_signals


class SignalsOrchestrator:
    """Generate SIGNALS for a given Case using deterministic rules.

    Public API:
        orchestrator = SignalsOrchestrator()
        signals = orchestrator.generate(case)

    The resulting signals are also stored in case.payload["signals"] as a
    list of serialised dicts for future persistence.
    """

    def generate(self, case: Case, *, sort: bool = True) -> list[Signal]:
        ei: EvidenceIntegrityReport | None = case.evidence_integrity
        graph: TrustGraph | None = case.trust_graph

        signals = generate_signals_from_case(case, ei, graph)
        if sort:
            signals = highest_priority_signals(signals, limit=None)

        # Store a serialised form in the Case payload to make this easy to
        # persist alongside other vertical-specific data.
        case.payload["signals"] = [s.model_dump(mode="json") for s in signals]
        return signals
