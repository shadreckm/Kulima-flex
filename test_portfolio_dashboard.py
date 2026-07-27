"""Test suite for Portfolio Intelligence Layer.

Validates:
- aggregation (aggregate_portfolio)
- charts (recommendation_chart, reliability_chart, sector_chart, score_vs_reliability_scatter, risk_matrix_figure)
- ranking (top_deals by score, reliability, confidence)
- filtering (ic_pipeline_filter, quadrant_label)
- empty database state
"""

from __future__ import annotations

import plotly.graph_objects as go
import pytest

from kulima.portfolio_intelligence import (
    aggregate_portfolio,
    ic_pipeline_filter,
    quadrant_label,
    recommendation_chart,
    reliability_chart,
    risk_matrix_figure,
    score_vs_reliability_scatter,
    sector_chart,
    top_deals,
)


@pytest.fixture
def mock_deal_rows() -> list[dict]:
    """Sample dataset of stored deal runs."""
    return [
        {
            "id": 1,
            "created_at": "2026-07-27T08:00:00Z",
            "founder_name": "Iyinoluwa Aboyeji",
            "startup_name": "Flutterwave",
            "sector": "FinTech",
            "overall_score": 88.5,
            "confidence": 0.92,
            "recommendation": "Invest",
            "integrity_score": 92.0,
            "integrity_grade": "A",
        },
        {
            "id": 2,
            "created_at": "2026-07-27T08:10:00Z",
            "founder_name": "Olugbenga Agboola",
            "startup_name": "Paystack",
            "sector": "FinTech",
            "overall_score": 84.0,
            "confidence": 0.88,
            "recommendation": "Co-Invest",
            "integrity_score": 78.0,
            "integrity_grade": "B",
        },
        {
            "id": 3,
            "created_at": "2026-07-27T08:20:00Z",
            "founder_name": "Sim Shagaya",
            "startup_name": "Konga",
            "sector": "E-Commerce",
            "overall_score": 62.0,
            "confidence": 0.75,
            "recommendation": "Observe",
            "integrity_score": 70.0,
            "integrity_grade": "B",
        },
        {
            "id": 4,
            "created_at": "2026-07-27T08:30:00Z",
            "founder_name": "John Doe",
            "startup_name": "RiskyBiz",
            "sector": "Crypto",
            "overall_score": 72.0,
            "confidence": 0.50,
            "recommendation": "Pass",
            "integrity_score": 40.0,
            "integrity_grade": "D",
        },
        {
            "id": 5,
            "created_at": "2026-07-27T08:40:00Z",
            "founder_name": "Jane Smith",
            "startup_name": "AgriCrop",
            "sector": "AgTech",
            "overall_score": 45.0,
            "confidence": 0.60,
            "recommendation": "Pass",
            "integrity_score": 35.0,
            "integrity_grade": "F",
        },
        {
            "id": 6,
            "created_at": "2026-07-27T08:50:00Z",
            "founder_name": "Legacy Founder",
            "startup_name": "OldTech",
            "sector": "General / Tech",
            "overall_score": 79.0,
            "confidence": 0.80,
            "recommendation": "Invest",
            "integrity_score": None,
            "integrity_grade": None,
        },
    ]


def test_aggregate_portfolio_with_data(mock_deal_rows):
    kpis = aggregate_portfolio(mock_deal_rows)

    assert kpis["total_deals"] == 6
    assert kpis["invest_count"] == 2
    assert kpis["co_invest_count"] == 1
    assert kpis["observe_count"] == 1
    assert kpis["pass_count"] == 2
    assert kpis["ic_ready_count"] == 3  # Flutterwave (A), Paystack (B), OldTech (None)
    assert kpis["has_reliability_data"] is True
    assert pytest.approx(kpis["avg_score"], 0.1) == 71.75
    assert pytest.approx(kpis["avg_reliability"], 0.1) == 63.0
    assert pytest.approx(kpis["avg_confidence"], 0.01) == 0.74


