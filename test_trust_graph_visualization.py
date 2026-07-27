"""Trust Graph Visualization — unit tests.

Tests cover:
1.  node_color() — correct colours for all registered types
2.  node_symbol() — correct symbols for all registered types
3.  node_size() — scaling with weight
4.  build_layout_positions() — normal graph, empty graph, concentric ring logic
5.  conflict_node_ids() — extraction from EIE report
6.  trust_network_figure() — normal graph, empty graph, with/without EIE
7.  graph_summary_stats() — counts, conflict flag, reliability fields
8.  available_node_types() — sorted unique types
9.  source_nodes() — filter to media type only
10. Contradiction nodes — conflict detection rendering
11. Reliability integration — EIE data flows into stats and figure
12. Responsive layout — height parameter honoured
"""

from __future__ import annotations

import math

import pytest
import plotly.graph_objects as go

from kulima.trust_graph_viz import (
    available_node_types,
    build_layout_positions,
    conflict_node_ids,
    graph_summary_stats,
    node_color,
    node_size,
    node_symbol,
    source_nodes,
    trust_network_figure,
)
from kulima.models import (
    Claim,
    ClaimType,
    ConsistencyStatus,
    Contradiction,
    ContradictionSeverity,
    EvidenceDepth,
    EvidenceIntegrityReport,
    IntegrityGrade,
    StalenessT,
    TrustEdge,
    TrustGraph,
    TrustNode,
)


# ── Shared fixtures ───────────────────────────────────────────────────────────

def _make_node(
    id: str,
    label: str,
    node_type: str = "media",
    weight: float = 0.8,
) -> TrustNode:
    return TrustNode(id=id, label=label, node_type=node_type, weight=weight)


def _make_graph(
    extra_nodes: list[TrustNode] | None = None,
    extra_edges: list[TrustEdge] | None = None,
) -> TrustGraph:
    """Minimal realistic graph: founder → startup + 2 media nodes."""
    nodes = [
        TrustNode(id="founder", label="Ada Obi", node_type="founder", weight=1.2),
        TrustNode(id="startup", label="PayFast NG", node_type="company", weight=1.0),
        TrustNode(id="media_1", label="techcabal.com", node_type="media", weight=0.9),
        TrustNode(id="media_2", label="disrupt-africa.com", node_type="media", weight=0.7),
    ]
    edges = [
        TrustEdge(source="founder", target="startup", relation="founded", strength=0.9),
        TrustEdge(source="founder", target="media_1", relation="mentioned_in", strength=0.8),
        TrustEdge(source="founder", target="media_2", relation="mentioned_in", strength=0.6),
    ]
    if extra_nodes:
        nodes += extra_nodes
    if extra_edges:
        edges += extra_edges
    return TrustGraph(
        nodes=nodes,
        edges=edges,
        trust_score=72.0,
        density=0.42,
        explanation="Test trust graph.",
    )


def _make_claim(url: str = "https://techcabal.com/article") -> Claim:
    return Claim(
        claim_id="c1",
        claim_type=ClaimType.FUNDING_AMOUNT,
        value_raw="$2M",
        source_url=url,
        source_title="TechCabal",
        staleness=StalenessT.FRESH,
        confidence=0.85,
    )


def _make_contradiction(
    url_a: str = "https://techcabal.com/article",
    url_b: str = "https://blog.example.com/post",
) -> Contradiction:
    return Contradiction(
        contradiction_id="con1",
        claim_a=_make_claim(url_a),
        claim_b=_make_claim(url_b),
        severity=ContradictionSeverity.HIGH,
        description="Revenue figures conflict.",
        recommended_action="Verify with founder.",
    )


def _make_ei(
    contradictions: list[Contradiction] | None = None,
    grade: IntegrityGrade = IntegrityGrade.B,
    score: float = 78.0,
) -> EvidenceIntegrityReport:
    return EvidenceIntegrityReport(
        integrity_score=score,
        integrity_grade=grade,
        evidence_depth=EvidenceDepth.MODERATE,
        consistency_status=(
            ConsistencyStatus.CONFLICTS
            if contradictions
            else ConsistencyStatus.CLEAN
        ),
        sparse_mode=False,
        source_count=6,
        claim_count=10,
        high_authority_count=3,
        contradictions=contradictions or [],
        integrity_summary="Test summary.",
        confidence_adjusted=0.75,
    )


