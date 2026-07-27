"""Trust Graph Visualization — Plotly network rendering for Kulima FLEX.

Transforms TrustGraph data into investor-facing interactive visualizations.

Public API (pure, no Streamlit):
  trust_network_figure()     — Plotly scatter-network figure
  node_color()               — hex colour for a node type
  node_symbol()              — marker symbol for a node type
  build_layout_positions()   — spring-layout dict {node_id: (x, y)}
  conflict_node_ids()        — node ids involved in EIE contradictions

Public API (Streamlit):
  render_trust_network_preview()   — compact summary card (TAB 1)
  render_trust_graph_explorer()    — full expandable explorer (expander)

No agents, scoring, orchestrator, EIE logic, or session state modified.
"""

from __future__ import annotations

import math
import html as _html
import textwrap
from typing import Any

import plotly.graph_objects as go

from kulima.models import (
    EvidenceIntegrityReport,
    InvestmentBrief,
    TrustGraph,
    TrustNode,
)

# ── Node type palette ─────────────────────────────────────────────────────────
# Each node_type maps to a distinct, accessible colour and marker symbol.

_NODE_COLORS: dict[str, str] = {
    "founder":     "#0B6E4F",   # deep green   — protagonist
    "company":     "#1B9AAA",   # teal         — startup entity
    "media":       "#C4A35A",   # gold         — press / OSINT sources
    "investor":    "#6B4FBB",   # violet       — investors / funds
    "institution": "#2E6DA4",   # blue         — banks, DFIs, accelerators
    "market":      "#3D9970",   # mid-green    — market context
    "government":  "#8B4513",   # brown        — regulatory bodies
    "university":  "#E07B39",   # orange       — academic / incubator
    "conflict":    "#9B2226",   # red          — EIE contradiction node
    "accelerator": "#7EC8D4",   # light teal   — accelerators / hubs
    "default":     "#5B6F64",   # neutral grey — unclassified
}

_NODE_SYMBOLS: dict[str, str] = {
    "founder":     "star",
    "company":     "diamond",
    "media":       "circle",
    "investor":    "hexagon",
    "institution": "square",
    "market":      "triangle-up",
    "government":  "pentagon",
    "university":  "triangle-down",
    "conflict":    "x",
    "accelerator": "octagon",
    "default":     "circle",
}

_NODE_SIZES: dict[str, int] = {
    "founder":     26,
    "company":     22,
    "investor":    18,
    "institution": 16,
    "media":       14,
    "market":      14,
    "government":  16,
    "university":  15,
    "accelerator": 15,
    "conflict":    20,
    "default":     13,
}

_NODE_LABELS: dict[str, str] = {
    "founder":     "Founder",
    "company":     "Startup",
    "media":       "Source / Media",
    "investor":    "Investor",
    "institution": "Institution",
    "market":      "Market",
    "government":  "Government",
    "university":  "University / Accelerator",
    "conflict":    "⚠ Evidence Conflict",
    "accelerator": "Accelerator",
    "default":     "Entity",
}


# ═════════════════════════════════════════════════════════════════════════════
# Pure helpers — no Streamlit, fully testable
# ═════════════════════════════════════════════════════════════════════════════

def node_color(node_type: str) -> str:
    """Return the hex colour for a given node type."""
    return _NODE_COLORS.get(node_type.lower(), _NODE_COLORS["default"])


def node_symbol(node_type: str) -> str:
    """Return the Plotly marker symbol for a given node type."""
    return _NODE_SYMBOLS.get(node_type.lower(), _NODE_SYMBOLS["default"])


def node_size(node_type: str, weight: float = 1.0) -> int:
    """Return marker size scaled by node weight."""
    base = _NODE_SIZES.get(node_type.lower(), _NODE_SIZES["default"])
    return max(10, min(40, int(base * (0.6 + weight * 0.4))))


def conflict_node_ids(ei: EvidenceIntegrityReport | None) -> set[str]:
    """Return the set of source URLs involved in EIE contradictions.

    These are used to visually flag media nodes that are part of a detected
    conflict.  Pure function — reads EIE report, touches no scores.
    """
    if ei is None:
        return set()
    ids: set[str] = set()
    for c in ei.contradictions:
        if c.claim_a.source_url:
            ids.add(c.claim_a.source_url)
        if c.claim_b.source_url:
            ids.add(c.claim_b.source_url)
    return ids


