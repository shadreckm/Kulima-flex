"""Tavily-powered open-source intelligence research layer."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from tavily import TavilyClient

from kulima.config import get_settings
from kulima.models import SourceAttribution

_HIGH_AUTHORITY_DOMAINS = (
    "crunchbase.com",
    "techcrunch.com",
    "bloomberg.com",
    "reuters.com",
    "ft.com",
    "theinformation.com",
    "linkedin.com",
    "ycombinator.com",
    "cbinsights.com",
    "pitchbook.com",
    "africabusinesscommunities.com",
    "disrupt-africa.com",
    "techcabal.com",
    "restofworld.org",
)
_LOW_SIGNAL_DOMAINS = ("facebook.com", "instagram.com", "tiktok.com", "pinterest.com")


class ResearchEngine:
    """Ex-CIA OSINT style research with Africa-aware query framing."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = TavilyClient(api_key=settings.tavily_api_key)
        self.max_results = settings.max_research_results
        self.africa_focus = settings.africa_focus

    def search(
        self,
        query: str,
        depth: Literal["basic", "advanced", "fast", "ultra-fast"] = "advanced",
    ) -> list[SourceAttribution]:
        africa_boost = (
            " Africa startup founder venture funding market"
            if self.africa_focus
            else ""
        )
        response = self.client.search(
            query=f"{query}{africa_boost}".strip(),
            search_depth=depth,
            max_results=self.max_results,
            include_answer=True,
        )
        results = response.get("results", []) if isinstance(response, dict) else []
        sources: list[SourceAttribution] = []
        for item in results:
            url = item.get("url") or ""
            relevance = float(item.get("score") or 0.5)
            sources.append(
                SourceAttribution(
                    title=item.get("title") or "Untitled Source",
                    url=url,
                    snippet=self._summarize_snippet(item.get("content") or ""),
                    relevance=relevance,
                    source_type=self._source_type(url),
                    confidence_score=self._confidence_score(url, relevance),
                )
            )
        return self._rank_sources(sources)

    def research_founder(self, founder: str, startup: str) -> list[SourceAttribution]:
        queries = [
            f"{founder} {startup} founder entrepreneur biography funding",
            f"{founder} LinkedIn X Twitter reputation leadership previous companies",
            f"{founder} {startup} investor announcement interview Africa",
            f"{founder} {startup} awards accelerator board profile",
        ]
        return self._dedupe(self._multi(queries))

    def research_startup(self, founder: str, startup: str) -> list[SourceAttribution]:
        queries = [
            f"{startup} company product business model customers Africa",
            f"{startup} competitors market size traction revenue funding",
            f"{startup} {founder} startup launch growth customers",
            f"{startup} funding round investors valuation Africa",
        ]
        return self._dedupe(self._multi(queries))

    def research_market(
        self, startup: str, sector_hint: str = ""
    ) -> list[SourceAttribution]:
        queries = [
            f"{startup} {sector_hint} Africa market opportunity TAM SAM regulation",
            f"{sector_hint or startup} Africa fintech agritech healthtech competition market size",
            f"venture capital Africa {sector_hint or startup} trends 2024 2025 2026",
            f"Africa {sector_hint or startup} incumbents regulatory tailwinds customer adoption",
        ]
        return self._dedupe(self._multi(queries))

    def research_risks(self, founder: str, startup: str) -> list[SourceAttribution]:
        queries = [
            f"{founder} {startup} controversy lawsuit scandal fraud",
            f"{startup} regulatory risk compliance Africa license complaint",
            f"{startup} failure risk competition shutdown layoffs",
            f"{startup} security incident data breach customer complaints",
        ]
        return self._dedupe(self._multi(queries, depth="basic"))

    def _multi(
        self,
        queries: list[str],
        depth: Literal["basic", "advanced", "fast", "ultra-fast"] = "advanced",
    ) -> list[SourceAttribution]:
        """Run Tavily queries in parallel to cut OSINT wall-clock time."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not queries:
            return []

        def _one(q: str) -> list[SourceAttribution]:
            try:
                return self.search(q, depth=depth)
            except Exception:
                return []

        out: list[SourceAttribution] = []
        with ThreadPoolExecutor(max_workers=min(4, len(queries))) as pool:
            for fut in as_completed([pool.submit(_one, q) for q in queries]):
                out.extend(fut.result())
        return self._rank_sources(self._dedupe(out, limit=24))

    def research_bundle(
        self, founder: str, startup: str
    ) -> dict[str, list[SourceAttribution]]:
        """One-shot parallel OSINT pack: founder, startup, market, risks."""
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=4) as pool:
            f_fut = pool.submit(self.research_founder, founder, startup)
            s_fut = pool.submit(self.research_startup, founder, startup)
            m_fut = pool.submit(self.research_market, startup)
            r_fut = pool.submit(self.research_risks, founder, startup)
            return {
                "founder": f_fut.result(),
                "startup": s_fut.result(),
                "market": m_fut.result(),
                "risks": r_fut.result(),
            }

    @classmethod
    def _rank_sources(cls, sources: list[SourceAttribution]) -> list[SourceAttribution]:
        return sorted(
            sources, key=lambda s: (s.confidence_score, s.relevance), reverse=True
        )

    @classmethod
    def _dedupe(
        cls, sources: list[SourceAttribution], limit: int = 12
    ) -> list[SourceAttribution]:
        seen: set[str] = set()
        unique: list[SourceAttribution] = []
        for s in cls._rank_sources(sources):
            parsed = urlparse(s.url.lower())
            key = (
                (parsed.netloc.replace("www.", ""), parsed.path.rstrip("/"))
                if s.url
                else ("title", s.title.lower())
            )
            key_s = "|".join(key)
            if key_s in seen:
                continue
            seen.add(key_s)
            unique.append(s)
        return unique[:limit]

    @staticmethod
    def _domain(url: str) -> str:
        return urlparse(url.lower()).netloc.replace("www.", "")

    @classmethod
    def _source_type(cls, url: str) -> str:
        domain = cls._domain(url)
        if "linkedin.com" in domain:
            return "professional_profile"
        if any(d in domain for d in _HIGH_AUTHORITY_DOMAINS):
            return "high_authority_web"
        if any(d in domain for d in _LOW_SIGNAL_DOMAINS):
            return "social_low_signal"
        return "web"

    @classmethod
    def _confidence_score(cls, url: str, relevance: float) -> float:
        domain = cls._domain(url)
        boost = 0.18 if any(d in domain for d in _HIGH_AUTHORITY_DOMAINS) else 0.0
        penalty = -0.12 if any(d in domain for d in _LOW_SIGNAL_DOMAINS) else 0.0
        return max(0.05, min(0.98, relevance * 0.72 + 0.18 + boost + penalty))

    @staticmethod
    def _summarize_snippet(snippet: str, max_chars: int = 520) -> str:
        compact = " ".join((snippet or "").split())
        return compact[:max_chars].rstrip() + ("…" if len(compact) > max_chars else "")

    @staticmethod
    def evidence_corpus(sources: list[SourceAttribution], limit: int = 8) -> str:
        chunks: list[str] = []
        for i, s in enumerate(ResearchEngine._rank_sources(sources)[:limit], start=1):
            chunks.append(
                f"[{i}] {s.title}\nURL: {s.url}\nType: {s.source_type}\n"
                f"Relevance: {s.relevance:.2f}\nConfidence: {s.confidence_score:.2f}\nSummary: {s.snippet}\n"
            )
        return (
            "\n---\n".join(chunks) if chunks else "No open-source evidence retrieved."
        )
