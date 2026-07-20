"""
Verify PipelineStageError propagation and dimension validation logic.
Uses lightweight mocks — no real LLM calls or Tavily requests.
"""
import sys, types, unittest
from unittest.mock import MagicMock, patch

# ── Stub heavy optional dependencies so tests run without them ─────────────
for mod in ["networkx", "tavily", "reportlab", "reportlab.lib",
            "reportlab.lib.pagesizes", "reportlab.lib.styles",
            "reportlab.lib.colors", "reportlab.lib.units",
            "reportlab.platypus", "reportlab.platypus.frames",
            "plotly", "plotly.graph_objects", "streamlit"]:
    if mod not in sys.modules:
        sys.modules[mod] = types.ModuleType(mod)

# ── now safe to import project code ───────────────────────────────────────
from kulima.errors import PipelineStageError
from kulima.models import AgentResult, ScoreDimension, SourceAttribution
from kulima.scoring import clamp

_DUMMY_SRC = SourceAttribution(title="t", url="http://x", snippet="s", relevance=0.5)

def _make_dim(name, score=55.0):
    return ScoreDimension(name=name, score=score, rationale="test", confidence=0.6)


class TestPipelineStageError(unittest.TestCase):
    def test_stage_stored(self):
        err = PipelineStageError(stage="Risk Assessment Agent", message="test")
        self.assertEqual(err.stage, "Risk Assessment Agent")
        self.assertIn("Risk Assessment Agent", str(err))

    def test_cause_chained(self):
        cause = ValueError("bad value")
        err = PipelineStageError(stage="Founder Intelligence Agent", message="LLM failed", cause=cause)
        self.assertIn("ValueError", str(err))
        self.assertIs(err.cause, cause)


class TestFounderDimensionValidation(unittest.TestCase):
    """Inline simulation of the validation logic from founder_agent.py."""

    REQUIRED = {"Credibility", "Leadership", "Digital Footprint", "Reputation", "Domain Expertise"}

    def _validate(self, scores):
        canonical_map = {d.lower(): d for d in self.REQUIRED}
        for s in scores:
            if s.name.lower() in canonical_map:
                s.name = canonical_map[s.name.lower()]
        returned = {s.name for s in scores}
        missing = self.REQUIRED - returned
        if missing:
            raise PipelineStageError(
                stage="Founder Intelligence Agent",
                message=f"Missing: {', '.join(missing)}"
            )
        return scores

    def test_all_dims_present(self):
        scores = [_make_dim(d) for d in self.REQUIRED]
        result = self._validate(scores)
        self.assertEqual({s.name for s in result}, self.REQUIRED)

    def test_missing_dim_raises(self):
        scores = [_make_dim("Credibility"), _make_dim("Leadership")]
        with self.assertRaises(PipelineStageError) as ctx:
            self._validate(scores)
        self.assertIn("Founder Intelligence Agent", ctx.exception.stage)

    def test_case_insensitive_canonical(self):
        scores = [_make_dim(d.lower()) for d in self.REQUIRED]
        result = self._validate(scores)
        self.assertEqual({s.name for s in result}, self.REQUIRED)


class TestRiskDimensionValidation(unittest.TestCase):
    REQUIRED = {
        "Execution Risk", "Market Risk", "Regulatory Risk", "FX Macro Risk",
        "Key Person Risk", "Competitive Risk", "Reputational Risk", "Capital Risk",
    }

    def _validate(self, scores):
        canonical_map = {d.lower(): d for d in self.REQUIRED}
        for s in scores:
            if s.name.lower() in canonical_map:
                s.name = canonical_map[s.name.lower()]
        missing = self.REQUIRED - {s.name for s in scores}
        if missing:
            raise PipelineStageError(
                stage="Risk Assessment Agent",
                message=f"Missing: {', '.join(missing)}"
            )
        return scores

    def test_all_dims_pass(self):
        scores = [_make_dim(d) for d in self.REQUIRED]
        self._validate(scores)  # should not raise

    def test_partial_dims_fail(self):
        scores = [_make_dim("Market Risk")]
        with self.assertRaises(PipelineStageError):
            self._validate(scores)


class TestStartupDimensionValidation(unittest.TestCase):
    REQUIRED = {
        "Market Opportunity", "Competitive Position",
        "Business Model", "Growth Potential", "Investment Readiness",
    }

    def _validate(self, scores):
        canonical_map = {d.lower(): d for d in self.REQUIRED}
        for s in scores:
            if s.name.lower() in canonical_map:
                s.name = canonical_map[s.name.lower()]
        missing = self.REQUIRED - {s.name for s in scores}
        if missing:
            raise PipelineStageError(
                stage="Startup Intelligence Agent",
                message=f"Missing: {', '.join(missing)}"
            )
        return scores

    def test_all_dims_pass(self):
        scores = [_make_dim(d) for d in self.REQUIRED]
        self._validate(scores)

    def test_missing_readiness_fails(self):
        scores = [_make_dim(d) for d in self.REQUIRED if d != "Investment Readiness"]
        with self.assertRaises(PipelineStageError) as ctx:
            self._validate(scores)
        self.assertIn("Investment Readiness", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
