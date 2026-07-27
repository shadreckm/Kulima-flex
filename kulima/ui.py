"""Executive dashboard UI helpers — visual scorecards & charts."""

from __future__ import annotations

import html
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
    st.markdown(
        """
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
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
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
        """,
        unsafe_allow_html=True,
    )


def render_empty_state() -> None:
    st.markdown(
        """
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
        """,
        unsafe_allow_html=True,
    )


def render_success_banner(brief: InvestmentBrief) -> None:
    flags = len(brief.red_flags)
    st.markdown(
        f"""
        <div class="success-banner">
            <strong>Analysis complete</strong><br/>
            {html.escape(brief.founder_name)} / {html.escape(brief.startup_name)}
            &nbsp;·&nbsp; Recommendation <b>{html.escape(brief.recommendation.value)}</b>
            &nbsp;·&nbsp; Overall {brief.overall_score:.0f}/100
            &nbsp;·&nbsp; {flags} red flag{"s" if flags != 1 else ""} reviewed
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_recommendation_banner(brief: InvestmentBrief) -> None:
    color = REC_COLORS.get(brief.recommendation, "#0B3D2E")
    syn = ""
    if brief.syndicate:
        final = brief.syndicate.final_recommendation or brief.syndicate.majority_vote
        syn = (
            f"Syndicate {final.value} · Consensus "
            f"{(brief.syndicate.consensus_score or brief.syndicate.average_score):.0f}/100"
        )
    st.markdown(
        f"""
        <div class="rec-banner" style="background:{color};">
            IC Recommendation: {html.escape(brief.recommendation.value)}
            &nbsp;·&nbsp; Conviction {html.escape(brief.confidence_level.value)}
            &nbsp;·&nbsp; Overall {brief.overall_score:.0f}/100
            <span class="sub">{html.escape(syn) if syn else "Partner-grade diligence complete"}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_score_row(brief: InvestmentBrief) -> None:
    """
    Phase 2/3: Executive scorecard.

    HTML chips are rendered in a CSS grid (.score-chip-grid) that reflows
    automatically: 6 columns on desktop, 3 on tablet, 2 on phone.
    Below the grid, 6 st.metric widgets (collapsed labels) provide
    accessibility / screen-reader support — Streamlit handles their own
    responsive reflow natively.
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

    # ── HTML chip grid — reflows via CSS at tablet/phone breakpoints ──────
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

    # ── Accessible st.metric row — screen-readers & keyboard nav ─────────
    # st.columns(6) is fine here: these are slim metric widgets whose own
    # Streamlit layout wraps gracefully; labels are hidden (collapsed).
    a_cols = st.columns(6)
    for col, (label, value, invert, hint, tooltip) in zip(a_cols, metrics):
        with col:
            delta_val = value - 75 if not invert else 75 - value
            st.metric(
                label=label,
                value=f"{value:.0f}/100",
                delta=f"{'▲' if delta_val >= 0 else '▼'} {abs(delta_val):.0f} vs threshold",
                delta_color=_delta_color(value, invert=invert),
                help=tooltip,
                label_visibility="collapsed",
            )


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


def render_twin_syndicate_committee(
    brief: InvestmentBrief, key_suffix: str = ""
) -> None:
    """
    Phase 2: Committee Debate tab.
    - Summary metrics
    - Syndicate bar chart
    - Individual persona cards (HTML) with colour-coded decision badges
    - Debate transcript rendered via st.chat_message()
    - Final committee outcome banner
    """
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
        st.plotly_chart(fig, use_container_width=True, key=chart_key)

    # ── Individual Committee Votes — persona cards ────────────────────────
    st.markdown("### Individual Committee Votes")
    for v in syn.votes:
        role = v.title or v.persona
        css = _vote_css_class(v.decision)
        badge_css = f"badge-{css}"
        concern_html = ""
        concern_text = v.major_concern or (v.concerns[0] if v.concerns else "")
        if concern_text:
            concern_html = (
                f'<div class="persona-concern">'
                f'<strong>⚠ Major Concern:</strong> {html.escape(concern_text)}'
                f"</div>"
            )
        reasoning = html.escape(v.key_reasoning or v.thesis or "—")
        st.markdown(
            f"""
            <div class="persona-card vote-{css}">
                <div class="persona-header">
                    <div>
                        <div class="persona-name">{html.escape(role)}</div>
                        <div class="persona-firm">{html.escape(v.investor_name)} · {html.escape(v.firm)}</div>
                    </div>
                    <div>
                        <span class="persona-badge {badge_css}">{html.escape(v.decision.value)}</span>
                        <div style="font-size:0.78rem;color:#5B6F64;text-align:right;margin-top:0.2rem;">
                            {v.confidence_score:.0f}/100
                        </div>
                    </div>
                </div>
                <div class="persona-reasoning">{reasoning}</div>
                {concern_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Debate Transcript — rendered as chat messages ─────────────────────
    if syn.debate_transcript:
        st.markdown("### IC Debate Transcript")
        st.caption("Live deliberation between committee members as recorded by the IC.")
        # Split transcript by line — attempt to detect speaker patterns
        lines = [ln.strip() for ln in syn.debate_transcript.splitlines() if ln.strip()]
        _render_debate_lines(lines, key_suffix=key_suffix)

    # ── Final outcome banner ──────────────────────────────────────────────
    st.markdown("### Final Committee Outcome")
    color = REC_COLORS.get(final, "#0B3D2E")
    st.markdown(
        f"""
        <div class="rec-banner" style="background:{color};">
            Committee Decision: {html.escape(final.value)}
            &nbsp;·&nbsp; Consensus {consensus:.0f}/100
            &nbsp;·&nbsp; Dissent {dissent:.0f}/100
        </div>
        """,
        unsafe_allow_html=True,
    )
    if syn.blocking_concerns:
        st.error("Blocking concerns: " + " · ".join(syn.blocking_concerns))


def _render_debate_lines(lines: list[str], key_suffix: str = "") -> None:
    """
    Phase 2: Render debate transcript lines using st.chat_message().

    Heuristic: if a line starts with a capitalised name followed by ':' treat it
    as a new speaker turn.  Otherwise concatenate continuation lines into the
    previous message.  Alternates assistant / user avatars by position to give
    visual variety without changing any underlying data.
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

    avatars = ["👤", "🧑‍💼", "👩‍💼", "🏦", "🌍"]
    for idx, (speaker, content) in enumerate(turns):
        role = "assistant" if idx % 2 == 0 else "user"
        avatar = avatars[idx % len(avatars)]
        with st.chat_message(role, avatar=avatar):
            st.markdown(f"**{html.escape(speaker)}**")
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
        st.plotly_chart(fig, use_container_width=True, key=chart_key)

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
        use_container_width=True,
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