def build_layout_positions(
    graph: TrustGraph,
    width: float = 1.0,
    height: float = 1.0,
) -> dict[str, tuple[float, float]]:
    """Compute node positions using a deterministic circular spring-like layout.

    Founder and company nodes are placed at the centre; other nodes radiate
    outward in concentric rings by node type priority.  No external graph
    library required — computed deterministically so tests don't need seeding.
    """
    if not graph.nodes:
        return {}

    # Priority layers: 0 = centre, 1 = inner ring, 2 = outer ring
    _LAYER: dict[str, int] = {
        "founder": 0, "company": 0,
        "investor": 1, "institution": 1, "accelerator": 1,
        "market": 1, "government": 1, "university": 1,
        "media": 2, "conflict": 2, "default": 2,
    }

    layers: dict[int, list[str]] = {0: [], 1: [], 2: []}
    for node in graph.nodes:
        layer = _LAYER.get(node.node_type.lower(), 2)
        layers[layer].append(node.id)

    positions: dict[str, tuple[float, float]] = {}
    radii = {0: 0.0, 1: 0.38 * min(width, height), 2: 0.78 * min(width, height)}

    for layer_idx, node_ids in layers.items():
        r = radii[layer_idx]
        n = len(node_ids)
        if n == 0:
            continue
        if r == 0.0:
            # Centre layer — spread slightly if multiple nodes
            for i, nid in enumerate(node_ids):
                offset = (i - (n - 1) / 2) * 0.06
                positions[nid] = (offset, 0.0)
        else:
            angle_step = 2 * math.pi / n
            for i, nid in enumerate(node_ids):
                angle = i * angle_step
                positions[nid] = (r * math.cos(angle), r * math.sin(angle))

    return positions


def trust_network_figure(
    graph: TrustGraph,
    ei: EvidenceIntegrityReport | None = None,
    *,
    height: int = 480,
    show_labels: bool = True,
    filter_types: set[str] | None = None,
) -> go.Figure:
    """Build an interactive Plotly scatter-network figure from a TrustGraph.

    Parameters
    ----------
    graph:        The TrustGraph data model (nodes + edges).
    ei:           Optional EvidenceIntegrityReport — used only to flag
                  conflict nodes visually.  Does NOT modify any scores.
    height:       Figure height in px.  Use smaller values on mobile.
    show_labels:  Whether to show node labels on the chart.
    filter_types: If set, only render nodes whose node_type is in this set.

    Returns a go.Figure that is ready to pass to st.plotly_chart().
    """
    if not graph.nodes:
        fig = go.Figure()
        fig.update_layout(
            title=dict(
                text="No trust network data available",
                font=dict(family="Fraunces", size=14, color="#5B6F64"),
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            height=200,
        )
        return fig

    conflict_urls = conflict_node_ids(ei)
    positions = build_layout_positions(graph)

    # Filter nodes
    visible_nodes = [
        n for n in graph.nodes
        if (filter_types is None or n.node_type.lower() in filter_types)
    ]
    visible_ids = {n.id for n in visible_nodes}

    # Build edge traces — one trace for all edges (thin grey lines)
    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    edge_hover: list[str] = []

    for edge in graph.edges:
        if edge.source not in visible_ids or edge.target not in visible_ids:
            continue
        x0, y0 = positions.get(edge.source, (0.0, 0.0))
        x1, y1 = positions.get(edge.target, (0.0, 0.0))
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        line=dict(width=1.2, color="rgba(11,61,46,0.22)"),
        hoverinfo="none",
        showlegend=False,
        name="",
    )

    # Build one node scatter trace per node_type for grouped legend
    type_groups: dict[str, list[TrustNode]] = {}
    for node in visible_nodes:
        nt = node.node_type.lower()
        # Override type for conflict nodes
        if any(
            node.id in (e.source, e.target)
            for e in graph.edges
            if _node_is_conflict_source(node, conflict_urls, graph)
        ):
            nt = "conflict"
        type_groups.setdefault(nt, []).append(node)

    node_traces: list[go.Scatter] = []
    for ntype, nodes_in_group in type_groups.items():
        xs, ys, texts, hovers, sizes = [], [], [], [], []
        for node in nodes_in_group:
            pos = positions.get(node.id, (0.0, 0.0))
            xs.append(pos[0])
            ys.append(pos[1])
            label = _html.escape(node.label[:28] + ("…" if len(node.label) > 28 else ""))
            texts.append(label if show_labels else "")
            conflict_note = ""
            if ntype == "conflict":
                conflict_note = "<br><b style='color:#9B2226'>⚠ Sources disagree</b>"
            hovers.append(
                f"<b>{_html.escape(node.label)}</b><br>"
                f"Type: {_NODE_LABELS.get(ntype, ntype)}<br>"
                f"Weight: {node.weight:.2f}"
                f"{conflict_note}"
                f"<extra></extra>"
            )
            sizes.append(node_size(ntype, node.weight))

        node_traces.append(
            go.Scatter(
                x=xs,
                y=ys,
                mode="markers+text" if show_labels else "markers",
                marker=dict(
                    symbol=node_symbol(ntype),
                    size=sizes,
                    color=node_color(ntype),
                    line=dict(
                        width=2 if ntype in ("founder", "company", "conflict") else 1,
                        color="white",
                    ),
                    opacity=0.92,
                ),
                text=texts,
                textposition="top center",
                textfont=dict(
                    size=9,
                    color="#1F2A24",
                    family="Source Sans 3, sans-serif",
                ),
                hovertemplate=hovers,
                name=_NODE_LABELS.get(ntype, ntype),
                showlegend=True,
            )
        )

    fig = go.Figure(data=[edge_trace] + node_traces)
    fig.update_layout(
        title=dict(
            text="Trust Network",
            font=dict(family="Fraunces", size=15, color="#0B3D2E"),
            x=0.0,
            xanchor="left",
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            y=-0.12,
            x=0.5,
            xanchor="center",
            font=dict(size=9, family="Source Sans 3"),
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor="rgba(11,61,46,0.12)",
            borderwidth=1,
        ),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=20, r=20, t=42, b=60),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(241,247,243,0.45)",
        height=height,
        hovermode="closest",
        dragmode="pan",
    )
    return fig


