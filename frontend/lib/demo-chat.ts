import { loadCurrentRun } from './current-run'

export function buildDemoModeResponse(personaName: string, question: string, runId?: string | null): string {
  const currentRun = loadCurrentRun()
  const startupName = currentRun?.startupName || 'the current assessment'
  const founderName = currentRun?.founderName ? `led by ${currentRun.founderName}` : ''
  const isSignals = personaName.toLowerCase().includes('signal')

  if (isSignals) {
    return `### Signals Analyst Briefing for ${startupName} ${founderName}
- **Status:** Evaluation active (${currentRun?.status || 'processing'})
- **Notice:** The live AI reasoning service is currently synthesizing signals from your uploaded evidence and research streams.
- **Action:** Please check the Signals workspace tab for extracted risk and opportunity signals.`
  }

  return `### AI Analyst Briefing for ${startupName} ${founderName}
- **Status:** Evaluation active (${currentRun?.status || 'processing'})
- **Recommendation Status:** ${currentRun?.recommendation || 'Pending evaluation completion'}
- **Notice:** The live AI reasoning service is currently analyzing the dossier. Full analysis will be available once pipeline processing finishes.`
}

