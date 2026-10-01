import { loadAssessmentContext } from './assessment-store'

/**
 * Demo-mode fallback briefing, derived from the shared Assessment Context —
 * no legacy current-run store.
 */
export function buildDemoModeResponse(personaName: string, question: string, runId?: string | null): string {
  const ctx = loadAssessmentContext()
  const startupName = ctx?.displayEntity || ctx?.entityName || 'the current assessment'
  const founderName = ctx?.founderOrLead ? `led by ${ctx.founderOrLead}` : ''
  const isSignals = personaName.toLowerCase().includes('signal')

  if (isSignals) {
    return `### Signals Analyst Briefing for ${startupName} ${founderName}
- **Status:** Evaluation active (${ctx?.status || 'processing'})
- **Notice:** The live AI reasoning service is currently synthesizing signals from your uploaded evidence and research streams.
- **Action:** Please check the Signals workspace tab for extracted risk and opportunity signals.`
  }

  return `### AI Analyst Briefing for ${startupName} ${founderName}
- **Status:** Evaluation active (${ctx?.status || 'processing'})
- **Recommendation Status:** ${ctx?.decision?.recommendation || 'Pending evaluation completion'}
- **Notice:** The live AI reasoning service is currently analyzing the dossier. Full analysis will be available once pipeline processing finishes.`
}

