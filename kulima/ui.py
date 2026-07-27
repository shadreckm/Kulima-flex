"""Executive dashboard UI helpers — visual scorecards & charts."""

from __future__ import annotations

import html
import textwrap
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from kulima.models import InvestmentBrief, Recommendation

REC_COLORS = {
    Recommendation.INVEST: "#0B6E4F",
    Recommendation.CO_INVEST: "#1B9AAA",
    Recommendation.OBSERVE: "#B8892D",
    Recommendation.FOLLOW_ON_WATCH: "#D97706",
    Recommendation.PASS: "#9B2226",
}

# ── Score thresholds ──────────────────────────────────────────────────────────
_STRONG = 75
_MID = 55

# ── Score metric tooltips (Phase 3) ──────────────────────────────────────────
_SCORE_HELP = {
    "Overall": (
        "Composite conviction score (0–100). Weighted average across Founder, Startup, "
        "Market, Trust, and Risk dimensions. ≥75 = strong conviction."
    ),
    "Founder": (
        "Founder credibility & leadership score (0–100). Assesses track record, domain "
        "expertise, execution history, and leadership capability."
    ),
    "Startup": (
        "Startup business model & readiness score (0–100). Covers product-market fit, "
        "revenue model viability, team composition, and traction signals."
    ),
    "Market": (
        "Africa market opportunity score (0–100). Evaluates addressable market size, "
        "growth trajectory, competitive intensity, and regulatory environment."
    ),
    "Trust": (
        "Trust & network footprint score (0–100). Maps ecosystem presence, quality of "
        "partnerships, investor references, and network density."
    ),
    "Risk": (
        "Aggregate risk score (0–100). Lower is better — a score of 20 means low risk. "
        "Factors in execution, regulatory, market, and reputational risks."
    ),
}


def _tone(score: float, invert: bool = False) -> str:
    """Return a CSS class name encoding green / amber / red signal."""
    value = 100 - score if invert else score
    if value >= _STRONG:
        return "tone-strong"
    if value >= _MID:
        return "tone-mid"
    return "tone-weak"


def _delta_color(score: float, invert: bool = False) -> str:
    """Return Streamlit delta_color string for st.metric."""
    value = 100 - score if invert else score
    if value >= _STRONG:
        return "normal"   # green
    if value >= _MID:
        return "off"      # grey/amber (neutral)
    return "inverse"      # red