def test_aggregate_portfolio_empty():
    kpis = aggregate_portfolio([])

    assert kpis["total_deals"] == 0
    assert kpis["invest_count"] == 0
    assert kpis["observe_count"] == 0
    assert kpis["pass_count"] == 0
    assert kpis["avg_score"] == 0.0
    assert kpis["avg_reliability"] == 0.0
    assert kpis["avg_confidence"] == 0.0
    assert kpis["ic_ready_count"] == 0
    assert kpis["has_reliability_data"] is False


def test_top_deals_ranking(mock_deal_rows):
    # Ranked by score (default)
    by_score = top_deals(mock_deal_rows, sort_by="score", limit=3)
    assert len(by_score) == 3
    assert by_score[0]["startup_name"] == "Flutterwave"
    assert by_score[1]["startup_name"] == "Paystack"
    assert by_score[2]["startup_name"] == "OldTech"

    # Ranked by reliability
    by_rel = top_deals(mock_deal_rows, sort_by="reliability", limit=3)
    assert len(by_rel) == 3
    assert by_rel[0]["startup_name"] == "Flutterwave"  # 92.0
    assert by_rel[1]["startup_name"] == "Paystack"     # 78.0
    assert by_rel[2]["startup_name"] == "Konga"        # 70.0

    # Ranked by confidence
    by_conf = top_deals(mock_deal_rows, sort_by="confidence", limit=3)
    assert len(by_conf) == 3
    assert by_conf[0]["startup_name"] == "Flutterwave"  # 0.92
    assert by_conf[1]["startup_name"] == "Paystack"     # 0.88
    assert by_conf[2]["startup_name"] == "OldTech"      # 0.80


def test_top_deals_empty():
    assert top_deals([], sort_by="score") == []


def test_ic_pipeline_filter(mock_deal_rows):
    ic_ready = ic_pipeline_filter(mock_deal_rows)
    names = {r["startup_name"] for r in ic_ready}

    # Flutterwave: Invest + Grade A -> Yes
    # Paystack: Co-Invest + Grade B -> Yes
    # Konga: Observe -> No
    # RiskyBiz: Pass -> No
    # AgriCrop: Pass -> No
    # OldTech: Invest + Grade None -> Yes (pre-EIE accepted)
    assert names == {"Flutterwave", "Paystack", "OldTech"}


def test_quadrant_label():
    assert quadrant_label(80.0, 90.0) == "Strong IC Candidate"
    assert quadrant_label(80.0, 40.0) == "Verify Before IC"
    assert quadrant_label(50.0, 80.0) == "Evidence Solid, Deal Weak"
    assert quadrant_label(40.0, 30.0) == "Primary Data Needed"
    assert quadrant_label(85.0, None) == "No Reliability Data"


def test_charts_generation(mock_deal_rows):
    # Recommendation chart
    fig_rec = recommendation_chart(mock_deal_rows)
    assert isinstance(fig_rec, go.Figure)

    # Reliability chart
    fig_rel = reliability_chart(mock_deal_rows)
    assert isinstance(fig_rel, go.Figure)

    # Sector chart
    fig_sec = sector_chart(mock_deal_rows)
    assert isinstance(fig_sec, go.Figure)

    # Scatter plot
    fig_scatter = score_vs_reliability_scatter(mock_deal_rows)
    assert isinstance(fig_scatter, go.Figure)

    # Risk matrix figure
    fig_matrix = risk_matrix_figure(mock_deal_rows)
    assert isinstance(fig_matrix, go.Figure)


def test_charts_empty_state():
    fig_rec = recommendation_chart([])
    assert isinstance(fig_rec, go.Figure)

    fig_rel = reliability_chart([])
    assert isinstance(fig_rel, go.Figure)

    fig_sec = sector_chart([])
    assert isinstance(fig_sec, go.Figure)

    fig_scatter = score_vs_reliability_scatter([])
    assert isinstance(fig_scatter, go.Figure)

    fig_matrix = risk_matrix_figure([])
    assert isinstance(fig_matrix, go.Figure)
