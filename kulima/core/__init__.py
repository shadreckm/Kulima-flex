"""Kulima OS Core namespace.

This module re-exports core platform services and utilities from the existing
Kulima FLEX codebase without moving or modifying their implementations.

Downstream code can begin importing from `kulima.core` while existing imports
from the original modules continue to function.
"""

from kulima.llm import LLMClient
from kulima.research import ResearchEngine
from kulima.evidence_integrity import EvidenceIntegrityEngine
from kulima.trust_graph import TrustGraphEngine

# Scoring utilities
from kulima.scoring import (
    aggregate_agent_score,
    build_explainability,
    clamp,
    confidence_level,
    mean,
    parse_qualitative_score,
    recommendation_from_score,
)

# Base agent framework
from kulima.agents.base import BaseAgent

__all__ = [
    "LLMClient",
    "ResearchEngine",
    "EvidenceIntegrityEngine",
    "TrustGraphEngine",
    # Scoring
    "aggregate_agent_score",
    "build_explainability",
    "clamp",
    "confidence_level",
    "mean",
    "parse_qualitative_score",
    "recommendation_from_score",
    # Agents
    "BaseAgent",
]