def _node_is_conflict_source(
    node: TrustNode,
    conflict_urls: set[str],
    graph: TrustGraph,
) -> bool:
    """Return True if this node's label matches a conflict source URL domain."""
    if not conflict_urls:
        return False
    label_lower = node.label.lower()
    for url in conflict_urls:
        domain = url.split("/")[2].replace("www.", "") if "/" in url else url
        if domain and domain.lower() in label_lower:
            return True
    return False


# ── Summary stats helpers ─────────────────────────────────────────────────────

def graph_summary_stats(
    graph: TrustGraph,
    ei: EvidenceIntegrityReport | None = None,
) -> dict[str, Any]:
    """Return a dict of display-ready summary statistics for the trust graph.

    Pure function — no Streamlit, fully testable.
    """
    n_nodes = len(graph.nodes)
    n_edges = len(graph.edges)
    density = graph.density
    trust_score = graph.trust_score

    type_counts: dict[str, int] = {}
    for node in graph.nodes:
        nt = node.node_type.lower()
        type_counts[nt] = type_counts.get(nt, 0) + 1

    n_conflicts = len(ei.contradictions) if ei else 0
    has_conflicts = n_conflicts > 0

    reliability_grade = ei.integrity_grade.value if ei else "—"
    reliability_score = ei.integrity_score if ei else None

    return {
        "node_count": n_nodes,
        "edge_count": n_edges,
        "density": density,
        "trust_score": trust_score,
        "type_counts": type_counts,
        "conflict_count": n_conflicts,
        "has_conflicts": has_conflicts,
        "reliability_grade": reliability_grade,
        "reliability_score": reliability_score,
    }


def available_node_types(graph: TrustGraph) -> list[str]:
    """Return sorted list of unique node types in the graph."""
    return sorted({n.node_type.lower() for n in graph.nodes})


def source_nodes(graph: TrustGraph) -> list[TrustNode]:
    """Return only media/source nodes from the graph."""
    return [n for n in graph.nodes if n.node_type.lower() == "media"]


# ═════════════════════════════════════════════════════════════════════════════
# Streamlit rendering functions
# ═════════════════════════════════════════════════════════════════════════════

