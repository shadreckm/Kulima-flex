import { findOstxCase, loadCurrentRun } from './current-run'

export function buildDemoModeResponse(personaName: string, question: string, runId?: string | null): string {
  const currentRun = loadCurrentRun()
  const ostx = runId ? findOstxCase(runId) : null
  const startupName = ostx?.startupName || currentRun?.startupName || 'AgriNova Malawi'
  const founderName = ostx?.founderName || currentRun?.founderName || 'Dr. Chimwemwe Phiri'
  const recommendation = ostx?.recommendation || currentRun?.recommendation || 'Invest'
  const trustScore = ostx?.trustScore ?? currentRun?.trustScore ?? 88

  const q = (question || '').toLowerCase()
  const isSignals = personaName.toLowerCase().includes('signal')

  const banner = `**Demo Mode Response**\n\nLive model APIs are currently offline. This response is synthesized directly from the seeded OSTX dataset, decision snapshot, trust score, signals, and evidence integrity for **${startupName}**.\n\n`

  if (isSignals) {
    if (q.includes('risk') || q.includes('critical') || q.includes('red flag')) {
      return banner + `### Key Risk & Evidence Signals for ${startupName}
- **Trust Score:** ${trustScore}/100
- **Evidence Integrity:** ${trustScore > 80 ? 'Grade A (Comprehensive OSINT)' : trustScore > 50 ? 'Grade C (Moderate Conflicts)' : 'Grade F (High Risk)'}
- **Top Signals:**
  1. High institutional corroboration across ministry filings and partner registries.
  2. Currency fluctuation exposure requires FX hedging buffer before Series A.
  3. Mobile-money settlement rails verified live.

**Recommended Action:** Review the Signals and Evidence workspaces for complete source citations.`
    }

    return banner + `### Signals Intelligence Briefing: ${startupName}
- **Founder:** ${founderName}
- **Status:** ${recommendation} (Trust Score: ${trustScore}/100)
- **Signal Summary:** 14 verified claims extracted, 0 critical contradictions, high authority source backing.
- **Next Step:** Consult the Evidence panel for source attribution and verification items.`
  }

  // Ask IC persona
  if (q.includes('invest') || q.includes('recommend') || q.includes('verdict') || q.includes('why')) {
    return banner + `### IC Analysis & Recommendation for ${startupName}
- **Verdict:** **${recommendation}**
- **Trust Score:** **${trustScore}/100**
- **Founder Assessment:** ${founderName} demonstrates exceptional operational track record and verified institutional credibility.
- **Key Investment Rationale:**
  1. Strong unit economics and proven product-market fit in primary operating corridor.
  2. Evidence integrity is verified with high-authority institutional backing.
  3. Clear post-harvest market demand with scalable regional distribution.

**Next Steps for IC:**
1. Finalize check allocation and term sheet terms.
2. Complete final legal verification on cross-border off-take agreements.`
  }

  return banner + `### IC Briefing for ${startupName}
- **Founder:** ${founderName}
- **Verdict:** **${recommendation}** (Trust Score: ${trustScore}/100)
- **Executive Summary:** ${startupName} is an IC-ready venture with strong founder-market fit, verified evidence integrity, and high growth potential in African agricultural supply chains.
- **Recommendation:** Proceed with the ${recommendation} recommendation as detailed in the Decision Snapshot and Reports panel.`
}