def inject_styles() -> None:
    st.markdown(textwrap.dedent("""
        <style>
        /* ── Phase 1: Hide all Streamlit chrome ───────────────────────────── */
        #MainMenu {visibility: hidden !important; display: none !important;}
        footer {visibility: hidden !important; display: none !important;}
        header {visibility: hidden !important;}
        /* Deploy / Share button — multiple selector fallbacks for Streamlit versions */
        .stDeployButton {display: none !important;}
        [data-testid="stDeployButton"] {display: none !important;}
        [data-testid="stToolbar"] {display: none !important;}
        [data-testid="manage-app-button"] {display: none !important;}
        button[title="View app in Streamlit Community Cloud"] {display:none!important;}
        button[title="Deploy this app"] {display:none!important;}

        /* ── Phase 5: Typography ──────────────────────────────────────────── */
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;700&family=Source+Sans+3:wght@400;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Source Sans 3', -apple-system, "Segoe UI", system-ui, sans-serif;
            font-size: 15px;
            line-height: 1.65;
        }
        h1, h2, h3, h4, .kulima-brand {
            font-family: 'Fraunces', Georgia, serif !important;
            letter-spacing: -0.02em;
        }
        p, li, label, span {
            line-height: 1.65;
        }

        /* ── Background ───────────────────────────────────────────────────── */
        .stApp {
            background:
                radial-gradient(1100px 520px at 8% -8%, rgba(11,110,79,0.20), transparent 55%),
                radial-gradient(900px 480px at 100% 0%, rgba(184,137,45,0.14), transparent 48%),
                linear-gradient(180deg, #F4F7F4 0%, #EEF3EF 42%, #E8EEE9 100%);
        }

        /* ── Sidebar ──────────────────────────────────────────────────────── */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0B3D2E 0%, #0F4A38 55%, #123F32 100%);
        }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] strong,
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
            color: #F3F7F4 !important;
        }
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div {
            color: #E2EBE5;
        }
        [data-testid="stSidebar"] code {
            background-color: rgba(255, 255, 255, 0.15) !important;
            color: #FFFFFF !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            padding: 0.1rem 0.3rem !important;
            border-radius: 4px !important;
        }
        [data-testid="stSidebar"] .stCaptionContainer p,
        [data-testid="stSidebar"] caption,
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            color: #D7E3DC !important;
        }
        [data-testid="stSidebar"] [data-testid="stAlert"] * {
            color: inherit !important;
        }
        [data-testid="stSidebar"] .stButton > button {
            background: #C4A35A !important;
            color: #0B3D2E !important;
            border: none !important;
            font-weight: 700 !important;
            border-radius: 12px !important;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.25);
        }

        /* ── Input fields ─────────────────────────────────────────────────── */
        .stTextInput input, textarea, [data-baseweb="input"] input {
            background: #FFFFFF !important;
            border: 1px solid rgba(11,61,46,0.24) !important;
            color: #10251C !important;
            caret-color: #0B6E4F !important;
            -webkit-text-fill-color: #10251C !important;
        }
        .stTextInput input::placeholder, textarea::placeholder {
            color: #5B6F64 !important;
            opacity: 1 !important;
        }
        [data-testid="stSidebar"] .stTextInput input {
            background: #F8FBF8 !important;
            border: 1px solid rgba(255,255,255,0.45) !important;
            color: #10251C !important;
            caret-color: #0B6E4F !important;
            -webkit-text-fill-color: #10251C !important;
        }
        [data-testid="stSidebar"] .stTextInput input::placeholder {
            color: #496055 !important;
            opacity: 1 !important;
        }
        [data-testid="stSidebar"] .stTextInput input::-webkit-input-placeholder { color: #496055 !important; }
        [data-testid="stSidebar"] .stTextInput input::-moz-placeholder { color: #496055 !important; opacity: 1 !important; }

        /* ── Layout ───────────────────────────────────────────────────────── */
        .block-container {
            padding-top: 1.4rem;
            max-width: 1280px;
        }

        /* ── Hero ─────────────────────────────────────────────────────────── */
        .kulima-hero {
            padding: 0.4rem 0 1rem 0;
            animation: fadeRise 0.55s ease-out;
        }
        .kulima-brand {
            font-size: 2.75rem;
            font-weight: 700;
            color: #0B3D2E;
            letter-spacing: -0.03em;
            margin: 0;
            line-height: 1.05;
        }
        .kulima-sub {
            color: #3F5A4E;
            font-size: 1.08rem;
            margin-top: 0.4rem;
        }
        .hero-pills {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-top: 0.85rem;
        }
        .hero-pill {
            background: rgba(11,61,46,0.08);
            border: 1px solid rgba(11,61,46,0.12);
            color: #0B3D2E;
            border-radius: 999px;
            padding: 0.28rem 0.75rem;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.02em;
        }

        /* ── Dashboard shell ──────────────────────────────────────────────── */
        .dashboard-shell {
            background: rgba(255,255,255,0.66);
            border: 1px solid rgba(11,61,46,0.10);
            border-radius: 22px;
            padding: 1.15rem 1.25rem 1.3rem;
            box-shadow: 0 18px 40px rgba(11,61,46,0.07);
            backdrop-filter: blur(8px);
            animation: fadeRise 0.6s ease-out;
            margin-bottom: 1rem;
        }
        .dashboard-kicker {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #5B6F64;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }

        /* ── Score chips ──────────────────────────────────────────────────── */
        .score-chip {
            background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(241,247,243,0.92));
            border: 1px solid rgba(11, 61, 46, 0.10);
            border-radius: 16px;
            padding: 0.95rem 1rem 0.85rem;
            margin-bottom: 0.55rem;
            box-shadow: 0 8px 18px rgba(11,61,46,0.05);
            position: relative;
            overflow: hidden;
            transition: transform 0.18s ease, box-shadow 0.18s ease;
            animation: fadeRise 0.5s ease-out;
            cursor: help;
        }
        .score-chip:hover {
            transform: translateY(-2px);
            box-shadow: 0 14px 28px rgba(11,61,46,0.10);
        }
        .score-chip::before {
            content: "";
            position: absolute;
            left: 0; top: 0; bottom: 0;
            width: 4px;
            border-radius: 4px 0 0 4px;
        }
        /* Phase 3: Green / Amber / Red accent bars */
        .score-chip.tone-strong::before { background: #0B6E4F; }
        .score-chip.tone-mid::before    { background: #B8892D; }
        .score-chip.tone-weak::before   { background: #9B2226; }
        .score-chip.tone-strong { border-color: rgba(11,110,79,0.28); }
        .score-chip.tone-mid    { border-color: rgba(184,137,45,0.28); }
        .score-chip.tone-weak   { border-color: rgba(155,34,38,0.28); }
        /* Phase 3: Tinted badge in top-right corner */
        .score-chip.tone-strong::after { content: "●"; position:absolute; top:0.55rem; right:0.65rem; font-size:0.55rem; color:#0B6E4F; opacity:0.7; }
        .score-chip.tone-mid::after    { content: "●"; position:absolute; top:0.55rem; right:0.65rem; font-size:0.55rem; color:#B8892D; opacity:0.7; }
        .score-chip.tone-weak::after   { content: "●"; position:absolute; top:0.55rem; right:0.65rem; font-size:0.55rem; color:#9B2226; opacity:0.7; }
        .score-chip .label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            color: #5B6F64;
            font-weight: 700;
        }
        .score-chip .value {
            font-family: Fraunces, Georgia, serif;
            font-size: 2rem;
            color: #0B3D2E;
            font-weight: 700;
            line-height: 1.1;
            margin-top: 0.2rem;
        }
        .score-chip .hint {
            font-size: 0.72rem;
            color: #6A7F74;
            margin-top: 0.15rem;
        }
        /* Phase 3: colour the numeric value to match tone */
        .score-chip.tone-strong .value { color: #0B6E4F; }
        .score-chip.tone-mid .value    { color: #8C6820; }
        .score-chip.tone-weak .value   { color: #9B2226; }

        /* ── Recommendation banner ────────────────────────────────────────── */
        .rec-banner {
            border-radius: 18px;
            padding: 1.15rem 1.35rem;
            color: white;
            font-family: Fraunces, Georgia, serif;
            font-size: 1.4rem;
            font-weight: 700;
            margin: 0.35rem 0 1rem 0;
            box-shadow: 0 14px 30px rgba(11,61,46,0.18);
            animation: fadeRise 0.45s ease-out;
        }
        .rec-banner .sub {
            display: block;
            font-family: 'Source Sans 3', sans-serif;
            font-size: 0.88rem;
            font-weight: 500;
            opacity: 0.92;
            margin-top: 0.35rem;
        }

        /* ── Success / archive banners ────────────────────────────────────── */
        .success-banner {
            background: linear-gradient(135deg, #0B6E4F, #147A58);
            color: white;
            border-radius: 16px;
            padding: 0.95rem 1.15rem;
            margin: 0.4rem 0 1rem 0;
            box-shadow: 0 12px 28px rgba(11,110,79,0.22);
            animation: pulseGlow 1.8s ease-in-out infinite;
        }
        .success-banner strong {
            font-family: Fraunces, Georgia, serif;
            font-size: 1.15rem;
        }

        /* ── Empty state ──────────────────────────────────────────────────── */
        .empty-state {
            background: rgba(255,255,255,0.7);
            border: 1px dashed rgba(11,61,46,0.22);
            border-radius: 20px;
            padding: 1.6rem 1.5rem;
            margin-top: 0.5rem;
        }
        .empty-state h3 {
            color: #0B3D2E;
            margin-top: 0;
        }
        .empty-state ol li {
            margin-bottom: 0.35rem;
        }

        /* ── Pipeline progress ────────────────────────────────────────────── */
        .pipeline-card {
            background: rgba(255,255,255,0.78);
            border-radius: 16px;
            border: 1px solid rgba(11,61,46,0.10);
            padding: 1rem 1.1rem;
            margin: 0.6rem 0 1rem 0;
        }
        .pipeline-step {
            display: flex;
            align-items: center;
            gap: 0.65rem;
            padding: 0.35rem 0;
            color: #2F453B;
            font-size: 0.92rem;
        }
        .pipeline-dot {
            width: 10px; height: 10px; border-radius: 50%;
            background: #0B6E4F;
            box-shadow: 0 0 0 0 rgba(11,110,79,0.45);
            animation: pulseDot 1.4s infinite;
            flex-shrink: 0;
        }

        /* ── Red flag alerts ──────────────────────────────────────────────── */
        .flag-critical { border-left: 4px solid #9B2226; background: rgba(155,34,38,0.04); padding: 0.65rem 0.8rem; border-radius: 0 8px 8px 0; margin: 0.5rem 0; }
        .flag-high     { border-left: 4px solid #D97706; background: rgba(217,119,6,0.04);  padding: 0.65rem 0.8rem; border-radius: 0 8px 8px 0; margin: 0.5rem 0; }
        .flag-medium   { border-left: 4px solid #C4A35A; background: rgba(196,163,90,0.04); padding: 0.65rem 0.8rem; border-radius: 0 8px 8px 0; margin: 0.5rem 0; }
        .flag-low      { border-left: 4px solid #1B9AAA; background: rgba(27,154,170,0.04);  padding: 0.65rem 0.8rem; border-radius: 0 8px 8px 0; margin: 0.5rem 0; }

        /* ── Futures cards ────────────────────────────────────────────────── */
        .futures-card {
            background: rgba(255,255,255,0.82);
            border: 1px solid rgba(11, 61, 46, 0.12);
            border-radius: 18px;
            padding: 1.15rem 1.2rem 1.25rem;
            min-height: 420px;
            box-shadow: 0 10px 28px rgba(11, 61, 46, 0.06);
            margin-bottom: 0.8rem;
            transition: transform 0.18s ease;
        }
        .futures-card:hover { transform: translateY(-3px); }
        .futures-card.bull { border-top: 4px solid #0B6E4F; }
        .futures-card.base { border-top: 4px solid #1B9AAA; }
        .futures-card.bear { border-top: 4px solid #9B2226; }
        .futures-card h3 {
            font-family: Fraunces, Georgia, serif !important;
            color: #0B3D2E;
            margin: 0 0 0.75rem 0;
            font-size: 1.35rem;
        }
        .futures-metric-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #5B6F64;
            margin-top: 0.65rem;
            font-weight: 700;
        }
        .futures-metric-value {
            font-family: Fraunces, Georgia, serif;
            font-size: 1.45rem;
            font-weight: 700;
            color: #0B3D2E;
        }
        .futures-body {
            color: #2F453B;
            font-size: 0.95rem;
            line-height: 1.55;
            margin: 0.35rem 0 0.2rem 0;
        }

        /* ── Section card ─────────────────────────────────────────────────── */
        .section-card {
            background: rgba(255,255,255,0.72);
            border: 1px solid rgba(11,61,46,0.10);
            border-radius: 18px;
            padding: 1rem 1.15rem;
            margin: 0.6rem 0 1rem 0;
            line-height: 1.65;
        }

        /* ── Phase 2: Debate persona cards ───────────────────────────────── */
        .persona-card {
            background: rgba(255,255,255,0.78);
            border: 1px solid rgba(11,61,46,0.12);
            border-radius: 16px;
            padding: 1rem 1.15rem;
            margin-bottom: 0.75rem;
            box-shadow: 0 6px 16px rgba(11,61,46,0.05);
            transition: transform 0.15s ease;
        }
        .persona-card:hover { transform: translateY(-2px); }
        .persona-card.vote-invest    { border-left: 5px solid #0B6E4F; }
        .persona-card.vote-coinvest  { border-left: 5px solid #1B9AAA; }
        .persona-card.vote-observe   { border-left: 5px solid #B8892D; }
        .persona-card.vote-watch     { border-left: 5px solid #D97706; }
        .persona-card.vote-pass      { border-left: 5px solid #9B2226; }
        .persona-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 0.55rem;
        }
        .persona-name {
            font-family: Fraunces, Georgia, serif;
            font-size: 1.05rem;
            font-weight: 700;
            color: #0B3D2E;
        }
        .persona-firm {
            font-size: 0.82rem;
            color: #5B6F64;
            margin-top: 0.1rem;
        }
        .persona-badge {
            display: inline-block;
            padding: 0.2rem 0.65rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            white-space: nowrap;
        }
        .badge-invest    { background: #D1F0E3; color: #0B6E4F; }
        .badge-coinvest  { background: #D1EEF5; color: #1B9AAA; }
        .badge-observe   { background: #FFF0D0; color: #8C6820; }
        .badge-watch     { background: #FEF0CC; color: #B55D00; }
        .badge-pass      { background: #FADADD; color: #9B2226; }
        .persona-reasoning { font-size: 0.92rem; color: #2F453B; line-height: 1.55; }
        .persona-concern {
            margin-top: 0.5rem;
            background: rgba(217,119,6,0.06);
            border-left: 3px solid #D97706;
            padding: 0.4rem 0.7rem;
            border-radius: 0 6px 6px 0;
            font-size: 0.88rem;
            color: #5B3800;
        }

        /* ── Tabs ─────────────────────────────────────────────────────────── */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.25rem;
            overflow-x: auto;
            border-bottom: 2px solid rgba(11,61,46,0.10);
        }
        .stTabs [data-baseweb="tab"] {
            color: #0B3D2E !important;
            font-weight: 700;
            white-space: nowrap;
            border-radius: 8px 8px 0 0;
            padding: 0.55rem 1rem;
        }
        .stTabs [aria-selected="true"] {
            background: rgba(11,61,46,0.07) !important;
        }

        /* ── Alerts ───────────────────────────────────────────────────────── */
        [data-testid="stAlert"] {
            color: #10251C !important;
        }
        [data-testid="stAlert"] * {
            color: inherit !important;
        }

        /* ── Progress bars ────────────────────────────────────────────────── */
        div[data-testid="stProgressBar"] > div {
            background: linear-gradient(90deg, #0B6E4F, #1B9AAA) !important;
        }

        /* ── Metric value font ────────────────────────────────────────────── */
        div[data-testid="stMetricValue"] {
            font-family: Fraunces, Georgia, serif;
        }

        /* ── Export section ───────────────────────────────────────────────── */
        .export-group {
            background: rgba(255,255,255,0.72);
            border: 1px solid rgba(11,61,46,0.10);
            border-radius: 16px;
            padding: 1rem 1.1rem 1.2rem;
            margin-bottom: 0.6rem;
        }
        .export-group-title {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            color: #5B6F64;
            font-weight: 700;
            margin-bottom: 0.55rem;
        }

        /* ── Phase 5: Dark mode ───────────────────────────────────────────── */
        @media (prefers-color-scheme: dark) {
            .stApp {
                background: linear-gradient(180deg, #071F18 0%, #0B2D22 100%);
                color: #EDF6F0;
            }
            .kulima-brand, .empty-state h3, .futures-card h3, .futures-metric-value {
                color: #F3F7F4 !important;
            }
            /* Score chip values: keep tone colour in dark mode */
            .score-chip.tone-strong .value { color: #4CC99A !important; }
            .score-chip.tone-mid .value    { color: #D4A840 !important; }
            .score-chip.tone-weak .value   { color: #E06670 !important; }
            .kulima-sub, .score-chip .label, .score-chip .hint, .dashboard-kicker,
            .futures-metric-label, .futures-body { color: #D7E3DC !important; }
            .dashboard-shell, .section-card, .empty-state, .score-chip,
            .futures-card, .pipeline-card, .persona-card, .export-group {
                background: rgba(13, 43, 33, 0.90) !important;
                border-color: rgba(215, 227, 220, 0.20) !important;
            }
            .stTextInput input, textarea, [data-baseweb="input"] input {
                background: #F8FBF8 !important;
                color: #10251C !important;
                -webkit-text-fill-color: #10251C !important;
            }
            .stTabs [data-baseweb="tab"] { color: #F3F7F4 !important; }
            .persona-name { color: #F3F7F4 !important; }
            .persona-reasoning { color: #D7E3DC !important; }
        }

        /* ══════════════════════════════════════════════════════════════════
           RESPONSIVE — mobile-first, three breakpoints
           320–767 px  : phone
           768–1023 px : tablet
           1024 px+    : laptop / desktop (base styles above)
           ══════════════════════════════════════════════════════════════════ */

        /* ── Global overflow guard — prevents horizontal scroll everywhere ── */
        html, body, .stApp, .block-container,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stVerticalBlock"] {
            overflow-x: hidden !important;
            max-width: 100% !important;
        }
        /* All direct children of column blocks must stay in bounds */
        [data-testid="stColumn"] > div,
        [data-testid="stHorizontalBlock"] > div {
            min-width: 0 !important;
            word-break: break-word;
        }

        /* ── Text overflow safety for all prose elements ─────────────────── */
        p, li, span, div, td, th, label {
            overflow-wrap: break-word;
            word-wrap: break-word;
        }

        /* ── Score chips — responsive grid ──────────────────────────────── */
        /* Desktop: natural 6-column layout via st.columns(6)               */
        /* Tablet : 3 columns, 2 rows                                        */
        /* Phone  : 2 columns, 3 rows                                        */
        .score-chip-grid {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 0.5rem;
            width: 100%;
        }

        /* ── Futures cards — flex-wrap on smaller viewports ─────────────── */
        .futures-cards-row {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
        }
        .futures-cards-row .futures-card {
            flex: 1 1 280px;
            min-width: 0;
        }

        /* ── Persona-card header: allow badge to wrap below name on mobile ─ */
        .persona-header {
            flex-wrap: wrap;
            gap: 0.4rem;
        }
        .persona-badge {
            max-width: 100%;
            white-space: normal;
            word-break: break-word;
        }

        /* ── Recommendation banner: ensure text wraps, never overflows ───── */
        .rec-banner {
            word-break: break-word;
            overflow-wrap: break-word;
        }
        .rec-banner .sub {
            white-space: normal;
            word-break: break-word;
        }

        /* ── Trust Layer — reliability badge & card ──────────────────────── */
        .reliability-badge {
            display: inline-flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.25rem;
            white-space: normal !important;
            word-break: break-word;
            max-width: 100%;
        }
        .reliability-card {
            word-break: break-word;
            overflow-wrap: break-word;
        }
        /* Contradiction rows — long descriptions always wrap */
        .conflict-row-critical,
        .conflict-row-high,
        .conflict-row-medium {
            word-break: break-word;
            overflow-wrap: break-word;
            white-space: normal;
        }

        /* ── Tabs — horizontal scroll without page overflow ─────────────── */
        .stTabs [data-baseweb="tab-list"] {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            scrollbar-width: thin;
            flex-wrap: nowrap;
            padding-bottom: 2px;
        }
        .stTabs [data-baseweb="tab"] {
            flex-shrink: 0;
        }

        /* ── Data tables / dataframes — horizontal scroll in container ───── */
        [data-testid="stDataFrame"],
        .stDataFrame,
        [data-testid="data_editor"] {
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch;
            max-width: 100% !important;
        }

        /* ── Chat messages — stay in bounds ─────────────────────────────── */
        [data-testid="stChatMessage"] {
            max-width: 100% !important;
            overflow-wrap: break-word;
        }

        /* ── Sidebar — safe minimum width, don't block content ──────────── */
        [data-testid="stSidebar"] {
            min-width: 220px !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            overflow-x: hidden !important;
            word-break: break-word;
        }

        /* ── Export buttons — always stack below ~500 px ─────────────────── */
        .export-mobile-stack {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            width: 100%;
        }

        /* ══════════════════════════════════════════════════════════════════
           TABLET  768 – 1023 px
           ══════════════════════════════════════════════════════════════════ */
        @media (max-width: 1023px) {
            .block-container {
                padding-top: 1rem;
                max-width: 100%;
            }
            .futures-card { min-height: unset; }
            .score-chip-grid { grid-template-columns: repeat(3, 1fr); }
        }

        /* ══════════════════════════════════════════════════════════════════
           PHONE  320 – 767 px
           ══════════════════════════════════════════════════════════════════ */
        @media (max-width: 767px) {
            /* Layout */
            .block-container {
                padding: 0.75rem 0.6rem 2.5rem !important;
                max-width: 100% !important;
            }

            /* Hero */
            .kulima-brand  { font-size: 1.85rem; }
            .kulima-sub    { font-size: 0.95rem; }
            .hero-pills    { gap: 0.25rem; }
            .hero-pill     { font-size: 0.7rem; padding: 0.2rem 0.55rem; }

            /* Recommendation banner */
            .rec-banner {
                font-size: 1rem !important;
                padding: 0.85rem 0.9rem !important;
                border-radius: 14px !important;
                line-height: 1.4 !important;
            }
            .rec-banner .sub { font-size: 0.8rem; }

            /* Score chips */
            .score-chip-grid { grid-template-columns: repeat(2, 1fr); }
            .score-chip { padding: 0.75rem 0.7rem 0.65rem; margin-bottom: 0; }
            .score-chip .value { font-size: 1.55rem; }
            .score-chip .label { font-size: 0.68rem; }
            .score-chip .hint  { font-size: 0.68rem; }

            /* Futures cards — full width stack */
            .futures-cards-row { flex-direction: column; }
            .futures-cards-row .futures-card { flex: 1 1 100%; }
            .futures-card { min-height: unset; padding: 0.9rem 1rem 1rem; }
            .futures-metric-value { font-size: 1.25rem; }

            /* Persona cards */
            .persona-card { padding: 0.75rem 0.85rem; }
            .persona-name { font-size: 0.95rem; }
            .persona-firm { font-size: 0.78rem; }
            .persona-reasoning { font-size: 0.88rem; }
            .persona-concern { font-size: 0.84rem; }

            /* Success / archive banners */
            .success-banner { padding: 0.8rem 0.9rem; font-size: 0.9rem; }

            /* Dashboard shell */
            .dashboard-shell { padding: 0.85rem 0.85rem 1rem; border-radius: 16px; }

            /* Trust Layer card */
            .reliability-card { padding: 0.7rem 0.8rem; }

            /* Section card */
            .section-card { padding: 0.8rem 0.9rem; border-radius: 14px; }

            /* Export groups */
            .export-group { padding: 0.8rem 0.9rem 1rem; }

            /* Tabs — smaller padding */
            .stTabs [data-baseweb="tab"] {
                padding: 0.4rem 0.7rem;
                font-size: 0.82rem;
            }

            /* Pipeline card */
            .pipeline-card { padding: 0.75rem 0.9rem; }
            .pipeline-step { font-size: 0.88rem; }

            /* st.metric — shrink on phone */
            [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
            [data-testid="stMetricLabel"] { font-size: 0.78rem !important; }
            [data-testid="stMetricDelta"] { font-size: 0.72rem !important; }
        }

        /* ══════════════════════════════════════════════════════════════════
           VERY SMALL PHONE  320 – 400 px  (Galaxy S8, iPhone SE)
           ══════════════════════════════════════════════════════════════════ */
        @media (max-width: 400px) {
            .kulima-brand { font-size: 1.6rem; }
            .rec-banner   { font-size: 0.9rem !important; }
            .score-chip .value { font-size: 1.35rem; }
            .futures-metric-value { font-size: 1.1rem; }
            /* Single column score chips on 320 px */
            .score-chip-grid { grid-template-columns: repeat(2, 1fr); }
            .stTabs [data-baseweb="tab"] {
                padding: 0.32rem 0.55rem;
                font-size: 0.76rem;
            }
        }

        /* ── Dark mode — trust layer components ──────────────────────────── */
        @media (prefers-color-scheme: dark) {
            .reliability-card {
                background: rgba(13,43,33,0.88) !important;
                border-color: rgba(215,227,220,0.18) !important;
            }
            .conflict-row-critical,
            .conflict-row-high,
            .conflict-row-medium {
                background: rgba(255,255,255,0.04) !important;
            }
            .verification-checklist li::before { color: #A0B4AC; }
        }

        /* ── Ask IC — suggested prompt buttons wrap on narrow viewports ──── */
        [data-testid="stButton"] > button {
            min-width: 0 !important;
            white-space: normal !important;
            word-break: break-word;
            height: auto !important;
            text-align: left;
        }

        /* ── Chart columns — stack to full width below 640 px ───────────── */
        @media (max-width: 640px) {
            [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
            }
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                min-width: 100% !important;
                width: 100% !important;
                flex: 1 1 100% !important;
            }
        }

        /* ── Trust Layer Reliability Card — 3-col → 1-col below 480 px ──── */
        @media (max-width: 480px) {
            div[data-reliability-grid=""] {
                grid-template-columns: 1fr !important;
            }
        }

        /* ── Floating Ask IC — FAB + right-side drawer ──────────────────── */
        .ask-ic-fab-wrapper {
            position: fixed;
            bottom: 1.5rem;
            right: 1.5rem;
            z-index: 9999;
            display: block;
        }
        .ask-ic-fab-wrapper button,
        div[data-testid="stVerticalBlock"] > div[data-testid="stButton"] > button.ask-ic-fab-btn {
            border-radius: 9999px !important;
            background: #0B3D2E !important;
            color: #FFFFFF !important;
            border: none !important;
            box-shadow: 0 10px 28px rgba(11,61,46,0.32), 0 2px 6px rgba(0,0,0,0.18) !important;
            padding: 0.7rem 1.05rem !important;
            font-weight: 700 !important;
            font-family: 'Source Sans 3', sans-serif !important;
            font-size: 0.92rem !important;
            letter-spacing: 0.01em !important;
            min-width: 56px !important;
            min-height: 56px !important;
            transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease !important;
        }
        .ask-ic-fab-wrapper button:hover,
        div[data-testid="stVerticalBlock"] > div[data-testid="stButton"] > button.ask-ic-fab-btn:hover {
            background: #0F4A38 !important;
            transform: translateY(-2px);
            box-shadow: 0 14px 36px rgba(11,61,46,0.42), 0 4px 10px rgba(0,0,0,0.22) !important;
        }
        .ask-ic-fab-wrapper button:active {
            transform: translateY(0) scale(0.98);
        }

        /* Drawer shell */
        .ask-ic-drawer-shell {
            position: fixed;
            top: 0;
            right: 0;
            height: 100vh;
            width: min(440px, 92vw);
            background: rgba(252,253,252,0.985);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-left: 1px solid rgba(0,0,0,0.08);
            box-shadow: -20px 0 60px rgba(0,0,0,0.18);
            z-index: 9998;
            display: flex;
            flex-direction: column;
            transform: translateX(100%);
            transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .ask-ic-drawer-shell.open {
            transform: translateX(0%);
        }
        /* Tablet breakpoint (769-1024): 60vw */
        @media (min-width: 769px) and (max-width: 1024px) {
            .ask-ic-drawer-shell { width: 60vw !important; }
        }
        /* Mobile breakpoint (≤768px): 100vw */
        @media (max-width: 768px) {
            .ask-ic-drawer-shell {
                width: 100vw !important;
                right: 0 !important;
                left: 0 !important;
                border-left: none !important;
                border-bottom: none !important;
            }
            .ask-ic-fab-wrapper {
                bottom: 1rem;
                right: 1rem;
            }
            .ask-ic-fab-wrapper button {
                min-width: 56px;
                min-height: 56px;
                padding: 0.7rem 0.9rem !important;
            }
        }
        /* Drawer header */
        .ask-ic-drawer-header {
            flex: 0 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.9rem 1rem 0.7rem 1.05rem;
            border-bottom: 1px solid rgba(0,0,0,0.07);
            background: linear-gradient(180deg, rgba(11,61,46,0.03), transparent);
        }
        .ask-ic-drawer-title {
            font-family: 'Fraunces', Georgia, serif;
            font-weight: 700;
            font-size: 1.08rem;
            color: #0B3D2E;
            letter-spacing: -0.01em;
        }
        .ask-ic-close-btn button {
            background: transparent !important;
            border: 1px solid rgba(0,0,0,0.10) !important;
            color: #5B6F64 !important;
            border-radius: 8px !important;
            padding: 0.25rem 0.5rem !important;
            font-weight: 700 !important;
            font-size: 0.82rem !important;
            line-height: 1 !important;
            min-height: 0 !important;
        }
        .ask-ic-close-btn button:hover {
            background: rgba(0,0,0,0.04) !important;
            color: #0B3D2E !important;
        }
        /* Drawer body (holds compact panel content): flex-fill scrollable */
        .ask-ic-drawer-body {
            flex: 1 1 auto;
            min-height: 0;
            padding: 0.6rem 0.9rem 0.25rem 1rem;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
        }
        /* Desktop overlay when drawer is open */
        .ask-ic-backdrop {
            position: fixed;
            inset: 0;
            background: rgba(7, 31, 24, 0.35);
            backdrop-filter: blur(2px);
            z-index: 9997;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.25s ease;
        }
        .ask-ic-backdrop.open {
            opacity: 1;
            pointer-events: auto;
        }

        @keyframes fadeRise {
            from { opacity: 0; transform: translateY(8px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulseGlow {
            0%,100% { box-shadow: 0 12px 28px rgba(11,110,79,0.18); }
            50%      { box-shadow: 0 16px 36px rgba(11,110,79,0.32); }
        }
        @keyframes pulseDot {
            0%   { box-shadow: 0 0 0 0   rgba(11,110,79,0.45); }
            70%  { box-shadow: 0 0 0 10px rgba(11,110,79,0); }
            100% { box-shadow: 0 0 0 0   rgba(11,110,79,0); }
        }
        /* ── Trust Layer / Evidence Integrity ────────────────────────────── */
        .reliability-badge { display: inline-flex; align-items: center; gap: 0.35rem; }
        .reliability-badge-A { border-color: rgba(11,110,79,0.30) !important; }
        .reliability-badge-B { border-color: rgba(45,138,107,0.30) !important; }
        .reliability-badge-C { border-color: rgba(184,137,45,0.30) !important; }
        .reliability-badge-D { border-color: rgba(217,119,6,0.30) !important; }
        .reliability-badge-F { border-color: rgba(155,34,38,0.30) !important; }
        .reliability-card {
            background: rgba(255,255,255,0.75);
            border: 1px solid rgba(11,61,46,0.10);
            border-radius: 16px;
            padding: 0.9rem 1rem;
            margin: 0.4rem 0 0.8rem;
        }
        .depth-dots { font-family: monospace; letter-spacing: 0.05em; }
        .consistency-band {
            height: 6px;
            border-radius: 3px;
            background: linear-gradient(90deg, #0B6E4F, #D97706);
        }
        .conflict-row-critical { border-left: 3px solid #9B2226; background: rgba(155,34,38,0.03); padding: 0.3rem 0.6rem; border-radius: 0 6px 6px 0; margin: 0.25rem 0; }
        .conflict-row-high     { border-left: 3px solid #D97706; background: rgba(217,119,6,0.03);  padding: 0.3rem 0.6rem; border-radius: 0 6px 6px 0; margin: 0.25rem 0; }
        .conflict-row-medium   { border-left: 3px solid #B8892D; background: rgba(184,137,45,0.03); padding: 0.3rem 0.6rem; border-radius: 0 6px 6px 0; margin: 0.25rem 0; }
        .verification-checklist { list-style: none; padding: 0; margin: 0.3rem 0; }
        .verification-checklist li::before { content: "☐ "; font-size: 0.9rem; color: #5B6F64; }

        @media (prefers-color-scheme: dark) {
            .reliability-card { background: rgba(13,43,33,0.88) !important; border-color: rgba(215,227,220,0.18) !important; }
        }
        """), unsafe_allow_html=True)