def render_trust_network_preview(
    brief: InvestmentBrief,
    *,
    key: str = "trust_net_preview",
) -> None:
    """Render the compact Trust Network Preview card inside the dashboard shell.

    Shows: node count · edge count · density · trust score · reliability badge.
    Gated on brief.trust_graph being present.
    """
    import streamlit as st

    if not brief.trust_graph:
        return

    graph = brief.trust_graph
    ei = brief.evidence_integrity
    stats = graph_summary_stats(graph, ei)

    # Reliability colour
    grade_colors = {
        "A": "#0B6E4F", "B": "#2D8A6B",
        "C": "#B8892D", "D": "#D97706", "F": "#9B2226",
    }
    grade = stats["reliability_grade"]
    grade_color = grade_colors.get(grade, "#5B6F64")
    conflict_badge = ""
    if stats["has_conflicts"]:
        conflict_badge = (
            f'&nbsp;<span style="background:#9B222614;border:1px solid #9B2226aa;'
            f'color:#9B2226;padding:0.1rem 0.45rem;border-radius:999px;'
            f'font-size:0.72rem;font-weight:700;">⚠ {stats["conflict_count"]} conflict'
            f'{"s" if stats["conflict_count"] != 1 else ""}</span>'
        )

    reliability_html = ""
    if ei is not None:
        reliability_html = (
            f'<span style="background:{grade_color}18;border:1px solid {grade_color}44;'
            f'color:{grade_color};padding:0.12rem 0.55rem;border-radius:999px;'
            f'font-size:0.75rem;font-weight:700;">'
            f'Reliability {grade} · {stats["reliability_score"]:.0f}/100</span>'
        )

    html_block = textwrap.dedent(f"""
        <div style="background:rgba(255,255,255,0.68);border:1px solid rgba(11,61,46,0.10);
            border-radius:14px;padding:0.7rem 1rem 0.65rem;margin:0.4rem 0 0.6rem;
            display:flex;flex-wrap:wrap;align-items:center;gap:0.5rem;">
            <span style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.07em;
                color:#5B6F64;font-weight:700;margin-right:0.25rem;">Trust Network</span>
            <span style="font-size:0.85rem;color:#0B3D2E;font-weight:600;">
                {stats['node_count']} nodes
            </span>
            <span style="color:#A8BDB2;">·</span>
            <span style="font-size:0.85rem;color:#0B3D2E;font-weight:600;">
                {stats['edge_count']} edges
            </span>
            <span style="color:#A8BDB2;">·</span>
            <span style="font-size:0.85rem;color:#0B3D2E;font-weight:600;">
                Density {stats['density']:.2f}
            </span>
            <span style="color:#A8BDB2;">·</span>
            <span style="font-size:0.85rem;color:#0B3D2E;font-weight:600;">
                Trust {stats['trust_score']:.0f}/100
            </span>
            {reliability_html}
            {conflict_badge}
        </div>
        """)
    st.markdown(html_block, unsafe_allow_html=True)


