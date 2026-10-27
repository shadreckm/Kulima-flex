'use client'

// Admin Console — Phase 4: AI provider health.
//
// The authoritative source is the audit log: every completed assessment writes a
// `provider.health` event carrying which provider answered, whether a fallback was
// needed and how long it took. The live provider manager is shown too, but marked
// as what it is — one worker process's spot check, not a platform total.

import { useState } from 'react'
import AdminConsoleShell from '../../../components/AdminConsole/AdminConsoleShell'
import {
  BarList,
  DataNotes,
  EmptyNote,
  FetchStatus,
  KV,
  Metric,
  Panel,
  Pill,
  Table,
  WindowPicker,
  fmtDateTime,
  fmtInt,
  fmtNum,
  fmtPct,
  mapItems,
  relTime,
  shortId,
} from '../../../components/AdminConsole/adminUi'
import { useAdminFetch } from '../../../hooks/useAdminFetch'
import { getAdminAiHealth, type AdminProviderTier } from '../../../lib/admin'

function ProviderCard({ p }: { p: AdminProviderTier }) {
  const tone = !p.configured ? 'neutral' : p.disabledNow ? 'bad' : p.inChain ? 'good' : 'warn'
  const status = !p.configured
    ? 'no api key'
    : p.disabledNow
      ? 'disabled in process'
      : p.inChain
        ? 'in active chain'
        : 'configured, not in chain'
  return (
    <div className="bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-extrabold text-[#101828]">{p.label}</div>
          <div className="text-[10px] font-mono text-slate-400 truncate" title={p.model}>{p.model || '—'}</div>
        </div>
        <Pill tone={tone as 'good' | 'warn' | 'bad' | 'neutral'}>{p.configured ? 'key set' : 'no key'}</Pill>
      </div>
      <div className="mt-2 text-[11px] font-bold uppercase tracking-wider text-slate-500">{status}</div>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <div>
          <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Assessments</div>
          <div className="text-lg font-black tabular-nums text-slate-900">{fmtInt(p.assessmentsUsingIt)}</div>
        </div>
        <div>
          <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Fell back from it</div>
          <div className="text-lg font-black tabular-nums text-[#B54708]">{fmtInt(p.fallbacksFromIt)}</div>
        </div>
        <div>
          <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Avg response</div>
          <div className="text-xs font-bold text-slate-700">{p.avgResponseMs === null ? 'NO DATA' : `${fmtNum(p.avgResponseMs, 0)} ms`}</div>
        </div>
        <div>
          <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Last seen</div>
          <div className="text-xs font-bold text-slate-700" title={fmtDateTime(p.lastUsedAt)}>{relTime(p.lastUsedAt)}</div>
        </div>
      </div>
    </div>
  )
}