def render_hero() -> None:
    st.markdown(textwrap.dedent("""
        <div class="kulima-hero">
            <p class="kulima-brand">Kulima FLEX</p>
            <p class="kulima-sub">AI Investment Intelligence Operating System for Africa</p>
            <div class="hero-pills">
                <span class="hero-pill">Multi-Agent Diligence</span>
                <span class="hero-pill">Twin Syndicate IC</span>
                <span class="hero-pill">Continental Futures</span>
                <span class="hero-pill">Founder Memory</span>
                <span class="hero-pill">IC Memo Export</span>
            </div>
        </div>
        """), unsafe_allow_html=True)


def render_empty_state() -> None:
    st.markdown(textwrap.dedent("""
        <div class="empty-state">
            <h3>Executive IC Workspace</h3>
            <p>Enter a founder and startup in the sidebar, then run full intelligence.
            Kulima FLEX will research, score, convene the Twin Syndicate, simulate African
            market futures, and produce an IC-ready memo pack.</p>
            <ol>
              <li>OSINT research across founder &amp; startup signals</li>
              <li>Five specialized agents underwrite the deal</li>
              <li>Twin Syndicate votes Invest / Observe / Pass</li>
              <li>Continental Futures maps Bull / Base / Bear</li>
              <li>Export memo + full committee report</li>
            </ol>
        </div>
        """), unsafe_allow_html=True)


