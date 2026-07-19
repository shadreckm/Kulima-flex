"""Quick Tavily OSINT connectivity check for Kulima FLEX."""

from dotenv import load_dotenv

from kulima.research import ResearchEngine

load_dotenv()

if __name__ == "__main__":
    engine = ResearchEngine()
    try:
        results = engine.search("African venture capital startup funding 2026", depth="basic")
        print(f"SUCCESS — {len(results)} sources")
        for r in results[:3]:
            print(f"- {r.title}: {r.url}")
    except Exception as exc:
        print("ERROR:")
        print(exc)