export default function AdminAiHealthPage() {
  const [windowDays, setWindowDays] = useState(30)
  const { data, busy, error, denied, reload } = useAdminFetch(() => getAdminAiHealth(windowDays), [windowDays])

  return (
    <AdminConsoleShell
      section="ai-health"
      title="AI Health"
      description="Gemini, OpenAI, Groq, OpenRouter, HuggingFace and Document Intelligence Mode — usage, latency, failures and fallbacks derived from the audit log."
      toolbar={<WindowPicker value={windowDays} onChange={setWindowDays} />}
      onReload={reload}
      busy={busy}
    >
      <FetchStatus busy={busy} error={error} denied={denied} hasData={!!data} section="AI health" />

      {data ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric
              label="Health events"
              value={fmtInt(data.usage.providerHealthEvents)}
              hint={`Written per completed assessment · ${fmtInt(data.usage.assessmentsStartedInWindow)} assessments started · ${fmtInt(data.usage.analystQuestionsInWindow)} analyst questions in ${data.windowDays}d`}
            />
            <Metric
              label="Fallback rate"
              value={fmtPct(data.fallbacks.fallbackRate)}
              hint={data.fallbacks.definition}
              tone={data.fallbacks.fallbackRate === null ? 'neutral' : data.fallbacks.fallbackRate > 25 ? 'bad' : data.fallbacks.fallbackRate > 10 ? 'warn' : 'good'}
            />
            <Metric
              label="Document Intelligence Mode"
              value={fmtInt(data.documentIntelligence.activations)}
              hint={`Last activation ${relTime(data.documentIntelligence.lastActivationAt)} · ${fmtPct(data.fallbacks.documentIntelligenceRate)} of health events`}
              tone={data.documentIntelligence.activations > 0 ? 'warn' : 'good'}
            />
            <Metric
              label="Median latency"
              value={data.latency.medianMs === null ? null : `${fmtNum(data.latency.medianMs, 0)} ms`}
              hint={`p95 ${data.latency.p95Ms === null ? 'NO DATA' : `${fmtNum(data.latency.p95Ms, 0)} ms`} from ${fmtInt(data.latency.samples)} non-fallback samples · LLM timeout ${data.latency.llmTimeoutSeconds}s`}
            />
          </div>

          {data.usage.emptyReason ? (
            <Panel title="Why this page is empty" note="Honesty over zeros: these metrics come from real assessment runs. Nothing has completed yet, so nothing is measured.">
              <EmptyNote label={data.usage.emptyReason} />
            </Panel>
          ) : null}

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {data.providers.map(p => <ProviderCard key={p.id} p={p} />)}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Panel
              title="Provider chain"
              note={data.chain.note}
              right={<Pill tone={data.chain.configuredTiers.length ? 'good' : 'bad'}>{data.chain.configuredTiers.length} of 5 tiers keyed</Pill>}
            >
              <div className="flex flex-col">
                <KV label="Active order (this process)" value={<span className="font-mono text-[11px]">{data.chain.activeOrder.join(' → ') || 'none'}</span>} />
                <KV label="Configured by env" value={<span className="font-mono text-[11px]">{data.chain.configuredByEnv.join(' → ') || '—'}</span>} />
                <KV label="Tiers with a key" value={data.chain.configuredTiers.join(', ') || 'none'} />
                <KV
                  label="Tiers without a key"
                  value={data.chain.unconfiguredTiers.length
                    ? <span className="text-[#B54708] font-bold">{data.chain.unconfiguredTiers.join(', ')}</span>
                    : 'all five configured'}
                />
                <KV
                  label="Disabled in this process"
                  value={data.chain.disabledInProcess.length
                    ? <Pill tone="bad">{data.chain.disabledInProcess.join(', ')}</Pill>
                    : <Pill tone="good">none</Pill>}
                />
                <KV
                  label="External research"
                  value={(
                    <span className="flex items-center gap-2">
                      {data.externalResearch.provider}
                      {data.externalResearch.configured ? <Pill tone="good">key set</Pill> : <Pill tone="warn">no key</Pill>}
                      <span className="text-[11px] font-normal text-slate-500">max {data.externalResearch.maxResults} results · allow-listed fields only</span>
                    </span>
                  )}
                />
              </div>
            </Panel>

            <Panel title="Usage by provider" note="Health events and fallbacks per provider tier, from the audit log.">
              <BarList
                items={Object.entries(data.usage.perProvider).map(([k, v]) => ({ label: k, value: v.events }))}
                emptyLabel="NO DATA — no provider.health events yet."
              />
              <div className="mt-4">
                <Table
                  headers={['Provider', 'Events', 'Fallbacks']}
                  rows={Object.entries(data.usage.perProvider).map(([k, v]) => [
                    <span className="font-mono text-[11px] font-bold">{k}</span>,
                    fmtInt(v.events),
                    fmtInt(v.fallbacks),
                  ])}
                />
              </div>
            </Panel>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Panel
              title="Failures"
              note="Pipeline runs are tracked separately from provider health: a run can fail after every tier has already been tried."
              right={<Pill tone={data.failures.failedRuns > 0 ? 'bad' : 'good'}>{fmtInt(data.failures.failedRuns)} failed · {fmtInt(data.failures.runningRuns)} running</Pill>}
            >
              <BarList items={mapItems(data.failures.runsByStatus)} emptyLabel="NO DATA — no pipeline runs recorded." />
              <div className="mt-4">
                <Table
                  headers={['Run', 'When', 'Error']}
                  rows={data.failures.recentFailedRuns.map(f => [
                    <div>
                      <div className="font-mono text-[11px] font-bold text-slate-700">{shortId(f.runId, 18)}</div>
                      <div className="text-[10px] text-slate-400">{shortId(f.orgId, 16)}</div>
                    </div>,
                    <span title={fmtDateTime(f.createdAt)}>{relTime(f.createdAt)}</span>,
                    <span className="text-[11px] text-[#B42318]">{f.errorMessage || 'no error message stored'}</span>,
                  ])}
                />
              </div>
            </Panel>

            <Panel title="Fallbacks" note={data.fallbacks.definition}>
              <div className="flex flex-col">
                <KV label="Fallback events" value={fmtInt(data.fallbacks.fallbackEvents)} />
                <KV label="Fallback rate" value={fmtPct(data.fallbacks.fallbackRate)} />
                <KV label="Document Intelligence activations" value={fmtInt(data.fallbacks.documentIntelligenceActivations)} />
                <KV label="Research degraded to documents" value={fmtInt(data.fallbacks.researchDegradedToDocuments)} />
              </div>
              <div className="mt-4 p-3 rounded-lg bg-[#F5F8FC] border border-[#DDE6F0]">
                <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">{data.documentIntelligence.modeLabel}</div>
                <p className="mt-1 text-[11px] text-slate-600 leading-relaxed">{data.documentIntelligence.explanation}</p>
              </div>
            </Panel>
          </div>

          <Panel
            title="Last generation seen by this worker"
            note={data.processSnapshot.note}
          >
            {data.processSnapshot.lastResult ? (
              <div className="flex flex-col">
                <KV label="Provider / model" value={`${data.processSnapshot.lastResult.provider} · ${data.processSnapshot.lastResult.model}`} />
                <KV label="Analysis mode" value={data.processSnapshot.lastResult.analysisMode} />
                <KV label="Response time" value={`${fmtNum(data.processSnapshot.lastResult.responseTimeMs, 0)} ms`} />
                <KV
                  label="Fallback"
                  value={data.processSnapshot.lastResult.fallbackTriggered
                    ? <Pill tone="warn">triggered ×{data.processSnapshot.lastResult.fallbackCount}</Pill>
                    : <Pill tone="good">first tier</Pill>}
                />
              </div>
            ) : (
              <EmptyNote label="NO DATA — this process has not served a generation since it started. The audit-derived numbers above are the platform truth." />
            )}
          </Panel>

          <DataNotes notes={data.dataNotes} />
        </>
      ) : null}
    </AdminConsoleShell>
  )
}