def render_trust_graph_explorer(
    brief: InvestmentBrief,
    *,
    key_prefix: str = "tge",
) -> None:
    """Render the full expandable Trust Graph Explorer.

    Contains:
    - Interactive Plotly network diagram
    - Node type filter
    - Source breakdown table
    - Reliability context (if EIE data present)
    - Contradiction overlay (display-only, no score changes)

    Gated on brief.trust_graph being present.
    """
    import streamlit as st

    if not brief.trust_graph:
        st.caption("Trust graph not available for this analysis.")
        return

    graph = brief.trust_graph
    ei = brief.evidence_integrity
    stats = graph_summary_stats(graph, ei)
    conflict_urls = conflict_node_ids(ei)

    # ── Explanation + coverage note ───────────────────────────────────────
    st.write(graph.explanation)

    # Inline coverage note from trust_layer_ui if EIE present
    if ei is not None:
        from kulima.trust_layer_ui import render_trust_graph_coverage_note
        render_trust_graph_coverage_note(ei)

    # ── Conflict warning banner ───────────────────────────────────────────
    if stats["has_conflicts"]:
        conflict_descriptions = [
            c.description[:120] + ("…" if len(c.description) > 120 else "")
            for c in (ei.contradictions if ei else [])
        ]
        conflict_lines = "\n".join(f"- {d}" for d in conflict_descriptions[:3])
        st.warning(
            f"⚠ **Sources disagree** on {stats['conflict_count']} point"
            f"{'s' if stats['conflict_count'] != 1 else ''} in this network. "
            f"Conflict nodes are shown in **red**. Scores are not affected — "
            f"verify before IC.\n\n{conflict_lines}",
            icon="⚠️",
        )

    # ── Node type filter ──────────────────────────────────────────────────
    all_types = available_node_types(graph)
    type_labels = [_NODE_LABELS.get(t, t.title()) for t in all_types]

    show_labels_toggle = st.toggle(
        "Show node labels",
        value=True,
        key=f"{key_prefix}_labels_toggle",
    )

    selected_types_labels = st.multiselect(
        "Filter by node type",
        options=type_labels,
        default=type_labels,
        key=f"{key_prefix}_type_filter",
        help="Show or hide specific node types in the network diagram.",
    )

    # Map selected labels back to type strings
    label_to_type = {_NODE_LABELS.get(t, t.title()): t for t in all_types}
    selected_types: set[str] | None = (
        {label_to_type[lbl] for lbl in selected_types_labels}
        if selected_types_labels and len(selected_types_labels) < len(all_types)
        else None
    )

    # ── Network figure ────────────────────────────────────────────────────
    fig = trust_network_figure(
        graph,
        ei=ei,
        height=500,
        show_labels=show_labels_toggle,
        filter_types=selected_types,
    )
    st.plotly_chart(
        fig,
        width="stretch",
        key=f"{key_prefix}_network_chart",
    )

    # ── Stats row ─────────────────────────────────────────────────────────
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Nodes", stats["node_count"])
    sc2.metric("Edges", stats["edge_count"])
    sc3.metric("Density", f"{stats['density']:.2f}")
    sc4.metric("Trust Score", f"{stats['trust_score']:.0f}/100")

    # ── Node type breakdown ───────────────────────────────────────────────
    if stats["type_counts"]:
        with st.expander("📊 Node Type Breakdown", expanded=False):
            import pandas as pd
            rows = [
                {
                    "Type": _NODE_LABELS.get(t, t.title()),
                    "Count": c,
                    "Colour": node_color(t),
                }
                for t, c in sorted(
                    stats["type_counts"].items(), key=lambda x: -x[1]
                )
            ]
            df = pd.DataFrame(rows)
            st.dataframe(
                df[["Type", "Count"]],
                width="stretch",
                hide_index=True,
                key=f"{key_prefix}_type_breakdown",
            )

    # ── Source node breakdown ─────────────────────────────────────────────
    src_nodes = source_nodes(graph)
    if src_nodes:
        with st.expander(
            f"🔗 Evidence Sources in Network ({len(src_nodes)})", expanded=False
        ):
            for node in src_nodes:
                is_conflict = _node_is_conflict_source(node, conflict_urls, graph)
                conflict_tag = (
                    ' <span style="color:#9B2226;font-size:0.78rem;'
                    'font-weight:700;">⚠ Sources disagree</span>'
                    if is_conflict else ""
                )
                st.markdown(
                    f'<div style="padding:0.25rem 0;border-bottom:'
                    f'1px solid rgba(11,61,46,0.07);">'
                    f'<span style="font-size:0.88rem;color:#0B3D2E;">'
                    f'<b>{_html.escape(node.label)}</b></span>'
                    f'&nbsp;<span style="font-size:0.75rem;color:#5B6F64;">'
                    f'weight {node.weight:.2f}</span>'
                    f'{conflict_tag}</div>',
                    unsafe_allow_html=True,
                )

    # ── Full Reliability context ──────────────────────────────────────────
    if ei is not None:
        with st.expander("🔬 Evidence Integrity Context", expanded=False):
            from kulima.trust_layer_ui import render_reliability_report
            render_reliability_report(ei)

    # ── Legend ────────────────────────────────────────────────────────────
    with st.expander("🎨 Node Colour Legend", expanded=False):
        legend_cols = st.columns(3)
        items = [
            (t, _NODE_LABELS.get(t, t.title()))
            for t in _NODE_COLORS
            if t != "default"
        ]
        for idx, (ntype, label) in enumerate(items):
            col = legend_cols[idx % 3]
            color = node_color(ntype)
            col.markdown(
                f'<div style="display:flex;align-items:center;gap:0.4rem;'
                f'padding:0.18rem 0;">'
                f'<span style="display:inline-block;width:12px;height:12px;'
                f'border-radius:50%;background:{color};flex-shrink:0;"></span>'
                f'<span style="font-size:0.82rem;color:#2F453B;">'
                f'{_html.escape(label)}</span></div>',
                unsafe_allow_html=True,
            )
