"""Unit tests for kulima/comparison.py.

Mirrors the test_pipeline.py pattern: no Streamlit, no LLM, no DB.
Uses lightweight stubs so the test suite runs offline.
"""

import sys
import types
import unittest

# ── Stub heavy optional dependencies ─────────────────────────────────────────
for _mod in [
    "networkx", "tavily", "reportlab", "reportlab.lib",
    "reportlab.lib.pagesizes", "reportlab.lib.styles",
    "reportlab.lib.colors", "reportlab.lib.units", "reportlab.platypus",
    "plotly", "plotly.graph_objects", "streamlit",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

# ── Safe to import project code now ──────────────────────────────────────────
from kulima.comparison import build_comparison_rows, build_winner_line, _TIE_THRESHOLD
from kulima.models import InvestmentBrief


# ── Helpers ───────────────────────────────────────────────────────────────────

def _brief(
    founder: str = "Alice",
    startup: str = "StartupA",
    overall: float = 70.0,
    founder_s: float = 65.0,
    startup_s: float = 60.0,
    market_s: float = 55.0,
    trust_s: float = 50.0,
    risk_s: float = 40.0,
) -> InvestmentBrief:
    """Minimal InvestmentBrief — all other fields use Pydantic defaults."""
    return InvestmentBrief(
        founder_name=founder,
        startup_name=startup,
        overall_score=overall,
        founder_score=founder_s,
        startup_score=startup_s,
        market_score=market_s,
        trust_score=trust_s,
        risk_score=risk_s,
    )


# ── Test classes ──────────────────────────────────────────────────────────────

class TestBuildComparisonRows(unittest.TestCase):

    def setUp(self) -> None:
        self.a = _brief("Alice", "AlphaVenture", overall=80, founder_s=75,
                         startup_s=70, market_s=65, trust_s=60, risk_s=30)
        self.b = _brief("Bob",   "BetaStartup",  overall=40, founder_s=35,
                         startup_s=40, market_s=38, trust_s=42, risk_s=70)

    def test_row_count(self) -> None:
        rows = build_comparison_rows(self.a, self.b)
        self.assertEqual(len(rows), 6)

    def test_required_keys(self) -> None:
        rows = build_comparison_rows(self.a, self.b)
        required = {"Dimension", "Deal A", "Deal B", "\u0394", "Winner"}
        for row in rows:
            self.assertEqual(set(row.keys()), required)

    def test_returns_list_of_dicts(self) -> None:
        rows = build_comparison_rows(self.a, self.b)
        self.assertIsInstance(rows, list)
        for row in rows:
            self.assertIsInstance(row, dict)

    def test_a_wins_overall(self) -> None:
        rows = build_comparison_rows(self.a, self.b)
        self.assertEqual(rows[0]["Winner"], "A \u2713")

    def test_b_wins_overall(self) -> None:
        # Pass self.b as brief_a and self.a as brief_b.
        # self.b has overall=40, self.a has overall=80 → B (self.a) wins.
        rows = build_comparison_rows(self.b, self.a)
        self.assertEqual(rows[0]["Winner"], "B \u2713")

    def test_tie_threshold(self) -> None:
        # delta = 1.0 < _TIE_THRESHOLD=2.0 → tie
        a = _brief(overall=51.0)
        b = _brief(overall=50.0)
        rows = build_comparison_rows(a, b)
        self.assertEqual(rows[0]["Winner"], "—")
        self.assertEqual(rows[0]["\u0394"], "\u2248")

    def test_tie_exactly_at_boundary(self) -> None:
        # delta = _TIE_THRESHOLD exactly → still a tie (strict < used)
        a = _brief(overall=50.0 + _TIE_THRESHOLD)
        b = _brief(overall=50.0)
        rows = build_comparison_rows(a, b)
        # delta == 2.0, abs(delta) < 2.0 is False → should NOT be tie
        self.assertNotEqual(rows[0]["Winner"], "—")

    def test_risk_inversion_a_wins(self) -> None:
        # Brief A has lower risk → A wins risk dimension
        a = _brief(risk_s=20.0)
        b = _brief(risk_s=60.0)
        rows = build_comparison_rows(a, b)
        risk_row = next(r for r in rows if r["Dimension"] == "Risk \u2193")
        self.assertEqual(risk_row["Winner"], "A \u2713")

    def test_risk_inversion_b_wins(self) -> None:
        a = _brief(risk_s=60.0)
        b = _brief(risk_s=20.0)
        rows = build_comparison_rows(a, b)
        risk_row = next(r for r in rows if r["Dimension"] == "Risk \u2193")
        self.assertEqual(risk_row["Winner"], "B \u2713")

    def test_zero_scores_no_crash(self) -> None:
        a = _brief(overall=0, founder_s=0, startup_s=0,
                   market_s=0, trust_s=0, risk_s=0)
        b = _brief(overall=0, founder_s=0, startup_s=0,
                   market_s=0, trust_s=0, risk_s=0)
        rows = build_comparison_rows(a, b)
        self.assertEqual(len(rows), 6)
        for row in rows:
            self.assertEqual(row["Winner"], "—")

    def test_positive_delta_format(self) -> None:
        a = _brief(overall=80.0)
        b = _brief(overall=40.0)
        rows = build_comparison_rows(a, b)
        self.assertTrue(rows[0]["\u0394"].startswith("+"))

    def test_negative_delta_format(self) -> None:
        a = _brief(overall=40.0)
        b = _brief(overall=80.0)
        rows = build_comparison_rows(a, b)
        # Uses en-dash (−), not hyphen (-)
        self.assertTrue(rows[0]["\u0394"].startswith("\u2212"))


class TestBuildWinnerLine(unittest.TestCase):

    def _rows(self, a: InvestmentBrief, b: InvestmentBrief) -> list[dict]:
        return build_comparison_rows(a, b)

    def test_returns_string(self) -> None:
        a = _brief("Alice", "AlphaVenture", overall=80)
        b = _brief("Bob",   "BetaStartup",  overall=40)
        line = build_winner_line(a, b, self._rows(a, b))
        self.assertIsInstance(line, str)

    def test_a_leads_contains_founder_a(self) -> None:
        a = _brief("Alice", "AlphaVenture", overall=80)
        b = _brief("Bob",   "BetaStartup",  overall=40)
        line = build_winner_line(a, b, self._rows(a, b))
        self.assertIn("Alice", line)

    def test_b_leads_contains_founder_b(self) -> None:
        a = _brief("Alice", "AlphaVenture", overall=40)
        b = _brief("Bob",   "BetaStartup",  overall=80)
        line = build_winner_line(a, b, self._rows(a, b))
        self.assertIn("Bob", line)

    def test_tie_language(self) -> None:
        a = _brief(overall=50.0)
        b = _brief(overall=51.0)   # delta=1.0 < threshold → tie
        line = build_winner_line(a, b, self._rows(a, b))
        self.assertIn("evenly matched", line)

    def test_empty_rows_no_crash(self) -> None:
        a = _brief()
        b = _brief()
        line = build_winner_line(a, b, [])
        self.assertIsInstance(line, str)
        self.assertGreater(len(line), 0)

    def test_no_external_imports(self) -> None:
        """Verify comparison.py is a pure module — no LLM or network imports."""
        import kulima.comparison as cmp_mod
        source_file = cmp_mod.__file__ or ""
        with open(source_file, encoding="utf-8") as f:
            source = f.read()
        forbidden = ["openai", "tavily", "streamlit", "requests", "httpx"]
        for token in forbidden:
            self.assertNotIn(
                token, source,
                msg=f"kulima/comparison.py must not import '{token}'",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
