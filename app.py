import streamlit as st
import sqlite3
from tavily import TavilyClient

# ----------------------------------
# PAGE CONFIG
# ----------------------------------

st.set_page_config(
    page_title="Kulima FLEX VC Brain",
    page_icon="🚀",
    layout="wide"
)

# ----------------------------------
# TAVILY
# ----------------------------------

client = TavilyClient(
    api_key="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"
)

# ----------------------------------
# DATABASE
# ----------------------------------

conn = sqlite3.connect("founders.db")

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS founders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    founder_name TEXT,
    startup_name TEXT,
    founder_score INTEGER,
    trust_score INTEGER
)
""")

conn.commit()

# ----------------------------------
# HEADER
# ----------------------------------

st.title("🚀 Kulima FLEX VC Brain")

st.caption(
    "AI-Powered Founder Discovery, Trust Verification and Investment Intelligence"
)

st.divider()

# ----------------------------------
# INPUTS
# ----------------------------------

col1, col2 = st.columns(2)

with col1:
    founder = st.text_input(
        "Founder Name",
        placeholder="Sam Altman"
    )

with col2:
    startup = st.text_input(
        "Startup Name",
        placeholder="OpenAI"
    )

# ----------------------------------
# ANALYZE
# ----------------------------------

if st.button("Analyze Founder"):

    if founder.strip() == "":
        st.warning("Please enter a founder name.")

    else:

        query = f"""
        {founder}
        {startup}
        founder entrepreneur startup
        funding company technology
        """

        with st.spinner("Analyzing Founder..."):

            results = client.search(
                query=query,
                search_depth="advanced"
            )

            evidence = results.get(
                "results",
                []
            )

            evidence_count = len(evidence)

            founder_score = min(
                50 + evidence_count * 5,
                100
            )

            trust_score = min(
                evidence_count * 10,
                100
            )

            # VC Decision

            if founder_score >= 80:
                decision = "✅ INVEST"

            elif founder_score >= 65:
                decision = "🟡 FURTHER DUE DILIGENCE"

            else:
                decision = "🔴 PASS"

            # Save to Memory

            cursor.execute(
                """
                INSERT INTO founders
                (
                    founder_name,
                    startup_name,
                    founder_score,
                    trust_score
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    founder,
                    startup,
                    founder_score,
                    trust_score
                )
            )

            conn.commit()

            st.success(
                "Analysis Complete"
            )

            # ----------------------------------
            # METRICS
            # ----------------------------------

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Founder Score",
                founder_score
            )

            c2.metric(
                "Trust Score",
                trust_score
            )

            c3.metric(
                "Evidence Sources",
                evidence_count
            )

            c4.metric(
                "VC Decision",
                decision
            )

            st.divider()

            # ----------------------------------
            # EXPLAINABLE AI
            # ----------------------------------

            st.subheader(
                "🧠 Why This Score?"
            )

            reasons = []

            if evidence_count > 3:
                reasons.append(
                    "Multiple online sources identified."
                )

            if founder_score >= 70:
                reasons.append(
                    "Strong public founder footprint."
                )

            if trust_score >= 50:
                reasons.append(
                    "Evidence discovered from independent sources."
                )

            if len(reasons) == 0:
                reasons.append(
                    "Limited public information available."
                )

            for reason in reasons:
                st.write(
                    "✅",
                    reason
                )

            st.divider()

            # ----------------------------------
            # INVESTMENT MEMO
            # ----------------------------------

            st.subheader(
                "📄 Investment Memo"
            )

            memo = f"""
Founder: {founder}

Startup: {startup}

Founder Score: {founder_score}/100

Trust Score: {trust_score}/100

Evidence Sources: {evidence_count}

VC Decision:
{decision}

Strengths:
• Discoverable founder profile
• Public activity detected
• Multiple evidence sources available

Risks:
• Financial claims unverified
• Product traction not independently verified

Recommended Next Step:
Conduct founder interview and deeper due diligence.
"""

            st.text_area(
                "Generated Memo",
                memo,
                height=300
            )

            st.divider()

            # ----------------------------------
            # EVIDENCE
            # ----------------------------------

            st.subheader(
                "🔍 Evidence Sources"
            )

            for item in evidence:

                title = item.get(
                    "title",
                    "Unknown Source"
                )

                content = item.get(
                    "content",
                    ""
                )

                url = item.get(
                    "url",
                    ""
                )

                with st.expander(title):

                    st.write(content)

                    st.write(url)

# ----------------------------------
# MEMORY
# ----------------------------------

st.divider()

st.subheader(
    "🧠 Founder Memory"
)

history = cursor.execute("""
SELECT
founder_name,
startup_name,
founder_score,
trust_score
FROM founders
ORDER BY id DESC
LIMIT 20
""").fetchall()

if history:

    st.dataframe(
        history,
        use_container_width=True
    )

conn.close()