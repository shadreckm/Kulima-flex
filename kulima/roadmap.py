"""Architecture audit, roadmap, and judging narrative — see README.md for the full brief.

This module exists so judges/reviewers can `import kulima.roadmap` in notebooks
or print the prioritized backlog programmatically.
"""

from __future__ import annotations

AUDIT = {
    "legacy_problems": [
        "Monolithic Streamlit script with heuristic scoring",
        "Single Tavily query + single GPT call",
        "No agent separation, no explainability, no Africa thesis",
        "Hardcoded API keys in test/MCP configs",
        "No investor-grade communication structure",
    ],
    "transformed_into": "Multi-agent AI Investment Intelligence OS for Africa",
}

IMMEDIATE_FEATURES = [
    "Founder / Startup / Diligence / Risk / Memo agents",
    "Trust graph + digital footprint",
    "Kulima Twin Syndicate (breakthrough)",
    "Continental Futures Engine",
    "Executive dashboard + DNA scorecard",
    "Source attribution + explainability",
    "IC memo sections + next steps",
]

POST_HACKATHON = [
    "Pitch deck / data room ingestion",
    "PDF IC pack export",
    "Async parallel agents",
    "CRM sync (Affinity/Attio)",
    "Multilingual OSINT",
    "Portfolio heatmaps + LP reporting",
    "Fine-tuned Africa founder success model",
]

ROADMAP = {
    "P0": "Hackathon demo OS (shipped)",
    "P1": "Perf, PDF export, sector taxonomies, OSINT cache",
    "P2": "Fund pilot: primary data + calibration",
    "P3": "Multi-tenant SaaS + API",
}


def print_roadmap() -> None:
    print("Kulima FLEX Roadmap")
    for k, v in ROADMAP.items():
        print(f"  {k}: {v}")
    print("\nImmediate:")
    for f in IMMEDIATE_FEATURES:
        print(f"  - {f}")
    print("\nPost-hackathon:")
    for f in POST_HACKATHON:
        print(f"  - {f}")


if __name__ == "__main__":
    print_roadmap()
