"""LLM client facade — routed through AIProviderManager (multi-provider).

Business workflows (agents, Ask IC, Ask Signals, memo) keep calling
LLMClient.complete / complete_json unchanged, but every call now runs the
failover chain OpenAI → Groq → OpenRouter → HuggingFace. Provider-specific
logic no longer lives in the business layer (Phase 1).
"""

from __future__ import annotations

import json
import re
from typing import Any

from kulima.config import get_settings
from kulima.providers import AIProviderManager, ProviderExhaustedError, ProviderResult


class LLMClient:
    """Backwards-compatible facade over AIProviderManager."""

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.openai_model
        self._api_key = (api_key or settings.openai_api_key or "").strip()
        self.last_result: ProviderResult | None = None

    @property
    def manager(self) -> AIProviderManager:
        return AIProviderManager.instance()

    @property
    def is_available(self) -> bool:
        return bool(self.manager.chain)

    @property
    def last_provider(self) -> str | None:
        return self.last_result.provider if self.last_result else None

    def complete(self, system: str, user: str, temperature: float = 0.35) -> str:
        result = self.manager._run(system, user, temperature, None)
        self.last_result = result
        return result.text

    def complete_json(self, system: str, user: str, temperature: float = 0.2) -> dict[str, Any]:
        raw = self.complete(
            system=system + "\n\nRespond ONLY with valid JSON. No markdown fences.",
            user=user,
            temperature=temperature,
        )
        return parse_json_payload(raw)


def parse_json_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        return {"data": data}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return {"raw": raw, "parse_error": True}