def render_success_banner(brief: InvestmentBrief) -> None:
    flags = len(brief.red_flags)
    st.markdown(textwrap.dedent(f"""
        <div class="success-banner">
            <strong>Analysis complete</strong><br/>
            {html.escape(brief.founder_name)} / {html.escape(brief.startup_name)}
            &nbsp;·&nbsp; Recommendation <b>{html.escape(brief.recommendation.value)}</b>
            &nbsp;·&nbsp; Overall {brief.overall_score:.0f}/100
            &nbsp;·&nbsp; {flags} red flag{"s" if flags != 1 else ""} reviewed
        </div>
        """), unsafe_allow_html=True)


def render_recommendation_banner(brief: InvestmentBrief) -> None:
    color = REC_COLORS.get(brief.recommendation, "#0B3D2E")
    syn = ""
    if brief.syndicate:
        final = brief.syndicate.final_recommendation or brief.syndicate.majority_vote
        syn = (
            f"Syndicate {final.value} · Consensus "
            f"{(brief.syndicate.consensus_score or brief.syndicate.average_score):.0f}/100"
        )
    st.markdown(textwrap.dedent(f"""
        <div class="rec-banner" style="background:{color};">
            IC Recommendation: {html.escape(brief.recommendation.value)}
            &nbsp;·&nbsp; Conviction {html.escape(brief.confidence_level.value)}
            &nbsp;·&nbsp; Overall {brief.overall_score:.0f}/100
            <span class="sub">{html.escape(syn) if syn else "Partner-grade diligence complete"}</span>
        </div>
        """), unsafe_allow_html=True)


def render_score_row(brief: InvestmentBrief) -> None:
    """
    Phase 2/3: Executive scorecard.

    HTML chips are rendered in a CSS grid (.score-chip-grid) that reflows
    automatically: 6 columns on desktop, 3 on tablet, 2 on phone.
    Each chip carries a native ``title`` attribute for screen readers and
    mouse-hover tooltips, matching the Phase 3 help strings.
    """
    st.markdown(
        '<div class="dashboard-kicker">Executive Scorecard</div>',
        unsafe_allow_html=True,
    )

    metrics = [
        ("Overall", brief.overall_score,  False, "Composite conviction", _SCORE_HELP["Overall"]),
        ("Founder", brief.founder_score,  False, "Credibility &amp; leadership", _SCORE_HELP["Founder"]),
        ("Startup", brief.startup_score,  False, "Model &amp; readiness", _SCORE_HELP["Startup"]),
        ("Market",  brief.market_score,   False, "Africa opportunity",   _SCORE_HELP["Market"]),
        ("Trust",   brief.trust_score,    False, "Footprint &amp; network", _SCORE_HELP["Trust"]),
        ("Risk ↓",  brief.risk_score,     True,  "Lower is better",      _SCORE_HELP["Risk"]),
    ]

    chips_html = '<div class="score-chip-grid">'
    for label, value, invert, hint, tooltip in metrics:
        chips_html += (
            f'<div class="score-chip {_tone(value, invert=invert)}"'
            f' title="{html.escape(tooltip)}">'
            f'<div class="label">{label}</div>'
            f'<div class="value">{value:.0f}</div>'
            f'<div class="hint">{hint}</div>'
            f'</div>'
        )
    chips_html += '</div>'
    st.markdown(chips_html, unsafe_allow_html=True)


def render_dashboard_shell_open() -> None:
    st.markdown('<div class="dashboard-shell">', unsafe_allow_html=True)
    st.markdown(
        '<div class="dashboard-kicker">Investment Committee Dashboard</div>',
        unsafe_allow_html=True,
    )


def render_dashboard_shell_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def radar_figure(brief: InvestmentBrief) -> go.Figure:
    categories = [
        "Founder",
        "Startup",
        "Market",
        "Trust",
        "Growth",
        "Readiness",
        "Risk Inverse",
    ]
    values = [
        brief.founder_score,
        brief.startup_score,
        brief.market_score,
        brief.trust_score,
        brief.growth_potential,
        brief.investment_readiness,
        max(0, 100 - brief.risk_score),
    ]
    fig = go.Figure(
        data=go.Scatterpolar(
            r=values + [values[0]],
            theta=categories + [categories[0]],
            fill="toself",
            line=dict(color="#0B6E4F", width=2.5),
            fillcolor="rgba(11,110,79,0.28)",
            name="Deal DNA",
        )
    )
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(255,255,255,0.45)",
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                showticklabels=False,
                gridcolor="rgba(11,61,46,0.12)",
            ),
            angularaxis=dict(gridcolor="rgba(11,61,46,0.10)"),
        ),
        showlegend=False,
        margin=dict(l=40, r=40, t=40, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        height=380,
        title=dict(
            text="Startup DNA Scorecard",
            font=dict(family="Fraunces", size=16, color="#0B3D2E"),
        ),
    )
    return fig


