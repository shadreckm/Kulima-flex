"""AIProviderManager — multi-provider LLM abstraction (Phases 1 & 2).

Single entry point for every LLM call in Kulima FLEX. Business workflows
never talk to a specific provider; they call generate()/chat()/summarize()/
classify()/extract()/research() and the manager resolves the provider chain:

    Tier 1  OpenAI        (OPENAI_API_KEY)
    Tier 2  Groq          (GROQ_API_KEY)        — OpenAI-compatible endpoint
    Tier 3  Gemini        (GEMINI_API_KEY)      — Google OpenAI-compatible endpoint
    Tier 4  OpenRouter    (OPENROUTER_API_KEY)  — OpenAI-compatible endpoint
    Tier 5  HuggingFace   (HUGGINGFACE_API_KEY) — Router / Inference API
    Tier 6  Document Intelligence Mode (caller-supplied fallback)

Failures (invalid key, quota, timeout, network, outage) trigger automatic
failover to the next tier — no user intervention. Every call reports which
provider served it for observability (Phase 10).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

from openai import OpenAI

from kulima.config import get_settings

_log = logging.getLogger(__name__)

# Base URLs for OpenAI wire-compatible providers.
_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    # Official Google Gemini OpenAI-compatible endpoint.
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openrouter": "https://openrouter.ai/api/v1",
    "huggingface": os.getenv("HUGGINGFACE_BASE_URL", "https://router.huggingface.co/v1"),
}

# Fallback default model per provider.
_FALLBACK_MODEL = {
    "openai": "gpt-4.1-mini",
    "groq": "openai/gpt-oss-120b",
    "gemini": "gemini-3.8-flash",
    "openrouter": "openrouter/auto",
    "huggingface": "meta-llama/Llama-3.1-8B-Instruct",
}

# Gemini model ladder: preferred tier first, degraded tier on failover or
# lightweight tasks. Google deprecates 2.x models for new API keys, so the
# current generation is used and any configured GEMINI_MODEL is honoured.
_GEMINI_LADDER = {
    "gemini-2.5-pro": "gemini-3.1-pro-preview",
    "gemini-2.5-flash": "gemini-3.8-flash",
}

# Phase 4 Groq preferred model aliases
_GROQ_ALIASES = {
    "llama": "llama-3.3-70b-versatile",
    "qwen": "qwen-2.5-32b",
    "gpt-oss-120b": "openai/gpt-oss-120b",
}


@dataclass
class ProviderResult:
    """Outcome of one generation, with observability metadata (Phase 10)."""

    text: str
    provider: str
    model: str
    fallback_triggered: bool
    fallback_count: int
    response_time: float
    analysis_mode: str
    errors: list[dict[str, str]] = field(default_factory=list)


class ProviderExhaustedError(RuntimeError):
    """All configured providers failed; caller should use Document Intelligence Mode."""


class AIProviderManager:
    """Resolve LLM calls across the provider chain with automatic failover."""

    _instance: "AIProviderManager | None" = None

    def __init__(self) -> None:
        settings = get_settings()
        self.timeout = settings.llm_timeout_seconds
        self._keys = {
            "openai": settings.openai_api_key,
            "groq": settings.groq_api_key,
            "gemini": settings.gemini_api_key,
            "openrouter": settings.openrouter_api_key,
            "huggingface": settings.huggingface_api_key,
        }
        self._models = {
            "openai": settings.openai_model,
            "groq": settings.groq_model,
            "gemini": settings.gemini_model,
            "openrouter": settings.openrouter_model,
            "huggingface": settings.huggingface_model,
        }
        self._groq_reasoning_model = settings.groq_reasoning_model
        self._groq_preferred_models = settings.groq_preferred_models
        self._openrouter_free_model = settings.openrouter_free_model
        self._disabled_providers: set[str] = set()
        order = settings.provider_order or ("openai", "groq", "gemini", "openrouter", "huggingface")
        # Keep only tiers that have keys, in the configured order.
        self._configured_order: list[str] = [p for p in order if self._keys.get(p)]
        self._clients: dict[str, OpenAI] = {}
        self.last_result: Optional[ProviderResult] = None

    @classmethod
    def instance(cls) -> "AIProviderManager":
        if cls._instance is None:
            cls._instance = AIProviderManager()
        return cls._instance

    @property
    def chain(self) -> list[str]:
        """Active provider chain respecting dynamically disabled providers."""
        return [p for p in self._configured_order if p not in self._disabled_providers]

    # ── Testing / Phase 12 validation control ─────────────────────────────

    def disable_provider(self, provider: str) -> None:
        """Temporarily disable a provider for outage/failover simulation."""
        self._disabled_providers.add(provider.lower().strip())

    def enable_provider(self, provider: str) -> None:
        self._disabled_providers.discard(provider.lower().strip())

    def set_disabled_providers(self, providers: Sequence[str]) -> None:
        self._disabled_providers = {p.lower().strip() for p in providers}

    def reset_providers(self) -> None:
        """Clear disabled providers and reload keys."""
        self._disabled_providers.clear()
        settings = get_settings()
        self._keys = {
            "openai": settings.openai_api_key,
            "groq": settings.groq_api_key,
            "gemini": settings.gemini_api_key,
            "openrouter": settings.openrouter_api_key,
            "huggingface": settings.huggingface_api_key,
        }
        order = settings.provider_order or ("openai", "groq", "gemini", "openrouter", "huggingface")
        self._configured_order = [p for p in order if self._keys.get(p)]

    # ── Public API (Phase 1) ──────────────────────────────────────────────

    def generate(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.35,
        task: str | None = None,
        on_provider: Callable[[str], None] | None = None,
    ) -> str:
        """Single-turn generation (replaces LLMClient.complete)."""
        result = self._run(system, user, temperature, on_provider, task=task)
        return result.text

    def chat(
        self,
        system: str,
        user: str,
        history: list[dict] | None = None,
        *,
        temperature: float = 0.2,
        task: str | None = None,
        on_provider: Callable[[str], None] | None = None,
    ) -> str:
        """Multi-turn chat (Ask AI Analyst)."""
        result = self._run(system, user, temperature, on_provider, history=history, task=task)
        return result.text

    def summarize(self, system: str, user: str, **kw: Any) -> str:
        """Phase 6/8: Summarization tasks."""
        return self.generate(system, user, temperature=0.2, task="summarize", **kw)

    def classify(self, system: str, user: str, **kw: Any) -> str:
        """Phase 6: Classification tasks."""
        return self.generate(system, user, temperature=0.0, task="classify", **kw)

    def extract(self, system: str, user: str, **kw: Any) -> str:
        """Phase 6: Entity extraction tasks."""
        return self.generate(system, user, temperature=0.1, task="extract", **kw)

    def research(self, system: str, user: str, **kw: Any) -> str:
        """Analytical synthesis over collected sources."""
        return self.generate(system, user, temperature=0.3, task="research", **kw)

    @staticmethod
    def research_fallback_summary(
        documents: list[dict],
        assessment_context: dict | None,
        signals: list[str],
        evidence: list[str],
        trust_score: float | None,
    ) -> str:
        """Phase 8: research findings without Tavily/LLM — built from the
        uploaded documents, assessment context, signals, evidence and trust."""
        lines: list[str] = []
        if assessment_context:
            org = assessment_context.get("organizationName") or assessment_context.get("displayEntity")
            sector = assessment_context.get("sector")
            country = assessment_context.get("country")
            if org:
                lines.append(f"Subject: {org}" + (f" ({sector}, {country})" if sector or country else ""))
            intelligence = (assessment_context.get("extraction") or {}).get("intelligence") or {}
            for key, label in (
                ("objectives", "Objectives"),
                ("activities", "Activities"),
                ("outcomes", "Outcomes"),
                ("locations", "Locations"),
                ("budget_references", "Budget"),
                ("risks", "Risks"),
            ):
                items = intelligence.get(key) or []
                if items:
                    lines.append(f"{label}: " + "; ".join(str(i) for i in items[:5]))
        if documents:
            names = ", ".join(str(d.get("name") or "document") for d in documents[:5])
            lines.append(f"Evidence base: {len(documents)} uploaded document(s) — {names}")
        if evidence:
            lines.append("Key evidence items: " + "; ".join(str(e) for e in evidence[:5]))
        if trust_score is not None:
            lines.append(f"Trust score: {trust_score:.0f}/100")
        if signals:
            lines.append("Signals: " + "; ".join(str(s) for s in signals[:5]))
        if not lines:
            return "Document Intelligence Mode active — upload additional documents to expand evidence."
        return "Document Intelligence findings: " + " | ".join(lines)

    # ── Wire-level execution with failover (Phase 2) ──────────────────────

    def _client_for(self, provider: str) -> OpenAI:
        if provider not in self._clients:
            base_url = _BASE_URLS.get(provider)  # openai uses default
            timeout = self.timeout if provider not in ("huggingface", "gemini") else min(self.timeout, 30)
            self._clients[provider] = OpenAI(
                api_key=self._keys[provider],
                base_url=base_url,
                timeout=timeout,
                max_retries=0,
            )
        return self._clients[provider]

    def _model_for(self, provider: str, task: str | None = None, *, prefer_free: bool = False, fallback_count: int = 0) -> str:
        # Phase 4: Groq model resolution and preferred models
        if provider == "groq":
            groq_model = self._models.get("groq") or _FALLBACK_MODEL["groq"]
            # Check aliases
            if groq_model.lower() in _GROQ_ALIASES:
                groq_model = _GROQ_ALIASES[groq_model.lower()]
            # Specific reasoning tasks for Groq
            if task in (
                "reasoning",
                "investment_analysis",
                "ngo_evaluation",
                "tourism_assessment",
                "decision_generation",
            ):
                return self._groq_reasoning_model or groq_model
            return groq_model

        # Gemini: flash tier on failover / lightweight tasks; 2.x model names
        # requested by config are mapped to the current Google generation.
        if provider == "gemini":
            model = self._models.get("gemini") or _FALLBACK_MODEL["gemini"]
            model = _GEMINI_LADDER.get(model, model)
            if fallback_count > 0 or task in ("classify", "extract", "summarize"):
                model = _GEMINI_LADDER.get(model, model)
                model = model.replace("gemini-3.1-pro-preview", "gemini-3.8-flash").replace(
                    "gemini-2.5-pro", "gemini-2.5-flash"
                )
            return model

        # Phase 5: OpenRouter model resolution
        if provider == "openrouter":
            if prefer_free or task == "emergency":
                return self._openrouter_free_model or "openrouter/free"
            return self._models.get("openrouter") or _FALLBACK_MODEL["openrouter"]

        # Phase 6: HuggingFace model resolution
        if provider == "huggingface":
            return self._models.get("huggingface") or _FALLBACK_MODEL["huggingface"]

        return self._models.get(provider) or _FALLBACK_MODEL.get(provider, "")

    def _run(
        self,
        system: str,
        user: str,
        temperature: float,
        on_provider: Callable[[str], None] | None = None,
        history: list[dict] | None = None,
        *,
        task: str | None = None,
        prefer_free: bool = False,
    ) -> ProviderResult:
        started = time.perf_counter()
        errors: list[dict[str, str]] = []
        fallback_count = 0
        last_provider = "none"

        active_chain = self.chain
        if not active_chain:
            raise ProviderExhaustedError("All providers exhausted (no active providers configured).")

        for provider in active_chain:
            last_provider = provider
            try:
                # If falling back to OpenRouter, allow emergency free/reasoning model
                is_emergency = fallback_count >= 2 and provider == "openrouter"
                model = self._model_for(
                    provider,
                    task=task,
                    prefer_free=prefer_free or is_emergency,
                )
                messages: list[dict[str, str]] = [{"role": "system", "content": system}]
                if history:
                    messages.extend(history[-8:])
                messages.append({"role": "user", "content": user})
                client = self._client_for(provider)
                extra: dict[str, Any] = {}
                if provider == "openrouter":
                    extra["extra_headers"] = {
                        "HTTP-Referer": "https://kulima-flex.app",
                        "X-Title": "Kulima FLEX",
                    }
                if provider == "gemini":
                    # Gemini ignores unknown sampling params silently; keep the
                    # request minimal for maximum compatibility.
                    extra["max_tokens"] = None
                    extra = {k: v for k, v in extra.items() if v is not None}
                response = client.chat.completions.create(
                    model=model,
                    temperature=temperature,
                    messages=messages,
                    **extra,
                )
                text = (response.choices[0].message.content or "").strip()
                if not text:
                    raise ValueError("empty response")
                result = ProviderResult(
                    text=text,
                    provider=provider,
                    model=model,
                    fallback_triggered=fallback_count > 0,
                    fallback_count=fallback_count,
                    response_time=time.perf_counter() - started,
                    analysis_mode="ai_assisted",
                    errors=errors,
                )
                self.last_result = result
                if on_provider:
                    try:
                        on_provider(provider)
                    except Exception:  # noqa: BLE001
                        pass
                # Phase 10 Observability logging
                _log.info(
                    "llm_call_served",
                    extra={
                        "providerUsed": provider,
                        "model": model,
                        "fallbackTriggered": fallback_count > 0,
                        "fallbackCount": fallback_count,
                        "analysisMode": "ai_assisted",
                        "responseTime": result.response_time,
                    },
                )
                return result
            except Exception as exc:  # noqa: BLE001 — failover on any failure
                kind = self._classify_error(exc)
                errors.append({"provider": provider, "errorType": kind, "message": str(exc)[:200]})
                _log.warning(
                    "provider_failover",
                    extra={
                        "providerUsed": provider,
                        "errorType": kind,
                        "fallbackCount": fallback_count + 1,
                        "analysisMode": "ai_assisted",
                    },
                )
                fallback_count += 1
                continue

        raise ProviderExhaustedError(
            f"All providers exhausted ({last_provider} last). Errors: {errors}"
        )

    @staticmethod
    def _classify_error(exc: Exception) -> str:
        name = type(exc).__name__.lower()
        message = str(exc).lower()
        status = getattr(exc, "status_code", None)
        if status == 429 or "quota" in message or "rate_limit" in message:
            return "quota_exceeded"
        if status == 401 or "auth" in name or "api key" in message or "unauthorized" in message:
            return "invalid_key"
        if "timeout" in name or "timed out" in message:
            return "timeout"
        if "connect" in name or "network" in message:
            return "network_failure"
        return "provider_outage"

    # ── Health / observability (Phase 10) ─────────────────────────────────

    def status(self) -> dict[str, Any]:
        provider_rows: list[dict[str, Any]] = []
        for p in ("openai", "groq", "gemini", "openrouter", "huggingface"):
            provider_rows.append(
                {
                    "provider": p,
                    "configured": bool(self._keys.get(p)),
                    "enabled": p in self.chain,
                    "available": bool(self._keys.get(p)) and p not in self._disabled_providers,
                }
            )
        return {
            "providers": provider_rows,
            "chain": list(self.chain),
            "configuredChain": list(self._configured_order),
            "disabledProviders": list(self._disabled_providers),
            "lastProviderUsed": self.last_result.provider if self.last_result else None,
            "lastFallbackTriggered": self.last_result.fallback_triggered if self.last_result else None,
            "lastFallbackCount": self.last_result.fallback_count if self.last_result else None,
            "lastResponseTime": self.last_result.response_time if self.last_result else None,
            "analysisMode": self.last_result.analysis_mode if self.last_result else "document_intelligence",
            "errors": self.last_result.errors if self.last_result else [],
        }
