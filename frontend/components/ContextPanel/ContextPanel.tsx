import React, { useEffect, useState } from 'react'
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

export default function ContextPanel({ type, runId, status }: ContextPanelProps) {
  const [flexData, setFlexData] = useState<DecisionSnapshot | null>(null)
  const [signalsData, setSignalsData] = useState<SignalsSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadFlex() {
      if (!runId || status !== 'completed') {
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
      if (!runId || status !== 'completed') {
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

function FlexSnapshotView({ runId, status, loading, error, data }: SnapshotProps<DecisionSnapshot>) {
  if (!runId) {
    return <div className="text-xs text-gray-500">Run an analysis to see the decision snapshot.</div>
  }

  if (status && status !== 'completed') {
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
      <h3 className="text-sm font-semibold">Decision Snapshot</h3>
      <div className="mt-3 flex items-center gap-2">
        <div className="text-sm">Recommendation:</div>
        <Badge>{data.verdict}</Badge>
      </div>
      {data.confidencePercent != null && (
        <div className="mt-2 text-xs text-gray-500">
          Confidence: {data.confidencePercent.toFixed(0)}%
          {data.confidenceLabel ? ` (${data.confidenceLabel})` : ''}
        </div>
      )}
      {data.reliabilityGrade && (
        <div className="mt-1 text-xs text-gray-500">
          Reliability: Grade {data.reliabilityGrade}
          {data.reliabilityScore != null ? ` (${data.reliabilityScore.toFixed(0)}/100)` : ''}
        </div>
      )}
      <Separator className="my-3" />
      <div className="text-sm">Top Reasons</div>
      <ul className="mt-2 text-xs text-gray-600 list-disc list-inside space-y-1">
        {data.topReasons.map((r, idx) => (
          <li key={idx}>{r}</li>
        ))}
      </ul>
      <div className="mt-3 text-sm">Top Risks</div>
      <ul className="mt-2 text-xs text-gray-600 list-disc list-inside space-y-1">
        {data.topRisks.map((r, idx) => (
          <li key={idx}>{r}</li>
        ))}
      </ul>
      <div className="mt-3 text-sm">Next Action</div>
      <div className="mt-1 text-xs text-gray-700">{data.nextAction}</div>
    </div>
  )
}

const DOMAIN_CONFIG: Record<string, { label: string; icon: string; category: string }> = {
  trust: { label: 'Trust', icon: '🛡️', category: 'trust' },
  risk: { label: 'Risk', icon: '⚠️', category: 'risk' },
  opportunity: { label: 'Opportunity', icon: '🌱', category: 'opportunity' },
  market: { label: 'Market', icon: '📈', category: 'market' },
  funding: { label: 'Funding', icon: '💰', category: 'funding' },
  climate: { label: 'Climate', icon: '🌤️', category: 'climate' },
  environmental: { label: 'Environment', icon: '🌿', category: 'environmental' },
  tourism: { label: 'Tourism', icon: '🧭', category: 'tourism' },
  community_impact: { label: 'Community', icon: '🤝', category: 'community_impact' },
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
    return <div className="text-xs text-gray-500">Select or create an evaluation to inspect signal intelligence.</div>
  }

  if (status && status !== 'completed') {
    return <div className="text-xs text-gray-500">Analysis in progress… Signals will appear when complete.</div>
  }

  if (loading && !data) {
    return <div className="text-xs text-gray-500">Extracting signals from documents and Tavily OSINT…</div>
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

  return (
    <div className="space-y-3.5">
      {/* ── Value Chain Progression Header ── */}
      <div className="p-2 bg-[#F5F8FC] border border-[#DDE6F0] rounded-lg">
        <div className="text-[9px] font-black uppercase tracking-wider text-slate-400 mb-1">
          Decision Intelligence Value Chain
        </div>
        <div className="flex items-center justify-between text-[10px] font-extrabold">
          <span className="text-slate-500">Info</span>
          <span className="text-slate-400">→</span>
          <span className="text-slate-500">Evidence</span>
          <span className="text-slate-400">→</span>
          <span className="text-slate-500">Trust</span>
          <span className="text-slate-400">→</span>
          <span className="text-[#0B5D3B] bg-[#ECFDF3] px-1.5 py-0.5 rounded border border-[#A6F4C5]">Signals</span>
          <span className="text-slate-400">→</span>
          <span className="text-slate-500">Decision</span>
        </div>
      </div>

      {/* Header & Overall Counters */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-extrabold text-slate-900">Signals Intelligence</h3>
          <p className="text-[11px] text-slate-500 mt-0.5">9 Verified Domains · Docs & Tavily OSINT</p>
        </div>
        <Badge className="bg-[#0B5D3B] text-white text-[10px]">
          {allSignals.length || 9} Signals
        </Badge>
      </div>

      {/* Severity Counters */}
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
            All (9)
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
              <p className="text-[11px] text-slate-600 leading-relaxed">{dom.summary}</p>
            ) : null}

            {dom.recommendation ? (
              <div className="mt-1.5 text-[10px] font-bold text-[#0B5D3B] bg-[#F5F8FC] p-1.5 rounded border border-slate-200/60">
                → Recommendation: {dom.recommendation}
              </div>
            ) : null}

            <div className="space-y-2 mt-2">
              {dom.signals.length === 0 ? (
                <div className="text-[10px] text-slate-400 italic">No signals detected in this domain.</div>
              ) : dom.signals.map((sig: any) => {
                const isRisk = sig.direction === 'risk'
                const isDoc = sig.metadata?.source_type === 'document' || (sig.evidenceRefs && sig.evidenceRefs.some((r: string) => r.includes('DOC')))
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
                        {sig.level}
                      </span>
                      <span className="text-[10px] font-semibold text-slate-500">
                        {isDoc ? '📄 Primary Document' : '🌐 Tavily OSINT Research'}
                      </span>
                    </div>

                    <div className="font-extrabold text-slate-900 leading-tight">
                      {isRisk ? '⚠' : '✅'} {sig.title}
                    </div>
                    <p className="text-[11px] text-slate-600 mt-1 leading-relaxed">
                      {sig.description}
                    </p>

                    {sig.recommendedAction && (
                      <div className="mt-1.5 text-[10px] font-bold text-[#0B5D3B] bg-white/80 p-1 rounded border border-slate-200/60">
                        → Action: {sig.recommendedAction}
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
