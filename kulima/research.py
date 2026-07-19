"""Tavily-powered open-source intelligence research layer."""

from __future__ import annotations

from tavily import TavilyClient

from kulima.config import get_settings
from kulima.models import SourceAttribution


class ResearchEngine:
    """Ex-CIA OSINT style research with Africa-aware query framing."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = TavilyClient(api_key=settings.tavily_api_key)
        self.max_results = settings.max_research_results
        self.africa_focus = settings.africa_focus

    def search(self, query: str, depth: str = "advanced") -> list[SourceAttribution]:
        africa_boost = " Africa startup founder venture funding market" if self.africa_focus else ""
        response = self.client.search(
            query=f"{query}{africa_boost}".strip(),
            search_depth=depth,
            max_results=self.max_results,
        )
        results = response.get("results", []) if isinstance(response, dict) else []
        sources: list[SourceAttribution] = []
        for item in results:
            sources.append(
                SourceAttribution(
                    title=item.get("title") or "Untitled Source",
                    url=item.get("url") or "",
                    snippet=item.get("content") or "",
                    relevance=float(item.get("score") or 0.5),
                    source_type="web",
                )
            )
        return sources

    def research_founder(self, founder: str, startup: str) -> list[SourceAttribution]:
        queries = [
            f"{founder} {startup} founder entrepreneur biography",
            f"{founder} LinkedIn Twitter reputation leadership",
            f"{founder} {startup} funding investment Africa",
        ]
        return self._dedupe(self._multi(queries))

    def research_startup(self, founder: str, startup: str) -> list[SourceAttribution]:
        queries = [
            f"{startup} company product business model Africa",
            f"{startup} competitors market size traction funding",
            f"{startup} {founder} startup launch growth customers",
        ]
        return self._dedupe(self._multi(queries))

    def research_market(self, startup: str, sector_hint: str = "") -> list[SourceAttribution]:
        queries = [
            f"{startup} {sector_hint} Africa market opportunity TAM SAM",
            f"{sector_hint or startup} Africa fintech agritech healthtech competition",
            f"venture capital Africa {sector_hint or startup} trends 2024 2025 2026",
        ]
        return self._dedupe(self._multi(queries))

    def research_risks(self, founder: str, startup: str) -> list[SourceAttribution]:
        queries = [
            f"{founder} {startup} controversy lawsuit scandal fraud",
            f"{startup} regulatory risk compliance Africa",
            f"{startup} failure risk competition shutdown",
        ]
        return self._dedupe(self._multi(queries, depth="basic"))

    def _multi(self, queries: list[str], depth: str = "advanced") -> list[SourceAttribution]:
        """Run Tavily queries in parallel to cut OSINT wall-clock time."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        out: list[SourceAttribution] = []
        if not queries:
            return out

        def _one(q: str) -> list[SourceAttribution]:
            try:
                return self.search(q, depth=depth)
            except Exception:
                return []

        workers = min(4, len(queries))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_one, q) for q in queries]
            for fut in as_completed(futures):
                out.extend(fut.result())
        return out

    def research_bundle(
        self,
        founder: str,
        startup: str,
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

    @staticmethod
    def _dedupe(sources: list[SourceAttribution]) -> list[SourceAttribution]:
        seen: set[str] = set()
        unique: list[SourceAttribution] = []
        for s in sources:
            key = s.url or s.title
            if key in seen:
                continue
            seen.add(key)
            unique.append(s)
        return unique[:12]

    @staticmethod
    def evidence_corpus(sources: list[SourceAttribution], limit: int = 8) -> str:
        chunks: list[str] = []
        for i, s in enumerate(sources[:limit], start=1):
            chunks.append(
                f"[{i}] {s.title}\nURL: {s.url}\nRelevance: {s.relevance:.2f}\n{s.snippet}\n"
            )
        return "\n---\n".join(chunks) if chunks else "No open-source evidence retrieved."