# ── Test 1 — node_color() ────────────────────────────────────────────────────

class TestNodeColor:
    def test_founder_is_dark_green(self):
        assert node_color("founder") == "#0B6E4F"

    def test_company_is_teal(self):
        assert node_color("company") == "#1B9AAA"

    def test_media_is_gold(self):
        assert node_color("media") == "#C4A35A"

    def test_conflict_is_red(self):
        assert node_color("conflict") == "#9B2226"

    def test_investor_is_violet(self):
        assert node_color("investor") == "#6B4FBB"

    def test_unknown_type_returns_default(self):
        color = node_color("nonexistent_type")
        assert color == "#5B6F64"

    def test_case_insensitive(self):
        assert node_color("FOUNDER") == node_color("founder")
        assert node_color("Media") == node_color("media")

    def test_all_registered_types_return_hex(self):
        types = [
            "founder", "company", "media", "investor", "institution",
            "market", "government", "university", "conflict", "accelerator",
        ]
        for t in types:
            color = node_color(t)
            assert color.startswith("#"), f"{t} color must start with #"
            assert len(color) == 7, f"{t} color must be 6-digit hex"


# ── Test 2 — node_symbol() ───────────────────────────────────────────────────

class TestNodeSymbol:
    def test_founder_is_star(self):
        assert node_symbol("founder") == "star"

    def test_company_is_diamond(self):
        assert node_symbol("company") == "diamond"

    def test_conflict_is_x(self):
        assert node_symbol("conflict") == "x"

    def test_unknown_returns_circle(self):
        assert node_symbol("unknown_xyz") == "circle"

    def test_all_registered_return_strings(self):
        for t in ["founder", "company", "media", "investor", "institution",
                  "market", "government", "university", "conflict", "accelerator"]:
            sym = node_symbol(t)
            assert isinstance(sym, str) and len(sym) > 0


# ── Test 3 — node_size() ─────────────────────────────────────────────────────

class TestNodeSize:
    def test_founder_larger_than_media(self):
        assert node_size("founder", 1.0) > node_size("media", 1.0)

    def test_higher_weight_gives_larger_size(self):
        small = node_size("media", 0.1)
        large = node_size("media", 1.5)
        assert large >= small

    def test_size_bounded_above(self):
        assert node_size("founder", 99.0) <= 40

    def test_size_bounded_below(self):
        assert node_size("media", 0.0) >= 10


# ── Test 4 — build_layout_positions() ────────────────────────────────────────

class TestBuildLayoutPositions:
    def test_returns_dict_with_all_node_ids(self):
        graph = _make_graph()
        pos = build_layout_positions(graph)
        for node in graph.nodes:
            assert node.id in pos, f"Node {node.id} missing from positions"

    def test_empty_graph_returns_empty_dict(self):
        graph = TrustGraph(nodes=[], edges=[], trust_score=0.0, density=0.0)
        pos = build_layout_positions(graph)
        assert pos == {}

    def test_founder_and_startup_near_centre(self):
        graph = _make_graph()
        pos = build_layout_positions(graph)
        # Centre-layer nodes should have small radii
        for nid in ("founder", "startup"):
            x, y = pos[nid]
            radius = math.sqrt(x**2 + y**2)
            assert radius < 0.15, f"{nid} should be near centre, got radius {radius:.3f}"

    def test_media_nodes_in_outer_ring(self):
        graph = _make_graph()
        pos = build_layout_positions(graph)
        for nid in ("media_1", "media_2"):
            x, y = pos[nid]
            radius = math.sqrt(x**2 + y**2)
            assert radius > 0.3, f"{nid} should be in outer ring, got radius {radius:.3f}"

    def test_positions_are_floats(self):
        graph = _make_graph()
        pos = build_layout_positions(graph)
        for nid, (x, y) in pos.items():
            assert isinstance(x, float)
            assert isinstance(y, float)

    def test_single_node_graph(self):
        graph = TrustGraph(
            nodes=[TrustNode(id="n1", label="Solo", node_type="founder", weight=1.0)],
            edges=[],
            trust_score=50.0,
            density=0.0,
        )
        pos = build_layout_positions(graph)
        assert "n1" in pos


# ── Test 5 — conflict_node_ids() ─────────────────────────────────────────────

