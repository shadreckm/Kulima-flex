"""Kulima FLEX vertical namespace on top of Kulima OS Core.

This module re-exports FLEX-specific orchestrators, agents, engines, and
interfaces from their existing locations so callers can start using the
`kulima.flex` namespace without breaking any existing imports.
"""

# Orchestrator
from kulima.agents.orchestrator import IntelligenceOrchestrator

# Core venture agents
from kulima.agents.founder_agent import FounderIntelligenceAgent
from kulima.agents.startup_agent import StartupIntelligenceAgent
from kulima.agents.diligence_agent import DueDiligenceAgent
from kulima.agents.risk_agent import RiskAssessmentAgent
from kulima.agents.memo_agent import InvestmentMemoAgent

# Thesis Engine
from kulima.thesis import evaluate_thesis_match

# Twin Syndicate (Committee)
from kulima.breakthrough.syndicate import InvestorTwinSyndicate

# Continental Futures Engine
from kulima.breakthrough.futures import ContinentalFuturesEngine

# Ask IC (IC Analyst)
from kulima.ask_ic import build_ask_ic_context, answer_ask_ic_question

__all__ = [
    # Orchestrator
    "IntelligenceOrchestrator",
    # Agents
    "FounderIntelligenceAgent",
    "StartupIntelligenceAgent",
    "DueDiligenceAgent",
    "RiskAssessmentAgent",
    "InvestmentMemoAgent",
    # Thesis
    "evaluate_thesis_match",
    # Syndicate
    "InvestorTwinSyndicate",
    # Futures
    "ContinentalFuturesEngine",
    # Ask IC
    "build_ask_ic_context",
    "answer_ask_ic_question",
]
