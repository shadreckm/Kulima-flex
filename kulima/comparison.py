"""Deal comparison logic — pure computation, no Streamlit, no LLM, no I/O.

MVP scope: six scalar score dimensions only.
Accepts two ``InvestmentBrief`` objects; returns plain-dict rows and a
one-line winner string.  Nothing is stored in session state or the database.
"""

from __future__ import annotations

from kulima.models import InvestmentBrief

# ── Constants ─────────────────────────────────────────────────────────────────

# Scores within this band of each other are considered a tie.
_TIE_THRESHOLD: float = 2.0

# Ordered dimension specs: (display_name, field_name, is_risk)
# is_risk=True means a LOWER score is better (inverts winner logic).
_DIMENSIONS: list[tuple[str, str, bool]] = [
    ("Overall",  "overall_score",  False),
    ("Founder",  "founder_score",  False),
    ("Startup",  "startup_score",  False),
    ("Market",   "market_score",   False),
    ("Trust",    "trust_score",    False),
    ("Risk ↓",   "risk_score",     True),
]


# ── Public API ────────────────────────────────────────────────────────────────

def build_comparison_rows(
    brief_a: InvestmentBrief,
    brief_b: InvestmentBrief,
) -> list[dict]:
    """Return one display dict per score dimension.

    Each dict has keys: ``Dimension``, ``Deal A``, ``Deal B``, ``Δ``, ``Winner``.
    Suitable for direct use with ``pd.DataFrame`` and ``st.dataframe``.
    """
    rows: list[dict] = []
    for display_name, field, is_risk in _DIMENSIONS:
        sa = float(getattr(brief_a, field, 0.0))
        sb = float(getattr(brief_b, field, 0.0))
        delta = sa - sb

        if abs(delta) < _TIE_THRESHOLD:
            winner = "—"
            delta_str = "≈"
        else:
            if is_risk:
                winner = "A ✓" if sa < sb else "B ✓"
            else:
                winner = "A ✓" if sa > sb else "B ✓"
            delta_str = f"+{delta:.0f}" if delta > 0 else f"\u2212{abs(delta):.0f}"

        rows.append(
            {
                "Dimension": display_name,
                "Deal A": f"{sa:.0f}",
                "Deal B": f"{sb:.0f}",
                "\u0394": delta_str,   # Δ
                "Winner": winner,
            }
        )
    return rows


def build_winner_line(
    brief_a: InvestmentBrief,
    brief_b: InvestmentBrief,
    rows: list[dict],
) -> str:
    """Return a single plain-English sentence declaring the stronger deal.

    Purely deterministic — no LLM, no external calls.
    """
    if not rows:
        return "No comparison data available."

    overall_winner = rows[0]["Winner"]  # first row is always Overall

    if overall_winner == "—":
        return (
            f"Both deals are evenly matched on current evidence "
            f"({brief_a.founder_name}/{brief_a.startup_name} "
            f"vs {brief_b.founder_name}/{brief_b.startup_name})."
        )

    if overall_winner == "A ✓":
        winner_brief, loser_brief = brief_a, brief_b
        winner_label, loser_label = "A", "B"
    else:
        winner_brief, loser_brief = brief_b, brief_a
        winner_label, loser_label = "B", "A"

    # Find the two non-Overall dimensions where the winner leads by the most.
    non_overall = rows[1:]  # skip the Overall row
    winner_rows = [
        r for r in non_overall
        if r["Winner"] == f"{winner_label} \u2713"
    ]
    # Sort by absolute numeric delta descending.
    def _abs_delta(r: dict) -> float:
        raw = r["\u0394"].replace("\u2212", "-").replace("+", "").replace("\u2248", "0")
        try:
            return abs(float(raw))
        except ValueError:
            return 0.0

    top_dims = sorted(winner_rows, key=_abs_delta, reverse=True)[:2]
    dim_phrases = ", ".join(
        f"{r['Dimension']} {r['Deal A']} vs {r['Deal B']}" for r in top_dims
    )

    lead_clause = f" ({dim_phrases})" if dim_phrases else ""
    return (
        f"Deal {winner_label} ({winner_brief.founder_name} / {winner_brief.startup_name}) "
        f"leads overall {winner_brief.overall_score:.0f} vs "
        f"{loser_brief.overall_score:.0f}{lead_clause}."
    )