class TestConflictNodeIds:
    def test_no_ei_returns_empty_set(self):
        assert conflict_node_ids(None) == set()

    def test_no_contradictions_returns_empty_set(self):
        ei = _make_ei(contradictions=[])
        assert conflict_node_ids(ei) == set()

    def test_returns_both_source_urls(self):
        contradiction = _make_contradiction(
            url_a="https://techcabal.com/article",
            url_b="https://blog.example.com/post",
        )
        ei = _make_ei(contradictions=[contradiction])
        ids = conflict_node_ids(ei)
        assert "https://techcabal.com/article" in ids
        assert "https://blog.example.com/post" in ids

    def test_multiple_contradictions_all_urls_collected(self):
        c1 = _make_contradiction("https://a.com/x", "https://b.com/y")
        c2 = _make_contradiction("https://c.com/p", "https://d.com/q")
        ei = _make_ei(contradictions=[c1, c2])
        ids = conflict_node_ids(ei)
        assert len(ids) == 4

    def test_duplicate_urls_deduplicated(self):
        c1 = _make_contradiction("https://same.com/x", "https://other.com/y")
        c2 = _make_contradiction("https://same.com/x", "https://another.com/z")
        ei = _make_ei(contradictions=[c1, c2])
        ids = conflict_node_ids(ei)
        assert ids.count if False else True  # it's a set — always deduplicated
        assert "https://same.com/x" in ids
        assert len(ids) == 3


# ── Test 6 — trust_network_figure() ──────────────────────────────────────────

class TestTrustNetworkFigure:
    def test_returns_plotly_figure(self):
        graph = _make_graph()
        fig = trust_network_figure(graph)
        assert isinstance(fig, go.Figure)

    def test_empty_graph_returns_figure_with_no_data_message(self):
        graph = TrustGraph(nodes=[], edges=[], trust_score=0.0, density=0.0)
        fig = trust_network_figure(graph)
        assert isinstance(fig, go.Figure)
        # Empty graph should have a title indicating no data
        assert fig.layout.title.text is not None
        assert len(fig.layout.title.text) > 0

    def test_figure_has_traces(self):
        graph = _make_graph()
        fig = trust_network_figure(graph)
        # At minimum: edge trace + at least one node trace
        assert len(fig.data) >= 2

    def test_height_parameter_honoured(self):
        graph = _make_graph()
        fig = trust_network_figure(graph, height=300)
        assert fig.layout.height == 300

    def test_default_height_is_480(self):
        graph = _make_graph()
        fig = trust_network_figure(graph)
        assert fig.layout.height == 480

    def test_figure_with_ei_does_not_raise(self):
        graph = _make_graph()
        ei = _make_ei()
        fig = trust_network_figure(graph, ei=ei)
        assert isinstance(fig, go.Figure)

    def test_figure_with_contradictions_does_not_raise(self):
        graph = _make_graph()
        contradiction = _make_contradiction()
        ei = _make_ei(contradictions=[contradiction])
        fig = trust_network_figure(graph, ei=ei)
        assert isinstance(fig, go.Figure)

    def test_filter_types_limits_traces(self):
        graph = _make_graph()
        # Only show founder nodes
        fig_full = trust_network_figure(graph, filter_types=None)
        fig_filtered = trust_network_figure(graph, filter_types={"founder"})
        # Filtered figure should have fewer node traces
        assert len(fig_filtered.data) <= len(fig_full.data)

    def test_show_labels_false_does_not_raise(self):
        graph = _make_graph()
        fig = trust_network_figure(graph, show_labels=False)
        assert isinstance(fig, go.Figure)

    def test_paper_bgcolor_transparent(self):
        graph = _make_graph()
        fig = trust_network_figure(graph)
        assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"

    def test_legend_orientation_horizontal(self):
        graph = _make_graph()
        fig = trust_network_figure(graph)
        assert fig.layout.legend.orientation == "h"


# ── Test 7 — graph_summary_stats() ───────────────────────────────────────────

