'use client'

import React, { useEffect, useState } from 'react'
import { getActivity, type AuditEventRecord } from '../../lib/enterprise'

// Phase 4 — Activity Timeline. Shows the immutable audit trail for a single
// assessment (or evaluation run). Read-only by design: the backend audit
// stream is append-only, so this view can never diverge from the record.

type ActivityTimelineProps = {
  runId?: string | number | null
  assessmentId?: string | null
  title?: string
  limit?: number
}

const CATEGORY_STYLES: Record<string, string> = {
  Documents: 'bg-amber-50 text-amber-700 border-amber-200',
  Assessments: 'bg-[#EAF3FF] text-[#004085] border-[#D6E8FF]',
  Signals: 'bg-[#F5F8FC] text-slate-600 border-[#DDE6F0]',
  Decision: 'bg-[#ECFDF3] text-[#027A48] border-[#A6F4C5]',
  Reports: 'bg-[#EAF3FF] text-[#004085] border-[#D6E8FF]',
  Access: 'bg-[#F5F8FC] text-slate-600 border-[#DDE6F0]',
  Research: 'bg-[#EAF3FF] text-[#004085] border-[#D6E8FF]',
  Team: 'bg-[#F5F8FC] text-slate-600 border-[#DDE6F0]',
  Billing: 'bg-[#FFF7EB] text-[#B54708] border-[#F5DEB8]',
}

function formatWhen(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function ActivityTimeline({ runId, assessmentId, title = 'Activity Timeline', limit = 50 }: ActivityTimelineProps) {
  const [events, setEvents] = useState<AuditEventRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (runId == null && !assessmentId) {
      setEvents([])
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    getActivity({
      runId: runId ?? undefined,
      assessmentId: assessmentId ?? undefined,
      limit,
    })
      .then(res => {
        if (!cancelled) setEvents(res.events)
      })
      .catch(err => {
        if (!cancelled) setError(String(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [runId, assessmentId, limit])

  return (
    <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
      <div className="flex items-center justify-between pb-3 mb-4 border-b border-[#DDE6F0]">
        <div>
          <h2 className="text-base font-extrabold text-slate-900">{title}</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Append-only governance record: every upload, signal, decision and export for this assessment, in order.
          </p>
        </div>
        <span className="text-xs font-bold px-2.5 py-1 rounded-lg border text-slate-600 bg-[#F5F8FC] border-[#DDE6F0]">
          {loading ? '…' : `${events.length} event${events.length === 1 ? '' : 's'}`}
        </span>
      </div>

      {error ? (
        <div className="text-xs text-slate-500 p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
          Activity unavailable: {error}
        </div>
      ) : events.length === 0 && !loading ? (
        <div className="text-xs text-slate-500 p-4 bg-[#F5F8FC] rounded-lg border border-dashed border-[#DDE6F0] text-center">
          No governance events recorded for this assessment yet.
        </div>
      ) : (
        <ol className="space-y-0">
          {events.map((event, idx) => (
            <li key={event.id} className="flex gap-3">
              {/* Timeline rail */}
              <div className="flex flex-col items-center pt-1.5">
                <span className="w-2 h-2 rounded-full bg-[#0B5D3B] flex-shrink-0" />
                {idx < events.length - 1 ? <span className="w-px flex-1 bg-[#DDE6F0] my-1" /> : null}
              </div>
              <div className="pb-4 min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-extrabold text-slate-900">{event.label || event.eventType}</span>
                  <span
                    className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${
                      CATEGORY_STYLES[event.category] || CATEGORY_STYLES.Signals
                    }`}
                  >
                    {event.category}
                  </span>
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5 font-mono">{formatWhen(event.createdAt)}</div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
