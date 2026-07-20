"""Trust graph construction — digital footprint & reputation network."""

from __future__ import annotations

import hashlib

import networkx as nx

from kulima.llm import LLMClient
from kulima.models import SourceAttribution, TrustEdge, TrustGraph, TrustNode
from kulima.research import ResearchEngine
from kulima.scoring import clamp


class TrustGraphEngine:
    """Builds a founder–startup–ecosystem trust graph from OSINT + LLM inference."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    def build(
        self,
        founder: str,
        startup: str,
        sources: list[SourceAttribution],
    ) -> TrustGraph:
        nodes = [
            TrustNode(id="founder", label=founder, node_type="founder", weight=1.2),
            TrustNode(id="startup", label=startup or "Unnamed Venture", node_type="company", weight=1.0),
            TrustNode(id="africa_market", label="African Market Context", node_type="market", weight=0.8),
        ]
        edges = [
            TrustEdge(source="founder", target="startup", relation="founded", strength=0.9),
            TrustEdge(source="startup", target="africa_market", relation="operates_in", strength=0.6),
        ]

        # Seed nodes from evidence domains
        for i, src in enumerate(sources[:8]):
            domain = _domain(src.url) or f"source_{i}"
            node_id = f"media_{hashlib.md5(domain.encode()).hexdigest()[:8]}"
            if not any(n.id == node_id for n in nodes):
                nodes.append(
                    TrustNode(
                        id=node_id,
                        label=domain,
                        node_type="media",
                        weight=0.5 + src.relevance * 0.5,
                    )
                )
                rel = src.relevance / 100 if src.relevance > 1 else src.relevance
                edges.append(
                    TrustEdge(
                        source="founder",
                        target=node_id,
                        relation="mentioned_in",
                        strength=max(0.2, min(1.0, rel)),
                    )
                )

        # LLM enrichment of institutional / investor links
        try:
            enriched = self.llm.complete_json(
                system=(
                    "You are an OSINT trust-graph analyst for African venture deals. "
                    "Infer plausible entities linked to the founder/startup from evidence. "
                    "Return JSON: {entities:[{id,label,type,weight}], "
                    "links:[{source,target,relation,strength}]}. "
                    "Types: investor|institution|media|company. Max 6 entities."
                ),
                user=(
                    f"Founder: {founder}\nStartup: {startup}\n\n"
                    f"Evidence:\n{ResearchEngine.evidence_corpus(sources, 6)}"
                ),
            )
            for ent in enriched.get("entities", [])[:6]:
                eid = str(ent.get("id") or ent.get("label", "entity")).lower().replace(" ", "_")
                if any(n.id == eid for n in nodes):
                    continue
                nodes.append(
                    TrustNode(
                        id=eid,
                        label=str(ent.get("label", eid)),
                        node_type=str(ent.get("type", "institution")),
                        weight=float(ent.get("weight", 0.7)),
                    )
                )
            for link in enriched.get("links", [])[:8]:
                edges.append(
                    TrustEdge(
                        source=str(link.get("source", "founder")),
                        target=str(link.get("target", "startup")),
                        relation=str(link.get("relation", "associated")),
                        strength=float(link.get("strength", 0.5)),
                    )
                )
        except Exception as exc:
            import logging
            logging.warning(
                f"TrustGraphEngine LLM enrichment failed — graph will use base nodes only. "
                f"{type(exc).__name__}: {exc}",
                exc_info=True,
            )

        g = nx.Graph()
        for n in nodes:
            g.add_node(n.id, **n.model_dump())
        for e in edges:
            if e.source in g.nodes and e.target in g.nodes:
                g.add_edge(e.source, e.target, weight=e.strength, relation=e.relation)

        density = float(nx.density(g)) if g.number_of_nodes() > 1 else 0.0
        # Trust score: footprint breadth + connectivity + evidence volume
        footprint = min(len(sources) * 6.5, 40)
        connectivity = density * 35
        centrality_bonus = 0.0
        if "founder" in g:
            try:
                cent = nx.degree_centrality(g).get("founder", 0)
                centrality_bonus = cent * 25
            except Exception:
                centrality_bonus = 10.0
        trust_score = clamp(footprint + connectivity + centrality_bonus + 15)

        explanation = (
            f"Trust graph spans {len(nodes)} entities and {len(edges)} relations. "
            f"Network density {density:.2f}. Digital footprint across {len(sources)} sources. "
            f"Founder centrality and ecosystem adjacency drive the {trust_score:.0f}/100 trust score."
        )
        return TrustGraph(
            nodes=nodes,
            edges=edges,
            trust_score=trust_score,
            density=density,
            explanation=explanation,
        )


def _domain(url: str) -> str:
    if not url:
        return ""
    try:
        return url.split("/")[2].replace("www.", "")
    except Exception:
        return url[:40]
