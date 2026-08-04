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

function SignalsSnapshotView({ runId, status, loading, error, data }: SnapshotProps<SignalsSummary>) {
  if (!runId) {
    return <div className="text-xs text-gray-500">Run an analysis to see signals.</div>
  }

  if (status && status !== 'completed') {
    return <div className="text-xs text-gray-500">Analysis in progress… Signals will appear when complete.</div>
  }

  if (loading && !data) {
    return <div className="text-xs text-gray-500">Loading signals…</div>
  }

  if (error && !data) {
    return <div className="text-xs text-red-600">{error}</div>
  }

  if (!data) {
    return <div className="text-xs text-gray-500">No signals available for this run.</div>
  }

  return (
    <div>
      <h3 className="text-sm font-semibold">Signals Summary</h3>
      <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-700">
        <div>Critical: <span className="font-semibold">{data.critical}</span></div>
        <div>High: <span className="font-semibold">{data.high}</span></div>
        <div>Medium: <span className="font-semibold">{data.medium}</span></div>
        <div>Low: <span className="font-semibold">{data.low}</span></div>
      </div>
      <Separator className="my-3" />
      {data.topRisks.length > 0 && (
        <div className="mb-3">
          <div className="text-sm">Top Risks</div>
          <ul className="mt-2 text-xs text-gray-600 list-disc list-inside space-y-1">
            {data.topRisks.map((s) => (
              <li key={s.id}>
                [{s.level.toUpperCase()}] {s.title} – {s.description}
              </li>
            ))}
          </ul>
        </div>
      )}
      {data.topOpportunities.length > 0 && (
        <div>
          <div className="text-sm">Top Opportunities</div>
          <ul className="mt-2 text-xs text-gray-600 list-disc list-inside space-y-1">
            {data.topOpportunities.map((s) => (
              <li key={s.id}>
                [{s.level.toUpperCase()}] {s.title} – {s.description}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