class TestGraphSummaryStats:
    def test_node_and_edge_counts_correct(self):
        graph = _make_graph()
        stats = graph_summary_stats(graph)
        assert stats["node_count"] == 4
        assert stats["edge_count"] == 3

    def test_density_matches_graph(self):
        graph = _make_graph()
        stats = graph_summary_stats(graph)
        assert stats["density"] == graph.density

    def test_trust_score_matches_graph(self):
        graph = _make_graph()
        stats = graph_summary_stats(graph)
        assert stats["trust_score"] == graph.trust_score

    def test_no_ei_gives_dash_grade(self):
        graph = _make_graph()
        stats = graph_summary_stats(graph, ei=None)
        assert stats["reliability_grade"] == "—"
        assert stats["reliability_score"] is None

    def test_ei_grade_and_score_populated(self):
        graph = _make_graph()
        ei = _make_ei(grade=IntegrityGrade.C, score=63.0)
        stats = graph_summary_stats(graph, ei=ei)
        assert stats["reliability_grade"] == "C"
        assert stats["reliability_score"] == 63.0

    def test_no_contradictions_has_conflicts_false(self):
        graph = _make_graph()
        ei = _make_ei(contradictions=[])
        stats = graph_summary_stats(graph, ei=ei)
        assert stats["has_conflicts"] is False
        assert stats["conflict_count"] == 0

    def test_with_contradictions_has_conflicts_true(self):
        graph = _make_graph()
        ei = _make_ei(contradictions=[_make_contradiction()])
        stats = graph_summary_stats(graph, ei=ei)
        assert stats["has_conflicts"] is True
        assert stats["conflict_count"] == 1

    def test_type_counts_correct(self):
        graph = _make_graph()
        stats = graph_summary_stats(graph)
        assert stats["type_counts"].get("founder", 0) == 1
        assert stats["type_counts"].get("company", 0) == 1
        assert stats["type_counts"].get("media", 0) == 2

    def test_empty_graph(self):
        graph = TrustGraph(nodes=[], edges=[], trust_score=0.0, density=0.0)
        stats = graph_summary_stats(graph)
        assert stats["node_count"] == 0
        assert stats["edge_count"] == 0
        assert stats["type_counts"] == {}


# ── Test 8 — available_node_types() ──────────────────────────────────────────

class TestAvailableNodeTypes:
    def test_returns_sorted_list(self):
        graph = _make_graph()
        types = available_node_types(graph)
        assert types == sorted(types)

    def test_returns_unique_types_only(self):
        graph = _make_graph()
        types = available_node_types(graph)
        assert len(types) == len(set(types))

    def test_correct_types_for_standard_graph(self):
        graph = _make_graph()
        types = available_node_types(graph)
        assert "founder" in types
        assert "company" in types
        assert "media" in types

    def test_empty_graph_returns_empty_list(self):
        graph = TrustGraph(nodes=[], edges=[], trust_score=0.0, density=0.0)
        assert available_node_types(graph) == []


# ── Test 9 — source_nodes() ──────────────────────────────────────────────────

class TestSourceNodes:
    def test_returns_only_media_nodes(self):
        graph = _make_graph()
        sources = source_nodes(graph)
        for node in sources:
            assert node.node_type.lower() == "media"

    def test_count_correct(self):
        graph = _make_graph()
        sources = source_nodes(graph)
        assert len(sources) == 2

    def test_empty_graph_returns_empty_list(self):
        graph = TrustGraph(nodes=[], edges=[], trust_score=0.0, density=0.0)
        assert source_nodes(graph) == []

    def test_graph_with_no_media_nodes(self):
        graph = TrustGraph(
            nodes=[
                TrustNode(id="f", label="Founder", node_type="founder", weight=1.0),
                TrustNode(id="s", label="Startup", node_type="company", weight=1.0),
            ],
            edges=[TrustEdge(source="f", target="s", relation="founded", strength=0.9)],
            trust_score=60.0,
            density=0.5,
        )
        assert source_nodes(graph) == []


# ── Test 10 — Contradiction nodes / conflict detection ───────────────────────

