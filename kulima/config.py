"""Central configuration for Kulima FLEX VC Brain."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Twin Syndicate must use this model for hackathon demo quality
SYNDICATE_MODEL = os.getenv("SYNDICATE_MODEL", "gpt-4.1-mini")
FUTURES_MODEL = os.getenv("FUTURES_MODEL", "gpt-4.1-mini")


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    tavily_api_key: str
    openai_model: str
    db_path: str
    max_research_results: int
    africa_focus: bool
    access_mode: str
    guest_daily_limit: int
    analyst_daily_limit: int
    investor_daily_limit: int
    admin_emails: tuple[str, ...]

    def missing_required_secrets(self) -> list[str]:
        missing = []
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if not self.tavily_api_key:
            missing.append("TAVILY_API_KEY")
        return missing

    def pilot_access_summary(self) -> dict[str, object]:
        return {
            "guest_access": self.access_mode in {"guest", "pilot", "open"},
            "authenticated_access": self.access_mode in {"pilot", "authenticated"},
            "guest_daily_limit": self.guest_daily_limit,
            "analyst_daily_limit": self.analyst_daily_limit,
            "investor_daily_limit": self.investor_daily_limit,
            "admin_controls": bool(self.admin_emails),
        }


def get_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        db_path=os.getenv("KULIMA_DB_PATH", "founders.db"),
        max_research_results=int(os.getenv("MAX_RESEARCH_RESULTS", "8")),
        africa_focus=os.getenv("AFRICA_FOCUS", "true").lower() == "true",
        access_mode=os.getenv("KULIMA_ACCESS_MODE", "pilot").lower(),
        guest_daily_limit=int(os.getenv("KULIMA_GUEST_DAILY_LIMIT", "3")),
        analyst_daily_limit=int(os.getenv("KULIMA_ANALYST_DAILY_LIMIT", "25")),
        investor_daily_limit=int(os.getenv("KULIMA_INVESTOR_DAILY_LIMIT", "10")),
        admin_emails=tuple(
            email.strip().lower()
            for email in os.getenv("KULIMA_ADMIN_EMAILS", "").split(",")
            if email.strip()
        ),
    )


AFRICA_MARKETS = [
    "Nigeria",
    "Kenya",
    "South Africa",
    "Egypt",
    "Ghana",
    "Rwanda",
    "Senegal",
    "Côte d'Ivoire",
    "Morocco",
    "Ethiopia",
    "Tanzania",
    "Uganda",
    "Malawi",
    "Zambia",
]

INVESTOR_ARCHETYPES = [
    {
        "id": "african_vc",
        "name": "Amina Okonkwo",
        "title": "African VC Partner",
        "firm": "Sahel Horizon Ventures",
        "persona": "African VC Partner",
        "bias": "Founder-market fit, mobile-first distribution, unit economics under FX stress, continental expansion realism",
        "check_size": "$250K–$1.5M",
        "style": "Aggressive on talent density; ruthless on capital efficiency in hard markets",
    },
    {
        "id": "diaspora_angel",
        "name": "Fatima Diallo",
        "title": "Diaspora Angel Investor",
        "firm": "Lagos–London Angel Network",
        "persona": "Diaspora Angel Investor",
        "bias": "Founder grit, community trust, remittance corridors, authentic local insight, operator credibility",
        "check_size": "$25K–$150K",
        "style": "Conviction-led; bets on people who have survived hard markets",
    },
    {
        "id": "dfi_officer",
        "name": "James Mwangi-Reed",
        "title": "Development Finance Institution Officer",
        "firm": "Continental Development Partners",
        "persona": "Development Finance Institution Officer",
        "bias": "Additionality, gender lens, climate co-benefits, governance, job creation, developmental impact",
        "check_size": "$1M–$5M",
        "style": "Patient capital; high bar on compliance, safeguards, and impact measurement",
    },
    {
        "id": "cvc_investor",
        "name": "Thabo Nkosi",
        "title": "Corporate Venture Capital Investor",
        "firm": "AfriTel Corporate Ventures",
        "persona": "Corporate Venture Capital Investor",
        "bias": "Distribution synergies, regulatory adjacency, platform attach rates, strategic optionality",
        "check_size": "$500K–$3M",
        "style": "Strategic fit over pure financial return; needs a clear corporate pathway",
    },
    {
        "id": "global_tier1",
        "name": "Elena Vargas",
        "title": "Global Tier-1 VC Partner",
        "firm": "Atlantic Bridge Capital",
        "persona": "Global Tier-1 VC Partner",
        "bias": "Category creation, expandable TAM, repeatable GTM, path to Series B, global comps",
        "check_size": "$3M–$12M",
        "style": "Benchmarks against global winners; discounts Africa risk only with proof",
    },
]