def radar_figure_dual(
    brief_a: InvestmentBrief,
    brief_b: InvestmentBrief,
    label_a: str,
    label_b: str,
) -> go.Figure:
    """Dual-trace radar chart overlaying two deals on the same axes.

    Deal A: green (#0B6E4F).  Deal B: gold (#C4A35A).
    Uses the same 5 non-Growth axes as the MVP score table so the chart
    and table dimensions match exactly.
    The existing single-brief ``radar_figure()`` is not modified.
    """
    cats = ["Founder", "Startup", "Market", "Trust", "Risk Inverse"]

    def _vals(b: InvestmentBrief) -> list[float]:
        return [
            b.founder_score,
            b.startup_score,
            b.market_score,
            b.trust_score,
            max(0.0, 100.0 - b.risk_score),
        ]

    vals_a = _vals(brief_a)
    vals_b = _vals(brief_b)
    theta = cats + [cats[0]]

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=vals_a + [vals_a[0]],
            theta=theta,
            fill="toself",
            line=dict(color="#0B6E4F", width=2.5),
            fillcolor="rgba(11,110,79,0.22)",
            name=label_a,
        )
    )
    fig.add_trace(
        go.Scatterpolar(
            r=vals_b + [vals_b[0]],
            theta=theta,
            fill="toself",
            line=dict(color="#C4A35A", width=2.5),
            fillcolor="rgba(196,163,90,0.22)",
            name=label_b,
        )
    )
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(255,255,255,0.45)",
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                showticklabels=False,
                gridcolor="rgba(11,61,46,0.12)",
            ),
            angularaxis=dict(gridcolor="rgba(11,61,46,0.10)"),
        ),
        showlegend=True,
        legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center"),
        margin=dict(l=40, r=40, t=50, b=60),
        paper_bgcolor="rgba(0,0,0,0)",
        height=420,
        title=dict(
            text="Deal DNA — Side-by-Side",
            font=dict(family="Fraunces", size=16, color="#0B3D2E"),
        ),
    )
    return fig


def syndicate_bar(brief: InvestmentBrief) -> go.Figure | None:
    if not brief.syndicate:
        return None
    names = []
    for v in brief.syndicate.votes:
        label = v.title or v.persona
        names.append(label.replace(" ", "\n"))
    scores = [v.confidence_score for v in brief.syndicate.votes]
    colors = [REC_COLORS.get(v.decision, "#888") for v in brief.syndicate.votes]
    fig = go.Figure(
        data=go.Bar(
            x=names,
            y=scores,
            marker_color=colors,
            text=[
                f"{v.decision.value}\n{s:.0f}"
                for v, s in zip(brief.syndicate.votes, scores)
            ],
            textposition="outside",
        )
    )
    fig.update_layout(
        title=dict(
            text="Twin Syndicate — Confidence by Investor",
            font=dict(family="Fraunces", size=16, color="#0B3D2E"),
        ),
        yaxis=dict(
            range=[0, 120],
            title="Confidence Score (0–100)",
            gridcolor="rgba(11,61,46,0.08)",
        ),
        margin=dict(l=20, r=20, t=50, b=80),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.45)",
        height=400,
    )
    return fig


def _vote_css_class(decision) -> str:
    """Map a Recommendation enum to a CSS modifier for persona-card and badge."""
    val = decision.value.lower().replace("-", "").replace(" ", "")
    if val == "invest":
        return "invest"
    if "coinvest" in val or "co" in val:
        return "coinvest"
    if "observe" in val:
        return "observe"
    if "follow" in val or "watch" in val:
        return "watch"
    return "pass"


# ═════════════════════════════════════════════════════════════════════════════
# Twin Syndicate — speaker identity registry + UI helpers
# ═════════════════════════════════════════════════════════════════════════════

# Stable, one-role-per-speaker identity registry.  Every archetype is mapped
# once here so that the same speaker name always renders with the same
# avatar / color / persona badge across scoreboard, cards, dissent block
# AND debate transcript.  Previously transcript speakers used idx%N rotation
# → same speaker got different avatar/color each run / each mention.
COMMITTEE_SPEAKERS: dict[str, dict] = {
    "african_vc": {
        "id": "african_vc",
        "speaker_names": ["Amina Okonkwo", "Amina"],
        "label_short": "VC",
        "avatar": "🏦",
        "color": "#0B6E4F",
        "persona": "African VC Partner",
        "firm": "Sahel Horizon Ventures",
    },
    "diaspora_angel": {
        "id": "diaspora_angel",
        "speaker_names": ["Fatima Diallo", "Fatima"],
        "label_short": "Operator",
        "avatar": "🧑‍💼",
        "color": "#B8892D",
        "persona": "Diaspora Angel Investor",
        "firm": "Lagos–London Angel Network",
    },
    "dfi_officer": {
        "id": "dfi_officer",
        "speaker_names": ["James Mwangi-Reed", "James"],
        "label_short": "Impact",
        "avatar": "🌍",
        "color": "#1B9AAA",
        "persona": "Development Finance Institution Officer",
        "firm": "Continental Development Partners",
    },
    "cvc_investor": {
        "id": "cvc_investor",
        "speaker_names": ["Thabo Nkosi", "Thabo"],
        "label_short": "Banker",
        "avatar": "🏢",
        "color": "#5B21B6",
        "persona": "Corporate Venture Capital Investor",
        "firm": "AfriTel Corporate Ventures",
    },
    "global_tier1": {
        "id": "global_tier1",
        "speaker_names": ["Elena Vargas", "Elena"],
        "label_short": "Market Specialist",
        "avatar": "🌐",
        "color": "#9B2226",
        "persona": "Global Tier-1 VC Partner",
        "firm": "Atlantic Bridge Capital",
    },
}

# Inverse mapping: speaker name → full identity.  Built lazily because
# LLM-returned debate transcript often uses short names.
def _committee_speaker_lookup() -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for ident in COMMITTEE_SPEAKERS.values():
        for nm in ident["speaker_names"]:
            lookup[nm.lower()] = ident
            lookup[nm] = ident
    return lookup


def _vote_for_speaker_name(name: str, votes) -> object | None:
    """Resolve a speaker-name string (from debate transcript line) back to
    the matching InvestorVote, using first-match over speaker-names / persona
    / title / investor_name.  Returns None if no match."""
    if not name or not votes:
        return None
    nm = name.strip().lower()
    for v in votes:
        for hay in (
            getattr(v, "investor_name", None) or "",
            getattr(v, "persona", "") or "",
            getattr(v, "title", "") or "",
        ):
            if nm in hay.lower() or hay.lower() in nm:
                return v
    # Also check COMMITTEE_SPEAKERS identity short labels
    for ident in COMMITTEE_SPEAKERS.values():
        for s in ident["speaker_names"]:
            if nm == s.lower() or s.lower() in nm or nm in s.lower():
                # Now find vote whose persona/firm/title matches identity
                for v in votes:
                    if (
                        ident["firm"] == getattr(v, "firm", None)
                        or ident["persona"].lower() in (getattr(v, "persona", "") or "").lower()
                    ):
                        return v
    return None


def _speaker_identity_for(vote_or_speaker, votes=None) -> dict:
    """Given either an InvestorVote *or* a speaker-name string, return the
    COMMITTEE_SPEAKERS identity dict.  Falls back to a synthetic identity
    keyed off label_short if no match is found."""
    import kulima.models as km

    if isinstance(vote_or_speaker, km.InvestorVote):
        v = vote_or_speaker
        # Match by archetype_id first
        aid = getattr(v, "archetype_id", None) or ""
        if aid and aid in COMMITTEE_SPEAKERS:
            return COMMITTEE_SPEAKERS[aid]
        # Fall back: match by firm / persona
        for ident in COMMITTEE_SPEAKERS.values():
            if ident["firm"] == getattr(v, "firm", None):
                return ident
            if ident["persona"].lower() in (getattr(v, "persona", "") or "").lower():
                return ident
        # Final synthetic identity using vote attributes
        label = (getattr(v, "title", None) or getattr(v, "persona", "") or "Analyst")[:10]
        return {
            "id": aid or "synthetic",
            "speaker_names": [getattr(v, "investor_name", "Analyst")],
            "label_short": label,
            "avatar": "👤",
            "color": "#5B6F64",
            "persona": getattr(v, "persona", ""),
            "firm": getattr(v, "firm", ""),
        }
    # Speaker-name string path
    name = str(vote_or_speaker)
    lookup = _committee_speaker_lookup()
    if name.lower() in lookup:
        return lookup[name.lower()]
    if votes:
        v = _vote_for_speaker_name(name, votes)
        if v is not None:
            return _speaker_identity_for(v)
    # Synthetic fallback (keeps transcript visually stable even for unknowns)
    safe = name.strip() or "Analyst"
    return {
        "id": f"unknown-{safe.lower()}",
        "speaker_names": [safe],
        "label_short": safe[:10],
        "avatar": "💬",
        "color": "#5B6F64",
        "persona": "IC Analyst",
        "firm": "",
    }


# ── Step 1: Persona card summary line ────────────────────────────────────────

def _persona_one_line_summary(vote) -> str:
    """Condense a vote into one punchy summary line.  Composes: thesis +
    major_concern (if any) + vote.  Used as collapsed-card visible line."""
    thesis = (getattr(vote, "key_reasoning", None) or getattr(vote, "thesis", "") or "").strip()
    concern = (getattr(vote, "major_concern", None) or "").strip()
    if not thesis:
        # Build one from first concern / condition we can find
        extras = getattr(vote, "concerns", None) or []
        thesis = extras[0] if extras else "Submitted vote without commentary."
    # Take first sentence (period-delimited, up to ~130 chars)
    first_sent = thesis.split(". ")[0].split("\n")[0].strip()
    if not first_sent.endswith((".", "!", "?")):
        first_sent += "."
    if len(first_sent) > 140:
        first_sent = first_sent[:137].rsplit(" ", 1)[0] + "…"
    if concern:
        c = concern.strip()
        if len(c) > 80:
            c = c[:77].rsplit(" ", 1)[0] + "…"
        return f"{first_sent}  ⚠ {c}"
    return first_sent


