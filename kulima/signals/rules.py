"""Rule-based SIGNALS generation from Evidence Integrity and Trust Graph.

Phase 5C: Deterministic, LLM-free rules that derive Signal objects from
existing Kulima FLEX core outputs for a given Case.
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


def _gather_evidence_corpus(case: Case) -> tuple[list[dict], list[dict], str]:
    """Gather doc sources, web/tavily sources, and aggregate text for analysis."""
    doc_sources = []
    web_sources = []
    all_text_parts = []

    # 1. Sources from case
    for s in case.sources:
        text = f"{s.title} {s.snippet}".strip()
        all_text_parts.append(text)
        is_doc = (
            getattr(s, "source_type", "") == "document"
            or str(s.url).startswith("document://")
            or "upload" in str(s.url).lower()
        )
        record = {
            "title": s.title,
            "url": s.url,
            "snippet": s.snippet,
            "confidence": getattr(s, "confidence_score", 0.7),
            "ref": f"DOC:{s.title}" if is_doc else f"TAVILY:{s.title[:30]}",
            "is_doc": is_doc,
        }
        if is_doc:
            doc_sources.append(record)
        else:
            web_sources.append(record)

    # 2. Uploaded evidence from investment brief payload
    brief_data = case.payload.get("investment_brief") or {}
    for doc in brief_data.get("uploaded_evidence", []):
        filename = doc.get("filename", "Uploaded Document")
        summary = doc.get("raw_summary", "")
        items = " ".join(doc.get("evidence_items", []))
        signals_gen = " ".join(doc.get("signals_generated", []))
        content = f"{filename} {summary} {items} {signals_gen}"
        all_text_parts.append(content)
        doc_sources.append({
            "title": filename,
            "url": f"document://{doc.get('id', filename)}",
            "snippet": summary or items or filename,
            "confidence": float(doc.get("trust_breakdown", {}).get("final_trust_score", 75)) / 100.0,
            "ref": f"DOC:{filename}",
            "is_doc": True,
        })

    # 3. Assessment narratives from brief
    for k in ("executive_summary", "founder_assessment", "startup_assessment", "market_assessment", "risk_assessment"):
        val = brief_data.get(k)
        if val:
            all_text_parts.append(str(val))

    full_corpus = " ".join(all_text_parts).lower()
    return doc_sources, web_sources, full_corpus


def _climate_signals(case: Case) -> List[Signal]:
    """Extract Climate Signals from uploaded documents and Tavily OSINT."""
    doc_sources, web_sources, corpus = _gather_evidence_corpus(case)
    signals: List[Signal] = []

    climate_terms = ("climate", "carbon", "emissions", "solar", "renewable", "clean energy", "weather", "drought", "flooding", "irrigation", "clean cooking", "adaptation", "resilience")
    found_doc = next((d for d in doc_sources if any(t in d["snippet"].lower() or t in d["title"].lower() for t in climate_terms)), None)
    found_web = next((w for w in web_sources if any(t in w["snippet"].lower() or t in w["title"].lower() for t in climate_terms)), None)

    if found_doc or found_web or any(t in corpus for t in climate_terms):
        primary_ref = found_doc["ref"] if found_doc else (found_web["ref"] if found_web else "EVIDENCE_CORPUS")
        source_label = "uploaded primary document" if found_doc else "Tavily OSINT intelligence"
        snippet = (found_doc or found_web or {}).get("snippet", "")
        
        # Opportunity: Clean tech / adaptation
        signals.append(
            Signal(
                id=f"{case.id}-climate-opportunity",
                case_id=case.id,
                level=SignalLevel.HIGH if found_doc else SignalLevel.MEDIUM,
                category=SignalCategory.CLIMATE,
                title="Climate Signal: Clean energy & climate resilience verified",
                description=f"Evidence indicates active climate mitigation or adaptation mechanisms documented via {source_label}.",
                direction="opportunity",
                evidence_refs=[primary_ref],
                evidence_summary=f"Identified climate adaptation markers in {source_label}. {snippet[:140]}",
                recommended_action="Validate carbon offset potential and energy transition compliance metrics.",
                time_horizon="medium-term",
                confidence=0.85 if found_doc else 0.72,
                metadata={"domain": "Climate Signals", "source_type": "document" if found_doc else "tavily"}
            )
        )
    else:
        # Baseline climate risk for physical/agricultural operations
        signals.append(
            Signal(
                id=f"{case.id}-climate-risk",
                case_id=case.id,
                level=SignalLevel.MEDIUM,
                category=SignalCategory.CLIMATE,
                title="Climate Signal: Regional climate volatility exposure",
                description="Macro-operating corridor is subject to seasonal climate shifts and rainfall variability.",
                direction="risk",
                evidence_refs=["MACRO_CORRIDOR"],
                evidence_summary="Operating region exhibits weather exposure that requires weather-index mitigation.",
                recommended_action="Review operational contingency plans for weather extremes and seasonal grid stress.",
                time_horizon="short-term",
                confidence=0.68,
                metadata={"domain": "Climate Signals", "source_type": "macro"}
            )
        )
    return signals


def _environmental_signals(case: Case) -> List[Signal]:
    """Extract Environmental Signals from uploaded documents and Tavily OSINT."""
    doc_sources, web_sources, corpus = _gather_evidence_corpus(case)
    signals: List[Signal] = []

    env_terms = ("environment", "environmental", "waste", "recycling", "circular", "soil", "water", "biodiversity", "conservation", "pollution", "plastic", "deforestation")
    found_doc = next((d for d in doc_sources if any(t in d["snippet"].lower() or t in d["title"].lower() for t in env_terms)), None)
    found_web = next((w for w in web_sources if any(t in w["snippet"].lower() or t in w["title"].lower() for t in env_terms)), None)

    if found_doc or found_web or any(t in corpus for t in env_terms):
        primary_ref = found_doc["ref"] if found_doc else (found_web["ref"] if found_web else "EVIDENCE_CORPUS")
        source_label = "uploaded primary document" if found_doc else "Tavily OSINT intelligence"
        signals.append(
            Signal(
                id=f"{case.id}-env-circularity",
                case_id=case.id,
                level=SignalLevel.MEDIUM,
                category=SignalCategory.ENVIRONMENTAL,
                title="Environmental Signal: Resource stewardship & waste efficiency",
                description=f"Environmental sustainability metrics and resource preservation practices identified in {source_label}.",
                direction="opportunity",
                evidence_refs=[primary_ref],
                evidence_summary=f"Documented environmental safeguards and waste mitigation measures via {source_label}.",
                recommended_action="Confirm compliance with local Environmental Protection Agency guidelines and audits.",
                time_horizon="medium-term",
                confidence=0.80 if found_doc else 0.70,
                metadata={"domain": "Environmental Signals", "source_type": "document" if found_doc else "tavily"}
            )
        )
    else:
        signals.append(
            Signal(
                id=f"{case.id}-env-safeguards",
                case_id=case.id,
                level=SignalLevel.LOW,
                category=SignalCategory.ENVIRONMENTAL,
                title="Environmental Signal: Standard environmental compliance footprint",
                description="Entity operates within standard environmental thresholds with minimal direct emissions footprint.",
                direction="neutral",
                evidence_refs=["COMPLIANCE_STANDARDS"],
                evidence_summary="No acute environmental non-compliance flags detected in evidence corpus.",
                recommended_action="Maintain environmental compliance documentation for future regulatory review.",
                time_horizon="long-term",
                confidence=0.65,
                metadata={"domain": "Environmental Signals", "source_type": "standard"}
            )
        )
    return signals


def _tourism_signals(case: Case) -> List[Signal]:
    """Extract Tourism Signals from uploaded documents and Tavily OSINT."""
    doc_sources, web_sources, corpus = _gather_evidence_corpus(case)
    signals: List[Signal] = []

    tourism_terms = ("tourism", "tourist", "travel", "hospitality", "hotel", "lodge", "safari", "visitor", "booking", "destination", "cultural", "heritage", "attraction", "passenger")
    found_doc = next((d for d in doc_sources if any(t in d["snippet"].lower() or t in d["title"].lower() for t in tourism_terms)), None)
    found_web = next((w for w in web_sources if any(t in w["snippet"].lower() or t in w["title"].lower() for t in tourism_terms)), None)

    if found_doc or found_web or any(t in corpus for t in tourism_terms):
        primary_ref = found_doc["ref"] if found_doc else (found_web["ref"] if found_web else "EVIDENCE_CORPUS")
        source_label = "uploaded primary document" if found_doc else "Tavily OSINT intelligence"
        signals.append(
            Signal(
                id=f"{case.id}-tourism-ecosystem",
                case_id=case.id,
                level=SignalLevel.MEDIUM,
                category=SignalCategory.TOURISM,
                title="Tourism Signal: Travel & hospitality ecosystem alignment",
                description=f"Value proposition interfaces with tourism, traveler logistics, or regional hospitality channels in {source_label}.",
                direction="opportunity",
                evidence_refs=[primary_ref],
                evidence_summary=f"Ecosystem synergies with tourism and hospitality economy identified in {source_label}.",
                recommended_action="Explore partnerships with tourism boards, hotel networks, and regional travel operators.",
                time_horizon="medium-term",
                confidence=0.78 if found_doc else 0.69,
                metadata={"domain": "Tourism Signals", "source_type": "document" if found_doc else "tavily"}
            )
        )
    else:
        signals.append(
            Signal(
                id=f"{case.id}-tourism-indirect",
                case_id=case.id,
                level=SignalLevel.LOW,
                category=SignalCategory.TOURISM,
                title="Tourism Signal: Regional infrastructure & mobility connectivity",
                description="Indirect linkage to regional transport corridors and commercial mobility infrastructure.",
                direction="neutral",
                evidence_refs=["MOBILITY_CORRIDOR"],
                evidence_summary="Assessment of regional infrastructure supporting visitor mobility and trade transit.",
                recommended_action="Monitor cross-border transport rail and corridor development for logistics advantages.",
                time_horizon="long-term",
                confidence=0.60,
                metadata={"domain": "Tourism Signals", "source_type": "macro"}
            )
        )
    return signals


def _community_impact_signals(case: Case) -> List[Signal]:
    """Extract Community Impact Signals from uploaded documents and Tavily OSINT."""
    doc_sources, web_sources, corpus = _gather_evidence_corpus(case)
    signals: List[Signal] = []

    impact_terms = ("community", "beneficiar", "smallholder", "farmer", "livelihood", "women", "female", "youth", "employment", "jobs", "cooperative", "rural", "social", "poverty", "food security")
    found_doc = next((d for d in doc_sources if any(t in d["snippet"].lower() or t in d["title"].lower() for t in impact_terms)), None)
    found_web = next((w for w in web_sources if any(t in w["snippet"].lower() or t in w["title"].lower() for t in impact_terms)), None)

    if found_doc or found_web or any(t in corpus for t in impact_terms):
        primary_ref = found_doc["ref"] if found_doc else (found_web["ref"] if found_web else "EVIDENCE_CORPUS")
        source_label = "uploaded primary document" if found_doc else "Tavily OSINT intelligence"
        signals.append(
            Signal(
                id=f"{case.id}-community-livelihoods",
                case_id=case.id,
                level=SignalLevel.HIGH if found_doc else SignalLevel.MEDIUM,
                category=SignalCategory.COMMUNITY_IMPACT,
                title="Community Impact Signal: Livelihood uplift & local job creation",
                description=f"Significant grassroots community reach and income improvements verified via {source_label}.",
                direction="opportunity",
                evidence_refs=[primary_ref],
                evidence_summary=f"Demonstrated beneficiary impact, smallholder inclusion, or job creation in {source_label}.",
                recommended_action="Implement standardised M&E outcome indicator tracking (e.g. IRIS+/SDG metrics).",
                time_horizon="short-term",
                confidence=0.88 if found_doc else 0.76,
                metadata={"domain": "Community Impact Signals", "source_type": "document" if found_doc else "tavily"}
            )
        )
    else:
        signals.append(
            Signal(
                id=f"{case.id}-community-inclusion",
                case_id=case.id,
                level=SignalLevel.MEDIUM,
                category=SignalCategory.COMMUNITY_IMPACT,
                title="Community Impact Signal: Stakeholder engagement & social baseline",
                description="Community engagement mechanisms require formal baseline surveys to verify reach.",
                direction="risk",
                evidence_refs=["MEAL_FRAMEWORK"],
                evidence_summary="Beneficiary metrics require third-party corroboration to validate claimed social reach.",
                recommended_action="Deploy beneficiary feedback survey to corroborate local community reception.",
                time_horizon="medium-term",
                confidence=0.70,
                metadata={"domain": "Community Impact Signals", "source_type": "meal"}
            )
        )
    return signals


def _program_delivery_signals(case: Case) -> List[Signal]:
    """Extract Programme Delivery Signals (PRIMARY customer domain for V1).

    NGOs and development programmes are decided on whether they actually
    deliver: workplans, milestones, logframe / results-framework targets,
    theory of change and progress reporting. Uploaded documents are the
    authoritative source (Source A); Tavily OSINT only corroborates.
    """
    doc_sources, web_sources, corpus = _gather_evidence_corpus(case)
    signals: List[Signal] = []

    delivery_terms = (
        "workplan", "work plan", "milestone", "logframe", "logical framework",
        "results framework", "theory of change", "indicator", "target",
        "baseline", "endline", "deliverable", "implementation schedule",
        "progress report", "activity", "output", "outcome", "disbursement",
    )
    found_doc = next((d for d in doc_sources if any(t in d["snippet"].lower() or t in d["title"].lower() for t in delivery_terms)), None)
    found_web = next((w for w in web_sources if any(t in w["snippet"].lower() or t in w["title"].lower() for t in delivery_terms)), None)

    if found_doc or found_web:
        primary_ref = found_doc["ref"] if found_doc else found_web["ref"]
        source_label = "uploaded primary document" if found_doc else "Tavily OSINT intelligence"
        matched = [t for t in delivery_terms if t in (found_doc or found_web)["snippet"].lower()]
        signals.append(
            Signal(
                id=f"{case.id}-delivery-progress",
                case_id=case.id,
                level=SignalLevel.HIGH if found_doc else SignalLevel.MEDIUM,
                category=SignalCategory.PROGRAM_DELIVERY,
                title="Programme Delivery Signal: documented workplan, milestones and results",
                description=(
                    f"Delivery architecture (milestones, targets, results indicators) is documented in {source_label}."
                ),
                direction="opportunity",
                evidence_refs=[primary_ref],
                evidence_summary=(
                    f"Delivery markers detected: {', '.join(matched[:5]) or 'milestones / targets'} in {source_label}."
                ),
                recommended_action=(
                    "Verify reported milestone achievement against the logframe targets and the underlying field data."
                ),
                time_horizon="short-term",
                confidence=0.88 if found_doc else 0.74,
                metadata={"domain": "Programme Delivery", "source_type": "document" if found_doc else "tavily"},
            )
        )
    else:
        signals.append(
            Signal(
                id=f"{case.id}-delivery-evidence-gap",
                case_id=case.id,
                level=SignalLevel.MEDIUM,
                category=SignalCategory.PROGRAM_DELIVERY,
                title="Programme Delivery Signal: no workplan or milestone evidence yet",
                description=(
                    "No workplan, milestone, logframe or results-framework evidence was detected in the "
                    "corpus. Delivery capacity cannot be confirmed from the documents supplied."
                ),
                direction="risk",
                evidence_refs=["EVIDENCE_CORPUS"],
                evidence_summary=(
                    f"No delivery markers found across {len(doc_sources)} document(s) and {len(web_sources)} external source(s)."
                ),
                recommended_action=(
                    "Request the current workplan, logframe / results framework and the latest progress report before deciding."
                ),
                time_horizon="immediate",
                confidence=0.68,
                metadata={"domain": "Programme Delivery", "source_type": "gap"},
            )
        )
    return signals


def _market_signals(case: Case) -> List[Signal]:
    """Extract Market Signals from evidence corpus."""
    doc_sources, web_sources, corpus = _gather_evidence_corpus(case)
    signals: List[Signal] = []
    
    market_terms = ("market size", "tam", "sam", "som", "growth rate", "cagr", "customer adoption", "expansion", "traction")
    found = next((s for s in doc_sources + web_sources if any(t in s["snippet"].lower() for t in market_terms)), None)
    # Source-A first: prefer document evidence for the citation.
    doc_found = next((s for s in doc_sources if any(t in s["snippet"].lower() for t in market_terms)), None)
    if doc_found:
        found = doc_found
    ref = found["ref"] if found else "MARKET_INTELLIGENCE"

    # Evidence-grounded signal generation: when NO market evidence exists in
    # the corpus, the signal must reflect the gap — not assert fabricated
    # "tailwinds". Unsupported optimism distorts the Market domain score.
    if found:
        signals.append(
            Signal(
                id=f"{case.id}-market-expansion",
                case_id=case.id,
                level=SignalLevel.HIGH if doc_found else SignalLevel.MEDIUM,
                category=SignalCategory.MARKET,
                title="Market Signal: Commercial market runway & demand velocity",
                description="Addressable market demonstrates favorable structural tailwinds and commercial uptake.",
                direction="opportunity",
                evidence_refs=[ref],
                evidence_summary=f"Strong customer demand and corridor market dynamics corroborated by {ref}.",
                recommended_action="Accelerate sales distribution through existing anchor partnership channels.",
                time_horizon="short-term",
                confidence=0.82 if doc_found else 0.70,
                metadata={"domain": "Market Signals", "source_type": "document" if doc_found else "market"}
            )
        )
    else:
        signals.append(
            Signal(
                id=f"{case.id}-market-gap",
                case_id=case.id,
                level=SignalLevel.MEDIUM,
                category=SignalCategory.MARKET,
                title="Market Signal: Market sizing not yet evidenced",
                description="No market sizing, traction, or demand evidence found in the corpus — flagged as a diligence gap.",
                direction="risk",
                evidence_refs=[ref],
                evidence_summary="No market sizing or traction markers detected in uploaded documents or external research.",
                recommended_action="Request market sizing and customer validation evidence from the entity.",
                time_horizon="short-term",
                confidence=0.68,
                metadata={"domain": "Market Signals", "source_type": "gap"}
            )
        )
    return signals


def _funding_signals(case: Case, ei: EvidenceIntegrityReport | None) -> List[Signal]:
    """Extract Funding Signals from evidence corpus."""
    doc_sources, web_sources, corpus = _gather_evidence_corpus(case)
    signals: List[Signal] = []

    funding_terms = ("seed", "series a", "funding round", "investor", "grant", "runway", "capital", "debt", "valuation", "equity")
    doc_found = next((s for s in doc_sources if any(t in s["snippet"].lower() for t in funding_terms)), None)
    found = doc_found or next((s for s in web_sources if any(t in s["snippet"].lower() for t in funding_terms)), None)
    ref = found["ref"] if found else "FINANCIAL_DISCLOSURES"

    # Evidence-grounded signal generation: no funding evidence in the corpus →
    # neutral gap signal, never a fabricated opportunity claim.
    if found:
        signals.append(
            Signal(
                id=f"{case.id}-funding-runway",
                case_id=case.id,
                level=SignalLevel.HIGH if doc_found else SignalLevel.MEDIUM,
                category=SignalCategory.FUNDING,
                title="Funding Signal: Capital structure & runway sustainability",
                description="Historical capitalization and ongoing fundraising requirements mapped from evidence base.",
                direction="opportunity" if doc_found else "neutral",
                evidence_refs=[ref],
                evidence_summary=f"Capitalization history and investor syndicate commitments documented in {ref}.",
                recommended_action="Ensure minimum 18-month cash runway cushion post-disbursement.",
                time_horizon="short-term",
                confidence=0.80 if doc_found else 0.68,
                metadata={"domain": "Funding Signals", "source_type": "document" if doc_found else "funding"}
            )
        )
    else:
        signals.append(
            Signal(
                id=f"{case.id}-funding-gap",
                case_id=case.id,
                level=SignalLevel.MEDIUM,
                category=SignalCategory.FUNDING,
                title="Funding Signal: Capital structure not yet evidenced",
                description="No funding, grant, or capital-structure evidence found in the corpus — flagged as a diligence gap.",
                direction="risk",
                evidence_refs=[ref],
                evidence_summary="No funding or capitalization markers detected in uploaded documents or external research.",
                recommended_action="Request funding history and capital plan documentation from the entity.",
                time_horizon="short-term",
                confidence=0.66,
                metadata={"domain": "Funding Signals", "source_type": "gap"}
            )
        )
    return signals


def _competitive_signals(case: Case) -> List[Signal]:
    """Extract Competitive Signals from evidence corpus."""
    doc_sources, web_sources, corpus = _gather_evidence_corpus(case)
    signals: List[Signal] = []

    comp_terms = ("competitor", "moat", "competitive", "barrier", "pricing power", "incumbent", "differentiation")
    found = next((s for s in doc_sources + web_sources if any(t in s["snippet"].lower() for t in comp_terms)), None)
    ref = found["ref"] if found else "COMPETITIVE_LANDSCAPE"

    signals.append(
        Signal(
            id=f"{case.id}-competitive-moat",
            case_id=case.id,
            level=SignalLevel.MEDIUM,
            category=SignalCategory.COMPETITIVE,
            title="Competitive Signal: Moat defensibility & proprietary advantage",
            description="Proprietary technology, vendor lock-in, and local trust networks create defensive barriers.",
            direction="opportunity",
            evidence_refs=[ref],
            evidence_summary=f"Competitive advantage supported by local operating execution and distributor networks ({ref}).",
            recommended_action="Reinforce intellectual property filings and exclusive distributor contracts.",
            time_horizon="medium-term",
            confidence=0.75,
            metadata={"domain": "Competitive Signals", "source_type": "competitive"}
        )
    )
    return signals


def _opportunity_signals(case: Case) -> List[Signal]:
    """Extract Opportunity Signals (upside / expansion headroom) from evidence corpus."""
    doc_sources, web_sources, corpus = _gather_evidence_corpus(case)
    signals: List[Signal] = []

    opportunity_terms = ("opportunity", "expansion", "unmet demand", "under-served", "underserved", "untapped", "growth potential", "partnership", "scale-up", "scale up", "pilot", "new market")
    doc_found = next((s for s in doc_sources if any(t in s["snippet"].lower() or t in s["title"].lower() for t in opportunity_terms)), None)
    found = doc_found or next((s for s in web_sources if any(t in s["snippet"].lower() or t in s["title"].lower() for t in opportunity_terms)), None)
    ref = found["ref"] if found else "OPPORTUNITY_SCAN"

    signals.append(
        Signal(
            id=f"{case.id}-opportunity-upside",
            case_id=case.id,
            level=SignalLevel.HIGH if doc_found else (SignalLevel.MEDIUM if found else SignalLevel.LOW),
            category=SignalCategory.OPPORTUNITY,
            title="Opportunity Signal: Expansion headroom & upside potential",
            description=(
                "Evidence indicates unmet demand, expansion corridors, or partnership openings that can compound impact and returns."
                if found
                else "No expansion or upside markers detected yet — flagged as an evidence gap, not asserted as upside."
            ),
            direction="opportunity" if found else "risk",
            evidence_refs=[ref],
            evidence_summary=(
                f"Growth headroom and upside markers corroborated by {ref}."
                if found
                else "No opportunity markers found in uploaded documents or external research."
            ),
            recommended_action=(
                "Prioritise the highest-leverage expansion corridor and validate it with a scoped pilot."
                if found
                else "Request growth plan and expansion evidence from the entity."
            ),
            time_horizon="medium-term",
            confidence=0.80 if doc_found else (0.68 if found else 0.60),
            metadata={"domain": "Opportunity Signals", "source_type": "document" if doc_found else ("scan" if found else "gap")}
        )
    )
    return signals


def _domain_trust_signals(case: Case, graph: TrustGraph | None) -> List[Signal]:
    """Explicit Trust Domain Signals."""
    signals: List[Signal] = []
    score = graph.trust_score if graph else 75.0
    level = SignalLevel.HIGH if score < 50 else (SignalLevel.MEDIUM if score < 70 else SignalLevel.LOW)
    direction = "risk" if score < 60 else "opportunity"

    signals.append(
        Signal(
            id=f"{case.id}-domain-trust-score",
            case_id=case.id,
            level=level,
            category=SignalCategory.TRUST,
            title=f"Trust Signal: Corroboration index ({score:.0f}/100)",
            description=f"Institutional trust score is {score:.0f}/100 based on verified multi-source corroboration.",
            direction=direction,
            evidence_refs=["TRUST_GRAPH", "CORROBORATION_INDEX"],
            evidence_summary=f"Synthesized from node connectivity and independent verification checks ({score:.0f}/100).",
            recommended_action="Maintain audited documentation for institutional anchor entities.",
            time_horizon="immediate",
            confidence=0.90,
            metadata={"domain": "Trust Signals", "source_type": "trust_graph"}
        )
    )
    return signals


def _domain_risk_signals(case: Case, ei: EvidenceIntegrityReport | None) -> List[Signal]:
    """Explicit Risk Domain Signals."""
    signals: List[Signal] = []
    contradiction_count = len(ei.contradictions) if ei else 0
    level = SignalLevel.CRITICAL if contradiction_count >= 2 else (SignalLevel.HIGH if contradiction_count == 1 else SignalLevel.MEDIUM)

    signals.append(
        Signal(
            id=f"{case.id}-domain-risk-integrity",
            case_id=case.id,
            level=level,
            category=SignalCategory.RISK,
            title="Risk Signal: Evidence consistency & execution risks",
            description=(
                f"{contradiction_count} material contradiction(s) detected across claims."
                if contradiction_count > 0
                else "Clean consistency profile across verified claims and disclosures."
            ),
            direction="risk" if contradiction_count > 0 else "opportunity",
            evidence_refs=["EVIDENCE_INTEGRITY"],
            evidence_summary=f"Automated contradiction and unverified claim sweep: {contradiction_count} conflict(s).",
            recommended_action="Resolve top factual differences before submitting final IC memorandum.",
            time_horizon="immediate",
            confidence=0.88,
            metadata={"domain": "Risk Signals", "source_type": "evidence_integrity"}
        )
    )
    return signals


def generate_signals_from_case(
    case: Case,
    ei: EvidenceIntegrityReport | None,
    graph: TrustGraph | None,
) -> List[Signal]:
    """Generate deterministic Signals from a Case + core OS outputs.

    This function derives signals across the core domains: Community, Trust,
    Funding, Programme Delivery, Risk, Opportunity, Market, Competitive,
    Climate, Environmental and Tourism.

    Phase 3 (entity-aware intelligence): when the case payload carries an
    entity profile, entity-specific signal domains (e.g. Institutional
    Capacity for NGOs, Destination Readiness for Tourism SMEs) are generated
    on top of the universal domains, with uploaded-document evidence cited
    first (Source A before Source C).
    """

    signals: List[Signal] = []
    # 1. Backward-compatible legacy rules for Phase 5B/5C
    signals.extend(_governance_signals(case, ei))
    signals.extend(_impact_signals(case, ei))
    signals.extend(_trust_signals(case, graph))

    # 2. Core domains: extracted from uploaded documents and Tavily OSINT research
    # NGO/development-first: community, funding and programme delivery are the
    # primary customer's decision drivers and are generated before the
    # investment-shaped lenses (market, competitive).
    signals.extend(_domain_trust_signals(case, graph))
    signals.extend(_community_impact_signals(case))
    signals.extend(_funding_signals(case, ei))
    signals.extend(_program_delivery_signals(case))
    signals.extend(_domain_risk_signals(case, ei))
    signals.extend(_opportunity_signals(case))
    signals.extend(_market_signals(case))
    signals.extend(_competitive_signals(case))
    signals.extend(_climate_signals(case))
    signals.extend(_environmental_signals(case))
    signals.extend(_tourism_signals(case))

    # 3. Entity-aware domains (never replaces the universal set; extends it)
    signals.extend(_entity_profile_signals(case))

    return signals


def _entity_domain_category(domain: str) -> SignalCategory:
    """Fold an entity-specific signal domain into a dashboard domain.

    Kept as an explicit table (instead of nested ternaries) so new entity
    types can be expanded without touching the signal generator. Delivery-
    shaped domains lead because NGOs and development programmes are the
    primary customers; investment-shaped domains are retained for Startups.
    """
    name = (domain or "").strip().lower()

    # Programme delivery: workplans, milestones, results, M&E quality.
    if any(k in name for k in (
        "program delivery", "program performance", "programme delivery",
        "programme performance", "implementation readiness", "delivery capacity",
        "monitoring capacity", "monitoring quality", "impact evidence",
        "knowledge transfer",
    )):
        return SignalCategory.PROGRAM_DELIVERY

    # Community reach and public value.
    if any(k in name for k in ("community", "beneficiar", "public value")):
        return SignalCategory.COMMUNITY_IMPACT

    # Funding sustainability and donor base.
    if any(k in name for k in ("funding", "grantmaking")):
        return SignalCategory.FUNDING

    # Institutional trust: governance, capacity, partnerships, research quality.
    if any(k in name for k in (
        "institutional capacity", "governance", "partnership", "research quality",
    )):
        return SignalCategory.TRUST

    # Risk and compliance lenses.
    if any(k in name for k in ("risk", "policy alignment", "safeguard")):
        return SignalCategory.RISK

    if "climate" in name:
        return SignalCategory.CLIMATE

    if any(k in name for k in ("tourism", "visitor", "destination")):
        return SignalCategory.TOURISM

    if any(k in name for k in ("market", "revenue", "investment readiness")):
        return SignalCategory.MARKET

    return SignalCategory.OPPORTUNITY


def _entity_profile_signals(case: Case) -> List[Signal]:
    """Entity-aware signal domains driven by the entity profile in the payload."""
    from kulima.intelligence.entity_profile import (
        detect_domain_evidence,
        entity_signal_domains,
    )

    profile = (case.payload or {}).get("entity_profile") or {}
    entity_type = str(profile.get("entityType") or "startup")
    domains = entity_signal_domains(entity_type)
    if not domains:
        return []

    doc_sources, web_sources, corpus = _gather_evidence_corpus(case)
    detected = detect_domain_evidence(corpus, domains)
    signals: List[Signal] = []
    for domain in domains:
        hits = detected.get(domain) or []
        has_doc = any(h in corpus for h in hits) and doc_sources
        # Uploaded-document evidence outranks web corroboration (Source A > C).
        if hits and doc_sources:
            level = SignalLevel.HIGH
            primary_ref = doc_sources[0]["ref"]
            source_label = f"uploaded document ({doc_sources[0]['title']})"
            direction = "opportunity"
            confidence = 0.85
        elif hits:
            level = SignalLevel.MEDIUM
            primary_ref = web_sources[0]["ref"] if web_sources else "EVIDENCE_CORPUS"
            source_label = "external corroboration"
            direction = "opportunity"
            confidence = 0.7
        elif doc_sources:
            # Domain not evidenced yet, but documents exist: gap, not absence.
            level = SignalLevel.MEDIUM
            primary_ref = doc_sources[0]["ref"]
            source_label = f"uploaded document ({doc_sources[0]['title']})"
            direction = "risk"
            confidence = 0.65
        else:
            level = SignalLevel.LOW
            primary_ref = "EVIDENCE_CORPUS"
            source_label = "general corpus"
            direction = "risk"
            confidence = 0.55
        signals.append(
            Signal(
                id=f"{case.id}-entity-{domain.lower().replace(' ', '-')}",
                case_id=case.id,
                level=level,
                # Entity domains fold into the dashboard domains so every one
                # of them stays visible. Delivery-shaped domains (workplans,
                # milestones, beneficiary reach, M&E quality) belong to
                # Programme Delivery — the core domain for NGOs and
                # development programmes.
                category=_entity_domain_category(domain),
                title=f"{domain}: " + (
                    f"documented in {source_label}" if hits else f"not yet evidenced — gap flagged"
                ),
                description=(
                    f"Evidence markers ({', '.join(hits[:4])}) found in {source_label}."
                    if hits
                    else f"No {domain.lower()} evidence detected in the corpus; the assessment flags this as a diligence gap for the {profile.get('entityLabel') or 'entity'}."
                ),
                direction=direction,
                evidence_refs=[primary_ref],
                evidence_summary=(
                    f"Detected terms: {', '.join(hits[:6])}. Source: {source_label}."
                    if hits
                    else f"No matching evidence for {domain} in {len(doc_sources)} document(s) and {len(web_sources)} external source(s)."
                ),
                recommended_action=(
                    f"Leverage documented {domain.lower()} strength in the final assessment."
                    if hits
                    else f"Request {domain.lower()} documentation from the entity before final decision."
                ),
                time_horizon="immediate" if direction == "risk" else "medium-term",
                confidence=confidence,
                metadata={
                    "domain": domain,
                    "entityType": entity_type,
                    "source_type": "document" if has_doc else ("web" if hits else "gap"),
                },
            )
        )
    return signals