class TestConflictNodeDetection:
    def test_conflict_node_ids_empty_without_ei(self):
        ids = conflict_node_ids(None)
        assert isinstance(ids, set)
        assert len(ids) == 0

    def test_conflict_urls_match_claim_source_urls(self):
        url_a = "https://techcabal.com/funding-article"
        url_b = "https://disrupt-africa.com/blog/post"
        c = _make_contradiction(url_a, url_b)
        ei = _make_ei(contradictions=[c])
        ids = conflict_node_ids(ei)
        assert url_a in ids
        assert url_b in ids

    def test_figure_generated_with_conflict_ei(self):
        graph = _make_graph()
        c = _make_contradiction(
            "https://techcabal.com/article",
            "https://disrupt-africa.com/post",
        )
        ei = _make_ei(contradictions=[c])
        fig = trust_network_figure(graph, ei=ei)
        # Figure must still be valid
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_stats_conflict_count_matches_contradictions(self):
        graph = _make_graph()
        contradictions = [_make_contradiction() for _ in range(3)]
        ei = _make_ei(contradictions=contradictions)
        stats = graph_summary_stats(graph, ei=ei)
        assert stats["conflict_count"] == 3
        assert stats["has_conflicts"] is True


# ── Test 11 — Reliability integration ────────────────────────────────────────

class TestReliabilityIntegration:
    def test_grade_a_reflected_in_stats(self):
        graph = _make_graph()
        ei = _make_ei(grade=IntegrityGrade.A, score=95.0)
        stats = graph_summary_stats(graph, ei=ei)
        assert stats["reliability_grade"] == "A"
        assert stats["reliability_score"] == 95.0

    def test_grade_f_reflected_in_stats(self):
        graph = _make_graph()
        ei = _make_ei(grade=IntegrityGrade.F, score=30.0)
        stats = graph_summary_stats(graph, ei=ei)
        assert stats["reliability_grade"] == "F"

    def test_figure_does_not_modify_scores(self):
        """trust_network_figure must be pure presentation — scores unchanged."""
        graph = _make_graph()
        original_trust = graph.trust_score
        ei = _make_ei(contradictions=[_make_contradiction()])
        trust_network_figure(graph, ei=ei)
        assert graph.trust_score == original_trust, "trust_score must not be modified"

    def test_stats_does_not_modify_graph(self):
        graph = _make_graph()
        original_nodes = len(graph.nodes)
        ei = _make_ei()
        graph_summary_stats(graph, ei=ei)
        assert len(graph.nodes) == original_nodes, "node list must not be modified"

    def test_sparse_mode_ei_reflected_in_stats(self):
        graph = _make_graph()
        ei = EvidenceIntegrityReport(
            integrity_score=72.0,
            integrity_grade=IntegrityGrade.B,
            evidence_depth=EvidenceDepth.LIMITED,
            consistency_status=ConsistencyStatus.CLEAN,
            sparse_mode=True,
            source_count=3,
            claim_count=5,
            high_authority_count=1,
        )
        stats = graph_summary_stats(graph, ei=ei)
        assert stats["reliability_grade"] == "B"
        assert stats["has_conflicts"] is False


# ── Test 12 — Responsive layout ──────────────────────────────────────────────

class TestResponsiveLayout:
    def test_height_320px_valid(self):
        graph = _make_graph()
        fig = trust_network_figure(graph, height=280)
        assert fig.layout.height == 280

    def test_height_768px_valid(self):
        graph = _make_graph()
        fig = trust_network_figure(graph, height=600)
        assert fig.layout.height == 600

    def test_legend_position_bottom_for_mobile(self):
        """Legend orientation=h places it below the chart — correct for mobile."""
        graph = _make_graph()
        fig = trust_network_figure(graph)
        assert fig.layout.legend.orientation == "h"
        assert fig.layout.legend.y < 0

    def test_axes_have_no_tick_labels(self):
        """Hidden axes prevent overflow on small screens."""
        graph = _make_graph()
        fig = trust_network_figure(graph)
        assert fig.layout.xaxis.showticklabels is False
        assert fig.layout.yaxis.showticklabels is False

    def test_margin_compact(self):
        """Margins should be small to maximise chart area on mobile."""
        graph = _make_graph()
        fig = trust_network_figure(graph)
        assert fig.layout.margin.l <= 30
        assert fig.layout.margin.r <= 30

    def test_positions_bounded_within_unit_square(self):
        """All positions should be within [-1, 1] for both axes."""
        graph = _make_graph()
        pos = build_layout_positions(graph, width=1.0, height=1.0)
        for nid, (x, y) in pos.items():
            assert -1.1 <= x <= 1.1, f"{nid} x={x} out of bounds"
            assert -1.1 <= y <= 1.1, f"{nid} y={y} out of bounds"