def _vote_is_negative_or_dissenting(vote, majority) -> bool:
    """Rule for Step-1 auto-expand: PASS (negative) *or* any vote that
    disagrees with the majority outcome (dissenting)."""
    from kulima.models import Recommendation
    dec = getattr(vote, "decision", None) or getattr(vote, "vote", Recommendation.OBSERVE)
    if dec == Recommendation.PASS:
        return True
    if majority is not None and dec != majority:
        return True
    return False


# ── Step 2: Debate transcript keyword filters ────────────────────────────────

DEBATE_FILTER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "All": (),
    "Objections": (
        "disagree", "object", "against", "not convince", "push back", "concern",
        "doubt", "skeptic", "risk", "hesitate", "block", "veto", "don't", "do not",
        "won't", "not invest", "pass on this", "no",
    ),
    "Support": (
        "invest", "support", "convince", "buy-in", "buy in", "conviction",
        "confident", "bull", "excited", "great team", "love", "founder-market fit",
        "strong", "clear path",
    ),
    "Risks": (
        "risk", "danger", "red flag", "threat", "downside", "exposure",
        "volatil", "fx risk", "currency", "regulat", "governance", "dilution",
        "competition", "churn", "moat",
    ),
    "Opportunities": (
        "opportunit", "upside", "market", "traction", "growth", "scale",
        "expand", "category", "moat", "distribution", "partner", "synergy",
        "revenue", "path to", "series b", "series a",
    ),
}


def _debate_line_matches_filter(content: str, filter_name: str) -> bool:
    if not content or filter_name == "All":
        return True
    keywords = DEBATE_FILTER_KEYWORDS.get(filter_name, ())
    if not keywords:
        return True
    text = content.lower()
    return any(kw.lower() in text for kw in keywords)


# ── Step 4: Speaker label ↔ vote(s) for speaker filter pills ─────────────────

def _speaker_present_in_turn(speaker_label: str, turn_speaker_name: str, votes) -> bool:
    """Return True if a transcript turn belongs to the given speaker-label
    filter (e.g. \"VC\", \"Operator\", \"Banker\", \"Impact\", \"Market Specialist\")."""
    if speaker_label == "All":
        return True
    ident = _speaker_identity_for(turn_speaker_name, votes=votes)
    return ident.get("label_short", "") == speaker_label


# ── Step 6: Scoreboard sort keys ─────────────────────────────────────────────

def _sort_votes(votes, sort_by: str, rec_value: object) -> list:
    from kulima.models import Recommendation
    order = {
        Recommendation.INVEST: 0,
        Recommendation.CO_INVEST: 1,
        Recommendation.OBSERVE: 2,
        Recommendation.FOLLOW_ON_WATCH: 3,
        Recommendation.PASS: 4,
    }
    if sort_by == "vote":
        return sorted(
            votes,
            key=lambda v: (
                order.get(getattr(v, "decision", None) or getattr(v, "vote", Recommendation.OBSERVE), 9),
                -getattr(v, "confidence_score", 0),
            ),
        )
    # Default / confidence
    return sorted(votes, key=lambda v: -getattr(v, "confidence_score", 0))


# ═════════════════════════════════════════════════════════════════════════════


