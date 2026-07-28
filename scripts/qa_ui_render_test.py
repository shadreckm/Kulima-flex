from unittest.mock import MagicMock
import sys
import os

# Ensure repository root is on sys.path so 'kulima' package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import textwrap

import kulima.trust_layer_ui as t_ui
import kulima.ui as ui_module
from kulima.models import (
    ThesisMatchResult,
    ThesisStatus,
    InvestmentBrief,
    InvestorVote,
    SyndicateDecision,
    Recommendation,
)

# Setup shared MagicMock for streamlit in both modules
mock_st = MagicMock()
# expander context manager support
mock_st.expander.return_value.__enter__ = MagicMock(return_value=None)
mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)
# columns returns context-managers
def _cols(n=1):
    # st.columns may be called with an int or a list/tuple of widths
    count = 1
    if isinstance(n, (list, tuple)):
        count = len(n)
    else:
        try:
            count = int(n)
        except Exception:
            count = 1
    cols = [MagicMock() for _ in range(count)]
    for c in cols:
        c.__enter__ = MagicMock(return_value=c)
        c.__exit__ = MagicMock(return_value=False)
    return cols
mock_st.columns.side_effect = _cols
# chat_message context manager
mock_st.chat_message.return_value.__enter__ = MagicMock(return_value=None)
mock_st.chat_message.return_value.__exit__ = MagicMock(return_value=False)

# Inject mock into modules
t_ui.st = mock_st
ui_module.st = mock_st

# ---------- Test 1: render_thesis_fit_card ----------
thesis = ThesisMatchResult(
    overall_match=85.0,
    sector_fit="High",
    stage_fit="Seed",
    geography_fit="Pan-Africa",
    evidence_fit="Moderate",
    notes=["Note one.", "Note two."],
    status=ThesisStatus.PASS,
)

# Clear previous mock calls
mock_st.reset_mock()

# Call the function (the final render has been temporarily replaced with st.warning)
t_ui.render_thesis_fit_card(thesis)

# Collect evidence
calls = mock_st.mock_calls
print("--- THESIS FIT: mock_st calls (index, call) ---")
for i, c in enumerate(calls):
    print(i, c)

# Search for any calls that contain raw HTML-like content
html_calls = []
for i, c in enumerate(calls):
    # c is a call object like call.markdown(arg, unsafe_allow_html=True)
    try:
        method = c[0]
        args = c[1]
        kwargs = c[2]
    except Exception:
        # Fallback: parse str
        s = str(c)
        if "(" in s:
            method = s.split("(", 1)[0]
        else:
            method = str(c)
        args = c.args if hasattr(c, "args") else ()
        kwargs = c.kwargs if hasattr(c, "kwargs") else {}
    if args:
        for a in args:
            if isinstance(a, str) and ("<div" in a or "&lt;div" in a or "<span" in a or "&lt;span" in a or "<br" in a or "&lt;br" in a):
                html_calls.append((i, method, a[:400]))

# Print results for Thesis Fit
print("\n--- THESIS FIT: HTML-like calls found ---")
if not html_calls:
    print("No calls with HTML-like content detected.")
else:
    for idx, m, snippet in html_calls:
        print(f"call index={idx} method={m} snippet={snippet!r}")

# Count warnings
warning_calls = [c for c in calls if (str(c).startswith('call.warning(') or (len(c) > 0 and c[0] == 'warning'))]
print(f"\nTHESIS FIT: st.warning call count: {len(warning_calls)}")

# ---------- Test 2: render_twin_syndicate_committee ----------
# Build simple syndicate with two votes
v1 = InvestorVote(
    archetype_id='african_vc',
    investor_name='Amina Okonkwo',
    firm='Sahel Horizon Ventures',
    persona='African VC Partner',
    title='Partner',
    decision=Recommendation.INVEST,
    confidence_score=80,
    key_reasoning='Strong founder-market fit.',
)
v2 = InvestorVote(
    archetype_id='diaspora_angel',
    investor_name='Fatima Diallo',
    firm='Lagos–London Angel Network',
    persona='Diaspora Angel Investor',
    title='Angel',
    decision=Recommendation.OBSERVE,
    confidence_score=55,
    key_reasoning='Needs traction proof points.',
)

syn = SyndicateDecision(
    votes=[v1, v2],
    majority_vote=Recommendation.INVEST,
    average_score=67.5,
    dissent_index=10.0,
    consensus_score=67.5,
    final_recommendation=Recommendation.INVEST,
    debate_transcript='Amina: We should invest.\nFatima: I have concerns about traction.'
)

brief = InvestmentBrief(
    founder_name='Test Founder',
    startup_name='Test Startup',
    syndicate=syn,
)

# Clear previous mock calls
mock_st.reset_mock()

# Call the function (final scoreboard render replaced with st.warning)
ui_module.render_twin_syndicate_committee(brief)

# Collect evidence
calls = mock_st.mock_calls
print("\n--- SCOREBOARD: mock_st calls (index, call) ---")
for i, c in enumerate(calls):
    print(i, c)

# Search for HTML-like content
html_calls = []
for i, c in enumerate(calls):
    try:
        method = c[0]
        args = c[1]
        kwargs = c[2]
    except Exception:
        s = str(c)
        if "(" in s:
            method = s.split("(", 1)[0]
        else:
            method = str(c)
        args = c.args if hasattr(c, "args") else ()
        kwargs = c.kwargs if hasattr(c, "kwargs") else {}
    if args:
        for a in args:
            if isinstance(a, str) and ("<div" in a or "&lt;div" in a or "<span" in a or "&lt;span" in a or "<br" in a or "&lt;br" in a):
                html_calls.append((i, method, a[:400]))

print("\n--- SCOREBOARD: HTML-like calls found ---")
if not html_calls:
    print("No calls with HTML-like content detected.")
else:
    for idx, m, snippet in html_calls:
        print(f"call index={idx} method={m} snippet={snippet!r}")

warning_calls = [c for c in calls if (str(c).startswith('call.warning(') or (len(c) > 0 and c[0] == 'warning'))]
print(f"\nSCOREBOARD: st.warning call count: {len(warning_calls)}")

# End
print('\n--- TEST HARNESS COMPLETE ---')
