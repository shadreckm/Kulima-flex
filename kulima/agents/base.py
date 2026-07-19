"""Agent base contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from kulima.llm import LLMClient
from kulima.models import AgentResult, SourceAttribution
from kulima.research import ResearchEngine


class BaseAgent(ABC):
    name: str = "base"

    def __init__(
        self,
        llm: LLMClient | None = None,
        research: ResearchEngine | None = None,
    ) -> None:
        self.llm = llm or LLMClient()
        self.research = research or ResearchEngine()

    @abstractmethod
    def run(
        self,
        founder: str,
        startup: str,
        sources: list[SourceAttribution] | None = None,
        context: dict | None = None,
    ) -> AgentResult:
        raise NotImplementedError