def render_twin_syndicate_committee(
    brief: InvestmentBrief, key_suffix: str = ""
) -> None:
    """
    Phase 3: Committee Intelligence workspace.

    Decision-first layout PLUS:
    - Step 1: collapsed persona cards with one-line summary (auto-expand
      dissenting / negative votes).
    - Step 5: Dissenting Views analysis block.
    - Step 6: IC scoreboard above transcript.
    - Steps 2 + 4: keyword + speaker filter pills above transcript.
    - Step 3: stable speaker identity (same avatar / color / badge).
    """
    from kulima.models import Recommendation, InvestorVote  # noqa: F401 (for typing paths)

    st.markdown("## 🏛 Twin Syndicate Investment Committee")
    st.caption(
        "Five independent investor twins vote Invest / Observe / Pass using GPT-4.1-mini."
    )

    if not brief.syndicate:
        st.warning("Syndicate has not convened for this run.")
        return

    syn = brief.syndicate
    final = syn.final_recommendation or syn.majority_vote
    consensus = syn.consensus_score if syn.consensus_score else syn.average_score
    dissent = syn.dissent_score if syn.dissent_score else syn.dissent_index * 100

    # ── Final Committee Outcome banner — moved to TOP (decision-first) ──
    st.markdown("### Final Committee Outcome")
    color = REC_COLORS.get(final, "#0B3D2E")
    st.markdown(textwrap.dedent(f"""
        <div class="rec-banner" style="background:{color};">
            Committee Decision: {html.escape(final.value)}
            &nbsp;·&nbsp; Consensus {consensus:.0f}/100
            &nbsp;·&nbsp; Dissent {dissent:.0f}/100
        </div>
        """), unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Syndicate Consensus Score",
        f"{consensus:.0f}/100",
        help="Average confidence across all committee members. ≥75 = strong consensus.",
    )
    c2.metric(
        "Final Recommendation",
        final.value,
        help="Majority-weighted committee decision.",
    )
    c3.metric(
        "Dissent Score",
        f"{dissent:.0f}/100",
        help="Degree of disagreement between committee members. Lower = more unified.",
    )

    if syn.consensus_thesis:
        st.info(syn.consensus_thesis)

    fig = syndicate_bar(brief)
    if fig:
        chart_key = f"syndicate_chart{key_suffix}" if key_suffix else "syndicate_chart"
        st.plotly_chart(fig, width="stretch", key=chart_key)

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 5 — Dissenting Views (minority opinions + reasons)
    # ═══════════════════════════════════════════════════════════════════════
    majority_decision = final
    dissenting_votes = [
        v for v in syn.votes
        if _vote_is_negative_or_dissenting(v, majority_decision)
    ]
    if dissenting_votes:
        with st.expander("⚠ Dissenting Views", expanded=True):
            st.caption(
                f"{len(dissenting_votes)} committee member(s) disagree with the "
                f"{final.value} outcome or voted PASS (negative).  Review these before IC."
            )
            for v in dissenting_votes:
                ident = _speaker_identity_for(v)
                dec = getattr(v, "decision", None) or getattr(v, "vote", Recommendation.OBSERVE)
                css = _vote_css_class(dec)
                reasoning = html.escape(getattr(v, "key_reasoning", None) or getattr(v, "thesis", "") or "—")
                concern = html.escape(getattr(v, "major_concern", "") or "—")
                st.markdown(
                    f"""
                    <div class="persona-card vote-{css}" style="margin:0.35rem 0 0.55rem 0;">
                      <div class="persona-header">
                        <div>
                          <div class="persona-name">{ident['avatar']} {html.escape(getattr(v, 'investor_name', ident['persona']))}
                            <span style="display:inline-block;margin-left:0.4rem;padding:0.05rem 0.45rem;border-radius:999px;
                                background:{ident['color']}22;border:1px solid {ident['color']}55;
                                color:{ident['color']};font-size:0.72rem;font-weight:700;">
                              {html.escape(ident['label_short'])}</span>
                          </div>
                          <div class="persona-firm">{html.escape(getattr(v, 'firm', '') or ident['firm'])}</div>
                        </div>
                        <div>
                          <span class="persona-badge badge-{css}">{html.escape(dec.value)}</span>
                          <div style="font-size:0.78rem;color:#5B6F64;text-align:right;margin-top:0.2rem;">
                              {getattr(v, 'confidence_score', 0):.0f}/100
                          </div>
                        </div>
                      </div>
                      <div class="persona-reasoning">{reasoning}</div>
                      <div class="persona-concern"><strong>⚠ Reason for disagreement:</strong> {concern}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # ── Individual Committee Votes — persona cards (Step 1 compression) ──
    st.markdown("### Individual Committee Votes")
    for idx, v in enumerate(syn.votes):
        ident = _speaker_identity_for(v)
        role = getattr(v, "title", None) or getattr(v, "persona", "") or ident["persona"]
        dec = getattr(v, "decision", None) or getattr(v, "vote", Recommendation.OBSERVE)
        css = _vote_css_class(dec)
        badge_css = f"badge-{css}"
        auto_expand = _vote_is_negative_or_dissenting(v, majority_decision)

        summary_line = _persona_one_line_summary(v)
        firm_line = f"{html.escape(getattr(v, 'investor_name', '') or ident['speaker_names'][0])} · {html.escape(getattr(v, 'firm', '') or ident['firm'])}"
        header_html = f"""
        <div style="display:flex;align-items:center;gap:0.6rem;justify-content:space-between;flex-wrap:wrap;">
          <div style="display:flex;align-items:center;gap:0.55rem;min-width:0;">
            <div style="width:38px;height:38px;border-radius:999px;background:{ident['color']}22;
                        color:{ident['color']};display:flex;align-items:center;justify-content:center;
                        border:1px solid {ident['color']}55;font-size:1.1rem;flex:0 0 auto;">
              {ident['avatar']}
            </div>
            <div style="min-width:0;">
              <div style="font-family:'Fraunces',Georgia,serif;font-weight:700;font-size:1.02rem;color:#0B3D2E;letter-spacing:-0.01em;
                          display:flex;align-items:center;gap:0.35rem;flex-wrap:wrap;">
                {html.escape(role)}
                <span style="font-size:0.72rem;padding:0.08rem 0.45rem;border-radius:999px;
                            background:{ident['color']}22;border:1px solid {ident['color']}55;color:{ident['color']};font-weight:700;
                            font-family:'Source Sans 3',sans-serif;">
                  {html.escape(ident['label_short'])}
                </span>
              </div>
              <div style="font-size:0.82rem;color:#5B6F64;overflow:hidden;text-overflow:ellipsis;">
                {firm_line}
              </div>
            </div>
          </div>
          <div style="display:flex;align-items:center;gap:0.5rem;">
            <div style="font-size:0.78rem;color:#5B6F64;font-weight:700;">
              {getattr(v, 'confidence_score', 0):.0f}/100
            </div>
            <span class="persona-badge {badge_css}">{html.escape(dec.value)}</span>
          </div>
        </div>
        <div style="margin-top:0.45rem;padding:0.45rem 0.65rem;background:rgba(11,61,46,0.04);
                    border-radius:10px;font-size:0.88rem;color:#1B2A24;border-left:3px solid {ident['color']};">
          {html.escape(summary_line)}
        </div>
        """

        exp_title = f"{ident['avatar']} {role}"
        card_key = f"committee_persona_{idx}_{_vote_css_class(dec)}_{key_suffix or 'global'}"
        # Step 1: auto-expand if dissenting / negative, otherwise collapsed
        with st.expander(exp_title, expanded=bool(auto_expand)):
            st.markdown(header_html, unsafe_allow_html=True)

            # Full Reasoning + Full Concerns + Full Thesis (all only shown
            # inside expanded card)
            with st.expander("🔍 View Full Reasoning", expanded=False):
                reasoning = html.escape(
                    getattr(v, "key_reasoning", None) or getattr(v, "thesis", "") or "—"
                )
                st.markdown(f"**Thesis / Key Reasoning**  \n{reasoning}")
                concerns = getattr(v, "concerns", None) or []
                if getattr(v, "major_concern", None):
                    concerns = [getattr(v, "major_concern", "")] + [c for c in concerns if c != getattr(v, "major_concern", "")]
                if concerns:
                    st.markdown("**Concerns**")
                    for c in concerns:
                        if c:
                            st.markdown(f"- {html.escape(c)}")
                conditions = getattr(v, "conditions", None) or []
                if conditions:
                    st.markdown("**Conditions to proceed**")
                    for cond in conditions:
                        if cond:
                            st.markdown(f"- {html.escape(cond)}")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 6 — Investment Committee Scoreboard
    # ═══════════════════════════════════════════════════════════════════════
    sort_key = f"committee_scoreboard_sort_{key_suffix or 'global'}"
    if sort_key not in st.session_state:
        st.session_state[sort_key] = "confidence"

    st.markdown("### Investment Committee Scoreboard")
    scol1, scol2, scol3 = st.columns([1.4, 1, 1])
    scol1.caption("Sort scoreboard by")
    if scol2.button(
        "⇅ Confidence",
        key=f"sort_conf_{sort_key}",
        type=("primary" if st.session_state[sort_key] == "confidence" else "secondary"),
        width="stretch",
    ):
        st.session_state[sort_key] = "confidence"
    if scol3.button(
        "⇅ Vote",
        key=f"sort_vote_{sort_key}",
        type=("primary" if st.session_state[sort_key] == "vote" else "secondary"),
        width="stretch",
    ):
        st.session_state[sort_key] = "vote"

    sorted_votes = _sort_votes(syn.votes, st.session_state[sort_key], final)

    # Scoreboard body — desktop: 5-column grid.  Mobile (≤640px): each row
    # uses st.columns([2,1,1]) so it reflows naturally w/o horizontal scroll.
    # We emit as HTML grid with media queries for full control + mobile 1-col.
    sb_html = """
    <div style="
        display:grid;
        grid-template-columns: 2fr 1fr 1fr 1.2fr;
        gap: 0.45rem 0.75rem;
        background: rgba(255,255,255,0.72);
        border: 1px solid rgba(11,61,46,0.10);
        border-radius: 14px;
        padding: 0.7rem 0.85rem;
        margin: 0.3rem 0 0.1rem;
    " class="committee-scoreboard-grid">
    """
    headers = ["Member", "Role", "Vote", "Confidence"]
    for h in headers:
        sb_html += (
            f'<div style="font-size:0.72rem;font-weight:800;color:#5B6F64;'
            f'text-transform:uppercase;letter-spacing:0.05em;">{h}</div>'
        )
    for v in sorted_votes:
        ident = _speaker_identity_for(v)
        dec = getattr(v, "decision", None) or getattr(v, "vote", Recommendation.OBSERVE)
        css = _vote_css_class(dec)
        conf = getattr(v, "confidence_score", 0)
        # Confidence bar: thin inline strip
        bar_pct = max(0, min(100, int(round(conf))))
        bar_color = ident["color"]
        sb_html += f"""
          <div style="display:flex;align-items:center;gap:0.45rem;">
            <div style="width:26px;height:26px;border-radius:999px;background:{ident['color']}22;
                        color:{ident['color']};display:flex;align-items:center;justify-content:center;
                        border:1px solid {ident['color']}55;font-size:0.85rem;">
              {ident['avatar']}</div>
            <div style="min-width:0;">
              <div style="font-weight:700;font-size:0.88rem;color:#0B3D2E;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                {html.escape(getattr(v, 'investor_name', '') or ident['speaker_names'][0])}
              </div>
              <div style="font-size:0.7rem;color:#5B6F64;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                {html.escape(getattr(v, 'firm', '') or ident['firm'])}
              </div>
            </div>
          </div>
          <div style="display:flex;align-items:center;">
            <span style="display:inline-block;padding:0.1rem 0.45rem;border-radius:999px;
                         background:{ident['color']}22;border:1px solid {ident['color']}55;
                         color:{ident['color']};font-size:0.72rem;font-weight:700;">
              {html.escape(ident['label_short'])}</span>
          </div>
          <div style="display:flex;align-items:center;">
            <span class="persona-badge badge-{css}">{html.escape(dec.value)}</span>
          </div>
          <div style="display:flex;align-items:center;gap:0.5rem;">
            <div style="flex:1 1 auto;height:6px;border-radius:999px;background:rgba(11,61,46,0.10);overflow:hidden;">
              <div style="width:{bar_pct}%;height:100%;background:{bar_color};"></div>
            </div>
            <div style="font-size:0.82rem;font-weight:800;color:#0B3D2E;">{conf:.0f}</div>
          </div>
        """
    sb_html += """
    </div>
    <style>
      @media (max-width: 768px) {
        .committee-scoreboard-grid {
          grid-template-columns: 1.6fr 1fr !important;
        }
        .committee-scoreboard-grid > div:nth-child(-n+4) { display: none; }
        .committee-scoreboard-grid > div:nth-child(4n+1) { border-top: none !important; }
      }
      @media (max-width: 480px) {
        .committee-scoreboard-grid {
          grid-template-columns: 1fr !important;
        }
      }
    </style>
    """
    st.markdown(sb_html, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # DEBATE TRANSCRIPT BLOCK — Steps 2+3+4 (filters + stable speaker identity)
    # ═══════════════════════════════════════════════════════════════════════
    if syn.debate_transcript:
        with st.expander("📜 IC Debate Transcript", expanded=False):
            st.caption(
                "Live deliberation between committee members as recorded by the IC. "
                "Use filters below to narrow the view."
            )

            # ── Session-state filter keys (scoped per brief+suffix) ────────
            kb = f"committee_debate_keyword_{key_suffix or 'global'}"
            sp = f"committee_debate_speaker_{key_suffix or 'global'}"
            if kb not in st.session_state:
                st.session_state[kb] = "All"
            if sp not in st.session_state:
                st.session_state[sp] = "All"

            # Step 2: keyword filter chip row
            st.markdown("**Debate Filters**")
            kw_pills = st.columns(len(DEBATE_FILTER_KEYWORDS))
            for i, (fname, _kws) in enumerate(DEBATE_FILTER_KEYWORDS.items()):
                is_on = st.session_state[kb] == fname
                with kw_pills[i]:
                    if st.button(
                        fname,
                        key=f"kw_{kb}_{fname}",
                        type="primary" if is_on else "secondary",
                        width="stretch",
                    ):
                        st.session_state[kb] = fname

            # Step 4: speaker filter pill row
            st.markdown("**Speaker Filters**")
            speaker_labels = ["All"] + [
                COMMITTEE_SPEAKERS[k]["label_short"]
                for k in ("african_vc", "diaspora_angel", "cvc_investor", "dfi_officer", "global_tier1")
                if any(
                    _speaker_identity_for(v).get("label_short") == COMMITTEE_SPEAKERS[k]["label_short"]
                    for v in syn.votes
                )
            ]
            sp_pills_cols = st.columns(len(speaker_labels))
            for i, label in enumerate(speaker_labels):
                is_on = st.session_state[sp] == label
                with sp_pills_cols[i]:
                    if st.button(
                        label,
                        key=f"sp_{sp}_{label}",
                        type="primary" if is_on else "secondary",
                        width="stretch",
                    ):
                        st.session_state[sp] = label

            lines = [ln.strip() for ln in syn.debate_transcript.splitlines() if ln.strip()]
            _render_debate_lines(
                lines,
                votes=syn.votes,
                keyword_filter=st.session_state[kb],
                speaker_filter=st.session_state[sp],
                key_suffix=key_suffix,
            )

    if syn.blocking_concerns:
        st.error("Blocking concerns: " + " · ".join(syn.blocking_concerns))


def _render_debate_lines(
    lines: list[str],
    votes=None,
    keyword_filter: str = "All",
    speaker_filter: str = "All",
    key_suffix: str = "",
) -> None:
    """
    Phase 3 — Analyst workspace transcript renderer.

    Changes vs. Phase 2 (summary of Step 2 + Step 3 + Step 4):
    * Step 3 — **Consistent speaker identity**.  Same speaker name always
      maps to the same avatar / color / persona badge.  Renderer looks up
      speaker via identity map (including InvestorVote fallback) so the
      speaker Amina Okonkwo always gets 🏦 VC green — regardless of
      position.  No more idx%N alternating.
    * Step 2 — Keyword filter.  Turns whose *content* matches the keyword
      filter are kept.
    * Step 4 — Speaker filter.  Turns whose *speaker label_short* matches
      the filter (e.g. \"VC\", \"Operator\") are kept.
    * Otherwise behaviour is preserved: unknowns → "IC" fallback,
      continuation lines → concatenated, markdown output.
    """
    import re

    speaker_pattern = re.compile(r"^([A-Z][^:]{2,40}):\s*(.+)$")
    turns: list[tuple[str, str]] = []  # (speaker, content)

    for line in lines:
        m = speaker_pattern.match(line)
        if m:
            turns.append((m.group(1).strip(), m.group(2).strip()))
        else:
            if turns:
                speaker, content = turns[-1]
                turns[-1] = (speaker, content + " " + line)
            else:
                turns.append(("IC", line))

    if not turns:
        st.write("\n".join(lines))
        return

    # Apply Step 2 (keyword) + Step 4 (speaker) filters
    filtered: list[tuple[str, str]] = []
    for speaker, content in turns:
        if not _debate_line_matches_filter(content, keyword_filter):
            continue
        if not _speaker_present_in_turn(speaker_filter, speaker, votes or []):
            continue
        filtered.append((speaker, content))

    if not filtered:
        st.info(
            "No debate turns match the current filters.  Try switching back to **All** "
            "for both Debate and Speaker filters."
        )
        return

    # Step 3 — Stable speaker rendering (same avatar/color/badge every time)
    for idx, (speaker, content) in enumerate(filtered):
        ident = _speaker_identity_for(speaker, votes=votes or [])
        # Streamlit chat_message avatar arg can be emoji string; use ident avatar
        # We keep the role alternating so we still get distinct bubbles, but
        # the emoji identity + color badge inside guarantees consistency.
        role = "assistant" if idx % 2 == 0 else "user"
        with st.chat_message(role, avatar=ident["avatar"]):
            st.markdown(
                f"<div style=\"display:flex;align-items:center;gap:0.35rem;flex-wrap:wrap;"
                f"margin-bottom:0.25rem;\">"
                f"<strong style=\"color:{ident['color']};\">{html.escape(speaker)}</strong>"
                f"<span style=\"display:inline-block;padding:0.05rem 0.4rem;border-radius:999px;"
                f"background:{ident['color']}22;border:1px solid {ident['color']}55;"
                f"color:{ident['color']};font-size:0.7rem;font-weight:700;letter-spacing:0.02em;\">"
                f"{html.escape(ident['label_short'])}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.write(content)


def futures_chart(brief: InvestmentBrief) -> go.Figure | None:
    if not brief.future_simulation:
        return None
    scenarios = brief.future_simulation.scenarios
    names = [f"{s.emoji} {s.name}" for s in scenarios]
    success = [s.success_probability for s in scenarios]
    attract = [s.investor_attractiveness_score for s in scenarios]
    colors = ["#0B6E4F", "#1B9AAA", "#9B2226"]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Success Probability %",
            x=names,
            y=success,
            marker_color=colors[: len(names)],
            text=[f"{v:.0f}%" for v in success],
            textposition="outside",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Investor Attractiveness",
            x=names,
            y=attract,
            marker_color=["#7CB69A", "#7EC8D4", "#C97B7E"][: len(names)],
            text=[f"{v:.0f}" for v in attract],
            textposition="outside",
        )
    )
    fig.update_layout(
        barmode="group",
        title=dict(
            text="Continental Futures — Success vs Attractiveness",
            font=dict(family="Fraunces", size=16, color="#0B3D2E"),
        ),
        yaxis=dict(range=[0, 120], title="Score", gridcolor="rgba(11,61,46,0.08)"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.45)",
        height=380,
        legend=dict(orientation="h", y=-0.2),
        margin=dict(l=20, r=20, t=50, b=70),
    )
    return fig


def render_continental_futures_simulator(
    brief: InvestmentBrief, key_suffix: str = ""
) -> None:
    st.markdown("## 🌍 Continental Futures Simulator")
    st.caption(
        "Bull / Base / Bear outcomes under African market conditions · GPT-4.1-mini"
    )

    fs = brief.future_simulation
    if not fs or not fs.scenarios:
        st.warning("Futures simulation has not run for this analysis.")
        return

    m1, m2, m3 = st.columns(3)
    m1.metric(
        "Most Likely Case",
        fs.most_likely_case or "Base Case",
        help="The scenario assessed as most probable given current market conditions.",
    )
    m2.metric(
        "Africa Risk Premium",
        f"{fs.africa_risk_premium:.1f} pp",
        help="Additional risk premium (percentage points) applied for African market exposure.",
    )
    m3.metric(
        "Expected Value (36m)",
        f"${fs.expected_value_usd:,.0f}",
        help="Probability-weighted expected portfolio value at the 36-month horizon.",
    )

    if fs.africa_conditions_summary:
        st.info(fs.africa_conditions_summary)

    fig = futures_chart(brief)
    if fig:
        chart_key = f"futures_chart{key_suffix}" if key_suffix else "futures_chart"
        st.plotly_chart(fig, width="stretch", key=chart_key)

    cols = st.columns(3)
    # Outer wrapper: CSS flex-wrap reflows cards to full-width on mobile
    st.markdown('<div class="futures-cards-row">', unsafe_allow_html=True)
    for col, scenario in zip(cols, fs.scenarios[:3]):
        css = "base"
        if "Bull" in scenario.name:
            css = "bull"
        elif "Bear" in scenario.name:
            css = "bear"

        risks_html = "".join(
            f"<li>{html.escape(r)}</li>" for r in scenario.major_risks[:4]
        )
        opps_html = "".join(
            f"<li>{html.escape(o)}</li>" for o in scenario.key_opportunities[:4]
        )
        outlook = html.escape(scenario.revenue_growth_outlook or scenario.narrative)

        with col:
            st.markdown(
                f"""
                <div class="futures-card {css}">
                    <h3>{scenario.emoji} {html.escape(scenario.name)}</h3>
                    <div class="futures-metric-label">Success Probability</div>
                    <div class="futures-metric-value">{scenario.success_probability:.0f}%</div>
                    <div class="futures-metric-label">Investor Attractiveness Score</div>
                    <div class="futures-metric-value">{scenario.investor_attractiveness_score:.0f}/100</div>
                    <div class="futures-metric-label">Revenue Growth Outlook</div>
                    <p class="futures-body">{outlook}</p>
                    <div class="futures-metric-label">Major Risks</div>
                    <ul class="futures-body">{risks_html or "<li>None listed</li>"}</ul>
                    <div class="futures-metric-label">Key Opportunities</div>
                    <ul class="futures-body">{opps_html or "<li>None listed</li>"}</ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if fs.simulation_notes:
        st.caption(fs.simulation_notes)
    st.markdown('</div>', unsafe_allow_html=True)  # close futures-cards-row


def trust_graph_table(brief: InvestmentBrief) -> pd.DataFrame | None:
    if not brief.trust_graph:
        return None
    rows = [
        {
            "Entity": n.label,
            "Type": n.node_type,
            "Weight": round(n.weight, 2),
        }
        for n in brief.trust_graph.nodes
    ]
    return pd.DataFrame(rows)


def history_frame(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


# ── Load Previous Run helpers ─────────────────────────────────────────────────

_REC_EMOJI = {
    "Invest": "✅",
    "Co-Invest": "🤝",
    "Observe": "👁",
    "Follow-On Watch": "🔭",
    "Pass": "❌",
}


def _fmt_ts(iso: str) -> str:
    """Convert an ISO 8601 UTC string to a readable local-style label."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y  %H:%M UTC")
    except Exception:
        return iso


def render_loaded_banner(run_id: int, created_at: str) -> None:
    """Teal archive-restore banner shown instead of the green live-run banner."""
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #1B7A9A, #176B87);
            color: white;
            border-radius: 16px;
            padding: 0.9rem 1.15rem;
            margin: 0.4rem 0 1rem 0;
            box-shadow: 0 12px 28px rgba(27,122,154,0.22);
        ">
            <strong style="font-family:Fraunces,Georgia,serif;font-size:1.1rem;">
                📂 Loaded from archive
            </strong>
            &nbsp;·&nbsp; Run <code style="background:rgba(255,255,255,0.18);
                border-radius:4px;padding:0 4px;">#{run_id}</code>
            &nbsp;·&nbsp; {html.escape(_fmt_ts(created_at))}
            <br/>
            <span style="font-size:0.83rem;opacity:0.9;margin-top:0.3rem;display:block;">
                No agents were re-run. All scores, sources, syndicate votes, and
                analyses are from the original intelligence run.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_history_panel(rows: list[dict]) -> int | None:
    """Interactive Founder Memory panel.

    Renders a selectable table of previous runs.  When the analyst checks
    a row and clicks **Load Selected Run**, returns that row's integer ``id``.
    Returns ``None`` in all other cases (nothing selected, button not
    pressed, or empty history).
    """
    if not rows:
        st.caption("No intelligence runs stored yet — run your first deal above.")
        return None

    # ── Build display table ──────────────────────────────────────────────────
    # Check whether integrity columns are present in the row dicts
    _has_integrity = any("integrity_grade" in r for r in rows)

    display_rows = []
    for r in rows:
        rec_raw = r.get("recommendation") or "Observe"
        emoji = _REC_EMOJI.get(rec_raw, "")
        row_dict: dict = {
            "Select": False,
            "ID": int(r["id"]),
            "Date": _fmt_ts(r.get("created_at") or ""),
            "Founder": r.get("founder_name") or "—",
            "Startup": r.get("startup_name") or "—",
            "Rec": f"{emoji} {rec_raw}",
            "Score": f"{float(r.get('overall_score') or 0):.0f}",
            "Confidence": f"{float(r.get('confidence') or 0):.0%}",
        }
        if _has_integrity:
            grade = r.get("integrity_grade") or "—"
            score = r.get("integrity_score")
            # Depth dots: approximate from integrity_score when no full report available
            row_dict["Reliability"] = grade
            row_dict["Rel. Score"] = f"{score:.0f}" if score is not None else "—"
        display_rows.append(row_dict)

    df_display = pd.DataFrame(display_rows)

    base_col_config: dict = {
        "Select": st.column_config.CheckboxColumn(
            "Load?", help="Check a row then click the button below", default=False
        ),
        "ID": st.column_config.NumberColumn("Run #", width="small"),
        "Date": st.column_config.TextColumn("Date (UTC)", width="medium"),
        "Founder": st.column_config.TextColumn("Founder"),
        "Startup": st.column_config.TextColumn("Startup"),
        "Rec": st.column_config.TextColumn("Recommendation"),
        "Score": st.column_config.TextColumn("Score", width="small"),
        "Confidence": st.column_config.TextColumn("Confidence", width="small"),
    }
    disabled_cols = ["ID", "Date", "Founder", "Startup", "Rec", "Score", "Confidence"]

    if _has_integrity:
        base_col_config["Reliability"] = st.column_config.TextColumn(
            "Reliability", width="small",
            help="Evidence Integrity Grade (A=best, F=most concern). — = pre-EIE run."
        )
        base_col_config["Rel. Score"] = st.column_config.TextColumn(
            "Rel. Score", width="small",
            help="Integrity score (0–100). — = pre-EIE run."
        )
        disabled_cols += ["Reliability", "Rel. Score"]

    edited = st.data_editor(
        df_display,
        width="stretch",
        hide_index=True,
        key="history_panel_editor",
        column_config=base_col_config,
        disabled=disabled_cols,
        num_rows="fixed",
    )

    load_clicked = st.button(
        "📂 Load Selected Run",
        key="load_selected_run_btn",
        help="Restore the checked run — no agents will be re-run",
    )

    if not load_clicked:
        return None

    # ── Identify selected row ────────────────────────────────────────────────
    selected = edited[edited["Select"] == True]  # noqa: E712
    if selected.empty:
        st.warning("Check a row in the table above first, then click Load.", icon="☝️")
        return None

    return int(selected.iloc[0]["ID"])
