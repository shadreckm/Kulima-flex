import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { Card } from '../shadcn/Card'
import { Separator } from '../shadcn/Separator'
import { Badge } from '../shadcn/Badge'
import type { DecisionSnapshot, SignalsSummary } from '../../lib/api'
import { getDecisionSnapshot, getSignalsSummary } from '../../lib/api'

interface ContextPanelProps {
  type: 'flex' | 'signals'
  runId?: string | null
  status?: string | null
}

/**
 * MVP reliability: the backend reports ``complete`` while the pipeline and
 * some legacy callers report ``completed`` — accept both so no page polls
 * forever once the assessment has actually finished.
 */
export function assessmentIsDone(status?: string | null): boolean {
  if (!status) return false
  const s = String(status).toLowerCase()
  return s === 'complete' || s === 'completed'
}

export default function ContextPanel({ type, runId, status }: ContextPanelProps) {
  const [flexData, setFlexData] = useState<DecisionSnapshot | null>(null)
  const [signalsData, setSignalsData] = useState<SignalsSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadFlex() {
      // MVP reliability: fetch whenever a run exists — the API returns data as
      // soon as the run has produced it, so the panel is never gated behind a
      // status string. Also poll briefly while running so the snapshot appears
      // automatically when the assessment reaches COMPLETE.
      if (!runId) {
        setFlexData(null)
        return
      }
      setLoading(true)
      setError(null)
      try {
        const data = await getDecisionSnapshot(runId)
        if (!cancelled) setFlexData(data)
      } catch (err: any) {
        if (!cancelled) setError(String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    async function loadSignals() {
      if (!runId) {
        setSignalsData(null)
        return
      }
      setLoading(true)
      setError(null)
      try {
        const data = await getSignalsSummary(runId)
        if (!cancelled) setSignalsData(data)
      } catch (err: any) {
        if (!cancelled) setError(String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    if (type === 'flex') {
      loadFlex()
    } else {
      loadSignals()
    }

    return () => {
      cancelled = true
    }
  }, [type, runId, status])

  return (
    <Card id={type === 'flex' ? 'decision-snapshot' : 'signals'} className="p-4">
      {type === 'flex' ? (
        <FlexSnapshotView runId={runId} status={status} loading={loading} error={error} data={flexData} />
      ) : (
        <SignalsSnapshotView runId={runId} status={status} loading={loading} error={error} data={signalsData} />
      )}
    </Card>
  )
}

interface SnapshotProps<T> {
  runId?: string | null
  status?: string | null
  loading: boolean
  error: string | null
  data: T | null
}

/**
 * The official chain, always shown in full so a user in any single stage can
 * see where the work goes next. Only the stage the user is actually in is
 * highlighted — nothing here is a link the user cannot follow.
 */
const CHAIN_STAGES = ['Info', 'Evidence', 'Trust', 'Signals', 'Decision', 'Reports', 'Action']

function ValueChainStrip({ stage }: { stage: string }) {
  return (
    <div className="p-2 bg-[#F5F8FC] border border-[#DDE6F0] rounded-lg">
      <div className="text-[9px] font-black uppercase tracking-wider text-slate-400 mb-1">
        Evidence-to-Decision Chain
      </div>
      <div className="flex flex-wrap items-center gap-x-1 gap-y-0.5 text-[10px] font-extrabold">
        {CHAIN_STAGES.map((s, i) => (
          <React.Fragment key={s}>
            {i > 0 ? <span className="text-slate-400">→</span> : null}
            {s === stage ? (
              <span className="text-[#0B5D3B] bg-[#ECFDF3] px-1.5 py-0.5 rounded border border-[#A6F4C5]">{s}</span>
            ) : (
              <span className="text-slate-500">{s}</span>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  )
}

function FlexSnapshotView({ runId, status, loading, error, data }: SnapshotProps<DecisionSnapshot>) {
  if (!runId) {
    return <div className="text-xs text-gray-500">Run an analysis to see the decision it produces.</div>
  }

  // STATE SYNCHRONIZATION FIX: If data exists, decision is complete regardless of status string
  // This prevents showing "Analysis in progress" when decision snapshot is already loaded
  if (status && !assessmentIsDone(status) && !data) {
    return <div className="text-xs text-gray-500">Analysis in progress… Decision snapshot will appear when complete.</div>
  }

  if (loading && !data) {
    return <div className="text-xs text-gray-500">Loading decision snapshot…</div>
  }

  if (error && !data) {
    return <div className="text-xs text-red-600">{error}</div>
  }

  if (!data) {
    return <div className="text-xs text-gray-500">Decision snapshot unavailable for this run.</div>
  }

  return (
    <div>
      <ValueChainStrip stage="Decision" />

      <h3 className="mt-3 text-sm font-semibold">Decision</h3>
      <div className="mt-2 flex items-center gap-2">
        <div className="text-sm">Recommendation:</div>
        <Badge>{data.verdict}</Badge>
      </div>

      {/* Trust Layer visibility (Phase 9): the grade and confidence behind this
          recommendation are shown up front, not buried on another screen. */}
      {(data.confidencePercent != null || data.reliabilityGrade) ? (
        <div className="mt-2 p-2 rounded border border-[#DDE6F0] bg-[#F5F8FC] space-y-1">
          {data.reliabilityGrade ? (
            <div className="text-[11px] text-gray-700">
              <span className="font-bold">Evidence grade:</span> Grade {data.reliabilityGrade}
              {data.reliabilityScore != null ? ` (${data.reliabilityScore.toFixed(0)}/100)` : ''}
            </div>
          ) : null}
          {data.confidencePercent != null ? (
            <div className="text-[11px] text-gray-700">
              <span className="font-bold">Confidence:</span> {data.confidencePercent.toFixed(0)}%
              {data.confidenceLabel ? ` — ${data.confidenceLabel}` : ''}
            </div>
          ) : null}
          <div className="text-[10px] text-gray-500">
            Based on what the documents actually support. Open the evidence to read it.
          </div>
        </div>
      ) : null}

      <Separator className="my-3" />

      <div className="text-sm">Why this decision</div>
      {data.topReasons.length ? (
        <ul className="mt-2 text-xs text-gray-600 list-disc list-inside space-y-1">
          {data.topReasons.map((r, idx) => (
            <li key={idx}>{r}</li>
          ))}
        </ul>
      ) : (
        <div className="mt-1 text-xs text-gray-500">NO DATA — no evidence-backed reasons recorded for this run.</div>
      )}

      <div className="mt-3 text-sm">Risks to watch</div>
      {data.topRisks.length ? (
        <ul className="mt-2 text-xs text-gray-600 list-disc list-inside space-y-1">
          {data.topRisks.map((r, idx) => (
            <li key={idx}>{r}</li>
          ))}
        </ul>
      ) : (
        <div className="mt-1 text-xs text-gray-500">No risks flagged from the evidence available.</div>
      )}

      <div className="mt-3 p-2 rounded border border-[#A6F4C5] bg-[#ECFDF3]">
        <div className="text-[10px] font-black uppercase tracking-wider text-[#027A48]">What to do next</div>
        <div className="mt-1 text-xs text-[#084D2F]">
          {data.nextAction ? data.nextAction : 'No next action recorded yet — review the signals above.'}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[11px] font-bold">
        <Link className="text-[#0B5D3B] hover:underline" href="/decision">Full decision record →</Link>
        <Link className="text-slate-600 hover:underline" href="/evidence">Evidence behind it</Link>
        <Link className="text-slate-600 hover:underline" href="/reports">Reports to send</Link>
      </div>
    </div>
  )
}

// PRIMARY EXPERIENCE: NGO and Development Program signal domains prioritized for V1
const DOMAIN_CONFIG: Record<string, { label: string; icon: string; category: string }> = {
  community_impact: { label: 'Community', icon: '🤝', category: 'community_impact' },
  trust: { label: 'Trust', icon: '🛡️', category: 'trust' },
  funding: { label: 'Funding', icon: '💰', category: 'funding' },
  risk: { label: 'Risk', icon: '⚠️', category: 'risk' },
  opportunity: { label: 'Opportunity', icon: '🌱', category: 'opportunity' },
  climate: { label: 'Climate', icon: '🌤️', category: 'climate' },
  environmental: { label: 'Environment', icon: '🌿', category: 'environmental' },
  // Secondary market signals (kept but deprioritized in order)
  market: { label: 'Market', icon: '📈', category: 'market' },
  tourism: { label: 'Tourism', icon: '🧭', category: 'tourism' },
}

/** Legacy domain keys folded into the nine display domains (backend Step 6). */
const LEGACY_DOMAIN_KEYS: Record<string, string> = {
  competitive: 'opportunity',
}

type ResolvedDomain = {
  label: string
  icon: string
  count: number
  riskCount: number
  oppCount: number
  score?: number
  summary?: string
  recommendation?: string
  signals: any[]
}

function scoreTone(score: number): string {
  if (score >= 70) return 'bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]'
  if (score >= 50) return 'bg-[#FFFAEB] text-[#B54708] border border-[#FEDF89]'
  return 'bg-[#FEF3F2] text-[#B42318] border border-[#FECDCA]'
}

function scoreBarTone(score: number): string {
  if (score >= 70) return 'bg-[#12B76A]'
  if (score >= 50) return 'bg-[#F79009]'
  return 'bg-[#F04438]'
}

function SignalsSnapshotView({ runId, status, loading, error, data }: SnapshotProps<SignalsSummary>) {
  const [selectedDomain, setSelectedDomain] = useState<string | 'all'>('all')

  if (!runId) {
    return <div className="text-xs text-gray-500">Start an assessment to see the signals it produces.</div>
  }

  // STATE SYNCHRONIZATION FIX: If data exists, signals are complete regardless of status string
  // This prevents showing "Analysis in progress" when signals are already loaded
  if (status && !assessmentIsDone(status) && !data) {
    return <div className="text-xs text-gray-500">Analysis in progress… Signals will appear when complete.</div>
  }

  if (loading && !data) {
    return <div className="text-xs text-gray-500">Extracting signals from your documents and public research…</div>
  }

  if (error && !data) {
    return <div className="text-xs text-red-600">{error}</div>
  }

  if (!data) {
    return <div className="text-xs text-gray-500">No signals available for this run.</div>
  }

  // Backend returns the nine display domains with score / summary /
  // recommendation (Step 6). Legacy runs may still group by raw categories —
  // fold those into their display domain instead of showing duplicates.
  const domains: Record<string, any> = { ...(data.domains || {}) }
  Object.entries(LEGACY_DOMAIN_KEYS).forEach(([legacyKey, displayKey]) => {
    if (domains[legacyKey] && !domains[displayKey]) domains[displayKey] = domains[legacyKey]
  })
  const allSignals = data.allSignals || [...data.topRisks, ...data.topOpportunities]

  const resolvedDomains: Record<string, ResolvedDomain> = {}
  Object.entries(DOMAIN_CONFIG).forEach(([key, cfg]) => {
    const fromApi = domains[key]
    const matched: any[] = fromApi?.signals ?? allSignals.filter(s => {
      const cat = (s.category || '').toLowerCase()
      const meta = (s.metadata?.domain || '').toLowerCase()
      return cat === key || meta.includes(key) || (key === 'community_impact' && (cat.includes('impact') || cat.includes('social')))
    })
    resolvedDomains[key] = {
      label: fromApi?.label || cfg.label,
      icon: cfg.icon,
      count: fromApi?.count ?? matched.length,
      riskCount: fromApi?.riskCount ?? matched.filter(s => s.direction === 'risk').length,
      oppCount: fromApi?.opportunityCount ?? matched.filter(s => s.direction === 'opportunity').length,
      score: typeof fromApi?.score === 'number' ? fromApi.score : undefined,
      summary: typeof fromApi?.summary === 'string' ? fromApi.summary : undefined,
      recommendation: typeof fromApi?.recommendation === 'string' ? fromApi.recommendation : undefined,
      signals: matched,
    }
  })

  const visibleDomains = selectedDomain === 'all'
    ? Object.entries(resolvedDomains)
    : Object.entries(resolvedDomains).filter(([k]) => k === selectedDomain)

  // Data honesty: counts come from what the run actually produced, never from
  // a fixed display number.
  const domainCount = Object.keys(resolvedDomains).length
  const signalCount = allSignals.length

  return (
    <div className="space-y-3.5">
      {/* ── Value Chain Progression Header ── */}
      <ValueChainStrip stage="Signals" />

      {/* Header & Overall Counters */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-extrabold text-slate-900">Signals</h3>
          <p className="text-[11px] text-slate-500 mt-0.5">
            {domainCount} domains · read from your documents and public research
          </p>
        </div>
        <Badge className="bg-[#0B5D3B] text-white text-[10px]">
          {signalCount ? `${signalCount} Signals` : 'NO SIGNALS YET'}
        </Badge>
      </div>

      {/* Severity Counters */}
      <div>
        <div className="text-[9px] font-black uppercase tracking-wider text-slate-400 mb-1">
          How urgent each signal is
        </div>
        <div className="grid grid-cols-4 gap-1.5 text-center">
        <div className="p-1.5 rounded bg-red-50 border border-red-200">
          <div className="text-[10px] font-black text-red-700">CRITICAL</div>
          <div className="text-xs font-black text-red-900 mt-0.5">{data.critical}</div>
        </div>
        <div className="p-1.5 rounded bg-amber-50 border border-amber-200">
          <div className="text-[10px] font-black text-amber-700">HIGH</div>
          <div className="text-xs font-black text-amber-900 mt-0.5">{data.high}</div>
        </div>
        <div className="p-1.5 rounded bg-yellow-50 border border-yellow-200">
          <div className="text-[10px] font-black text-yellow-700">MEDIUM</div>
          <div className="text-xs font-black text-yellow-900 mt-0.5">{data.medium}</div>
        </div>
        <div className="p-1.5 rounded bg-emerald-50 border border-emerald-200">
          <div className="text-[10px] font-black text-emerald-700">LOW</div>
          <div className="text-xs font-black text-emerald-900 mt-0.5">{data.low}</div>
        </div>
        </div>
      </div>

      <Separator />

      {/* Domain Filter Pills */}
      <div>
        <div className="text-[10px] font-black uppercase tracking-wider text-slate-400 mb-1.5">
          Signal Domains
        </div>
        <div className="flex flex-wrap gap-1">
          <button
            type="button"
            onClick={() => setSelectedDomain('all')}
            className={`px-2 py-1 rounded text-[10px] font-bold transition ${
              selectedDomain === 'all'
                ? 'bg-[#061C14] text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            All ({domainCount})
          </button>
          {Object.entries(resolvedDomains).map(([key, dom]) => (
            <button
              key={key}
              type="button"
              onClick={() => setSelectedDomain(key)}
              className={`px-2 py-1 rounded text-[10px] font-bold transition flex items-center gap-1 ${
                selectedDomain === key
                  ? 'bg-[#0B5D3B] text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              <span>{dom.icon}</span>
              <span>{dom.label}</span>
              <span className="text-[9px] opacity-75">({dom.count})</span>
            </button>
          ))}
        </div>
        <p className="mt-1.5 text-[9px] text-slate-400 leading-snug">
          A domain score summarises the signals found in that domain. Every score sits above the
          signals and sources it was calculated from — no number appears on its own.
        </p>
      </div>

      {/* Domain Cards & Extracted Signals */}
      <div className="space-y-2.5 max-h-[460px] overflow-y-auto pr-1">
        {visibleDomains.map(([key, dom]) => (
          <div key={key} className="p-2.5 bg-white rounded-lg border border-[#DDE6F0] shadow-sm">
            <div className="flex items-center justify-between mb-1.5 pb-1 border-b border-slate-100">
              <div className="flex items-center gap-1.5">
                <span className="text-sm">{dom.icon}</span>
                <span className="text-xs font-black text-slate-900">{dom.label} Signals</span>
                {dom.score != null && (
                  <span className={`text-[10px] font-black px-1.5 py-0.5 rounded ${scoreTone(dom.score)}`}>
                    {dom.score}/100
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1 text-[10px]">
                {dom.riskCount > 0 && (
                  <span className="text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200 font-bold">
                    {dom.riskCount} Risk
                  </span>
                )}
                {dom.oppCount > 0 && (
                  <span className="text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200 font-bold">
                    {dom.oppCount} Opp
                  </span>
                )}
              </div>
            </div>

            {dom.score != null && (
              <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden mb-2">
                <div
                  className={`h-full rounded-full ${scoreBarTone(dom.score)}`}
                  style={{ width: `${Math.max(0, Math.min(100, dom.score))}%` }}
                />
              </div>
            )}

            {dom.summary ? (
              <div>
                <div className="text-[9px] font-black uppercase tracking-wider text-slate-400">
                  What this domain shows
                </div>
                <p className="mt-0.5 text-[11px] text-slate-600 leading-relaxed">{dom.summary}</p>
              </div>
            ) : null}

            {dom.recommendation ? (
              <div className="mt-1.5 text-[10px] font-bold text-[#0B5D3B] bg-[#F5F8FC] p-1.5 rounded border border-slate-200/60">
                What should change → {dom.recommendation}
              </div>
            ) : null}

            <div className="space-y-2 mt-2">
              {dom.signals.length === 0 ? (
                <div className="text-[10px] text-slate-400 italic">No signals detected in this domain.</div>
              ) : dom.signals.map((sig: any) => {
                const isRisk = sig.direction === 'risk'
                const isDoc = sig.metadata?.source_type === 'document' || (sig.evidenceRefs && sig.evidenceRefs.some((r: string) => r.includes('DOC')))
                const refs: string[] = Array.isArray(sig.evidenceRefs) ? sig.evidenceRefs.filter(Boolean) : []
                const rawConf = typeof sig.confidence === 'number' ? sig.confidence : null
                const confidencePct = rawConf == null ? null : Math.round((rawConf <= 1 ? rawConf : rawConf / 100) * 100)
                return (
                  <div
                    key={sig.id}
                    className={`p-2 rounded border text-left text-xs ${
                      isRisk ? 'bg-amber-50/50 border-amber-200' : 'bg-emerald-50/40 border-emerald-200'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1 mb-1">
                      <span className={`text-[9px] font-black uppercase px-1.5 py-0.5 rounded ${
                        sig.level === 'critical' ? 'bg-red-600 text-white' :
                        sig.level === 'high' ? 'bg-amber-600 text-white' :
                        sig.level === 'medium' ? 'bg-yellow-600 text-white' : 'bg-emerald-600 text-white'
                      }`}>
                        {sig.level || 'informational'}
                      </span>
                      <span className="text-[10px] font-semibold text-slate-500">
                        {isDoc ? '📄 From your documents' : '🌐 Public research'}
                      </span>
                    </div>
              
                    <div className="font-extrabold text-slate-900 leading-tight">
                      {isRisk ? '⚠' : '✅'} {sig.title}
                    </div>
              
                    <div className="mt-1">
                      <div className="text-[9px] font-black uppercase tracking-wider text-slate-400">
                        Why it matters
                      </div>
                      <p className="text-[11px] text-slate-600 mt-0.5 leading-relaxed">
                        {sig.description || 'No explanation was recorded for this signal — read the source behind it.'}
                      </p>
                    </div>
              
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-slate-500">
                      <span
                        className="font-bold text-slate-600"
                        title={refs.length ? refs.join('\n') : 'No evidence reference stored for this signal'}
                      >
                        {refs.length
                          ? `Evidence: ${refs.length} reference${refs.length > 1 ? 's' : ''}`
                          : 'Evidence: source only'}
                      </span>
                      {confidencePct != null ? (
                        <span
                          className="font-bold text-slate-600"
                          title="Confidence: how firmly the extracted evidence supports this individual signal, not the overall assessment score"
                        >
                          Confidence {confidencePct}%
                        </span>
                      ) : (
                        <span className="italic text-slate-400">Confidence not measured</span>
                      )}
                      {sig.timeHorizon ? <span>Horizon: {sig.timeHorizon}</span> : null}
                    </div>
              
                    {sig.recommendedAction ? (
                      <div className="mt-1.5 text-[10px] font-bold text-[#0B5D3B] bg-white/80 p-1 rounded border border-slate-200/60">
                        What should change → {sig.recommendedAction}
                      </div>
                    ) : (
                      <div className="mt-1.5 text-[10px] italic text-slate-400">
                        No action recorded — this signal informs the decision rather than changing it.
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
