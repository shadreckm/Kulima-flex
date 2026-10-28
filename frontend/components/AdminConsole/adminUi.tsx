import React from 'react'

// Presentational primitives for the internal Admin Console. Kept in one file
// because every screen needs the same honest-number treatment: a metric with no
// denominator renders NO DATA, never a zero that an operator could read as a
// real rate. Same rule the backend applies (admin_ops returns None, not 0).

export const NO_DATA = 'NO DATA'

// ── Formatting ───────────────────────────────────────────────────────────────

export function fmtInt(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NO_DATA
  return Math.round(value).toLocaleString('en-US')
}

export function fmtNum(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NO_DATA
  return value.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

/** Percentages arrive already scaled (0-100) or null for "nothing to divide by". */
export function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NO_DATA
  return `${value.toFixed(1)}%`
}

export function fmtMoney(value: number | null | undefined, currency = 'KES'): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NO_DATA
  return `${currency} ${Math.round(value).toLocaleString('en-US')}`
}

export function fmtBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NO_DATA
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let idx = 0
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024
    idx += 1
  }
  return `${idx === 0 ? Math.round(size) : size.toFixed(1)} ${units[idx]}`
}

export function fmtDate(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function fmtDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return `${d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })} ${d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`
}

export function relTime(value: string | null | undefined): string {
  if (!value) return 'never'
  const t = new Date(value).getTime()
  if (Number.isNaN(t)) return String(value)
  const mins = Math.floor((Date.now() - t) / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  return fmtDate(value)
}

export function shortId(value: string | null | undefined, len = 14): string {
  if (!value) return '—'
  return value.length > len ? `${value.slice(0, len)}…` : value
}

// ── Building blocks ──────────────────────────────────────────────────────────

const CARD = 'bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas'
const LABEL = 'text-[10px] font-extrabold uppercase tracking-wider text-slate-500'

export function Panel({
  title,
  note,
  right,
  children,
  className = '',
}: {
  title: string
  note?: string
  right?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  return (
    <section className={`${CARD} p-5 ${className}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-extrabold text-[#101828] tracking-tight">{title}</h2>
          {note ? <p className="mt-1 text-[11px] text-slate-500 leading-relaxed max-w-3xl">{note}</p> : null}
        </div>
        {right ? <div className="flex items-center gap-2 shrink-0">{right}</div> : null}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  )
}

export function Metric({
  label,
  value,
  hint,
  tone = 'neutral',
}: {
  label: string
  value: string | number | null
  hint?: string
  tone?: 'neutral' | 'good' | 'warn' | 'bad'
}) {
  const display = value === null || value === undefined ? NO_DATA : String(value)
  const empty = display === NO_DATA
  const toneCls = {
    neutral: 'text-[#101828]',
    good: 'text-[#027A48]',
    warn: 'text-[#B54708]',
    bad: 'text-[#B42318]',
  }[tone]
  return (
    <div className={`${CARD} p-4`}>
      <div className={LABEL}>{label}</div>
      <div className={`mt-1.5 text-2xl font-black tracking-tight tabular-nums ${empty ? 'text-slate-300' : toneCls}`}>
        {display}
      </div>
      {hint ? <div className="mt-1 text-[11px] text-slate-400 leading-snug">{hint}</div> : null}
    </div>
  )
}

export function Pill({
  children,
  tone = 'neutral',
}: {
  children: React.ReactNode
  tone?: 'neutral' | 'good' | 'warn' | 'bad' | 'info'
}) {
  const cls = {
    neutral: 'bg-[#F5F8FC] text-slate-600 border-[#DDE6F0]',
    good: 'bg-[#ECFDF3] text-[#027A48] border-[#A6F4C5]',
    warn: 'bg-[#FFFAEB] text-[#B54708] border-[#FEDF89]',
    bad: 'bg-[#FEF3F2] text-[#B42318] border-[#FECDCA]',
    info: 'bg-[#EAF3FF] text-[#004085] border-[#D6E8FF]',
  }[tone]
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-[10px] font-extrabold uppercase tracking-wider ${cls}`}>
      {children}
    </span>
  )
}

/** A labelled count map rendered as ranked bars — the cheapest way to read a distribution. */
export function BarList({
  items,
  emptyLabel = 'NO DATA',
  max = 8,
}: {
  items: { label: string; value: number }[]
  emptyLabel?: string
  max?: number
}) {
  const rows = [...items]
    .filter(i => Number.isFinite(i.value))
    .sort((a, b) => b.value - a.value)
    .slice(0, max)
  if (!rows.length) {
    return <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300">{emptyLabel}</div>
  }
  const peak = Math.max(...rows.map(r => Math.abs(r.value)), 1)
  return (
    <div className="flex flex-col gap-2">
      {rows.map(row => (
        <div key={row.label} className="flex items-center gap-3">
          <div className="w-40 shrink-0 truncate text-xs font-bold text-slate-700" title={row.label}>{row.label}</div>
          <div className="flex-1 h-4 rounded bg-[#F1F5F9] overflow-hidden">
            <div
              className="h-full rounded bg-[#0B5D3B]/80"
              style={{ width: `${Math.max(2, (Math.abs(row.value) / peak) * 100)}%` }}
            />
          </div>
          <div className="w-16 shrink-0 text-right text-xs font-black tabular-nums text-slate-800">{fmtInt(row.value)}</div>
        </div>
      ))}
    </div>
  )
}

/** A labelled count map from the backend, ready for BarList. Empty maps stay
 *  empty (the bar list then prints NO DATA) instead of disappearing. */
export function mapItems(map: Record<string, number | null | undefined> | null | undefined): { label: string; value: number }[] {
  return Object.entries(map || {}).map(([label, value]) => ({ label: label || 'unknown', value: Number(value ?? 0) }))
}

export function Table({
  headers,
  rows,
  emptyLabel = 'NO DATA — nothing matched.',
}: {
  headers: string[]
  rows: (React.ReactNode[] | null | undefined)[]
  emptyLabel?: string
}) {
  const body = rows.filter((r): r is React.ReactNode[] => Array.isArray(r))
  if (!body.length) {
    return <EmptyNote label={emptyLabel} />
  }
  return (
    <div className="overflow-x-auto -mx-1">
      <table className="w-full text-left border-collapse min-w-[640px]">
        <thead>
          <tr className="border-b border-[#DDE6F0]">
            {headers.map(h => (
              <th key={h} className={`${LABEL} font-extrabold py-2 px-2 whitespace-nowrap`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((cells, idx) => (
            <tr key={idx} className="border-b border-slate-100 align-top hover:bg-slate-50">
              {headers.map((_, ci) => (
                <td key={ci} className="py-2 px-2 text-xs text-slate-700">
                  {cells[ci] ?? '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function EmptyNote({ label }: { label: string }) {
  return (
    <div className="p-4 rounded-lg border border-dashed border-[#DDE6F0] bg-[#F8FAFC] text-[11px] font-bold uppercase tracking-wider text-slate-400">
      {label}
    </div>
  )
}

/**
 * Backend honesty notes (absent tables / failed queries). Shown rather than
 * swallowed: an empty section must explain itself, not look like "zero".
 */
export function DataNotes({ notes }: { notes?: string[] }) {
  if (!notes || !notes.length) return null
  return (
    <div className="rounded-[12px] border border-[#FEDF89] bg-[#FFFAEB] p-4">
      <div className={`${LABEL} text-[#B54708]`}>Data notes</div>
      <ul className="mt-2 flex flex-col gap-1">
        {notes.map((n, i) => (
          <li key={i} className="text-[11px] text-[#8A5200] leading-relaxed">• {n}</li>
        ))}
      </ul>
    </div>
  )
}

export function KV({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 border-b border-slate-100 last:border-0">
      <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{label}</span>
      <span className="text-xs font-semibold text-slate-800 text-right break-words">{value}</span>
    </div>
  )
}

/** Segmented control over the read window. Local to each page — no URL state.
 *  A value of 0 means "no window applied" and is labelled ALL, never 0d. */
export function WindowPicker({
  value,
  onChange,
  options = [7, 30, 90, 365],
}: {
  value: number
  onChange: (days: number) => void
  options?: number[]
}) {
  return (
    <div className="inline-flex items-center gap-1 rounded-lg border border-[#DDE6F0] bg-white p-1">
      {options.map(d => (
        <button
          key={d}
          type="button"
          onClick={() => onChange(d)}
          className={`px-2.5 py-1 rounded text-[10px] font-extrabold uppercase tracking-wider transition ${
            value === d ? 'bg-[#0B5D3B] text-white' : 'text-slate-500 hover:bg-slate-100'
          }`}
        >
          {d === 0 ? 'all' : `${d}d`}
        </button>
      ))}
    </div>
  )
}

export function StateBlock({
  kind,
  title,
  body,
  action,
}: {
  kind: 'loading' | 'error' | 'denied' | 'info'
  title: string
  body: string
  action?: React.ReactNode
}) {
  const tone = {
    loading: 'border-[#D6E8FF] bg-[#EAF3FF] text-[#004085]',
    info: 'border-[#DDE6F0] bg-white text-slate-700',
    error: 'border-[#FECDCA] bg-[#FEF3F2] text-[#B42318]',
    denied: 'border-[#FEDF89] bg-[#FFFAEB] text-[#B54708]',
  }[kind]
  return (
    <div className={`rounded-[12px] border p-8 text-center ${tone}`}>
      <div className="text-sm font-extrabold tracking-tight">{title}</div>
      <p className="mt-2 mx-auto max-w-xl text-xs leading-relaxed">{body}</p>
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  )
}

/**
 * Loading / error strip every section screen shares. Renders nothing once data
 * is on screen, so a section never shows both numbers and a spinner.
 */
export function FetchStatus({
  busy,
  error,
  denied,
  hasData,
  section,
}: {
  busy: boolean
  error: string | null
  denied: boolean
  hasData: boolean
  section: string
}) {
  if (hasData) return null
  if (error) {
    return (
      <StateBlock
        kind={denied ? 'denied' : 'error'}
        title={denied ? `${section}: access denied` : `${section} could not be loaded`}
        body={denied
          ? 'The backend refused this section (HTTP 403) — this identity does not hold the PLATFORM_ADMIN role or the capability this route declares, or the role changed since the page loaded.'
          : `${error} No partial numbers are shown: an incomplete platform aggregate is more dangerous than none.`}
      />
    )
  }
  if (busy) {
    return <StateBlock kind="loading" title={`Reading ${section.toLowerCase()}…`} body="Aggregating across every workspace. Every read is recorded in the audit log." />
  }
  return null
}

// ── Platform actions (the console's write surface) ───────────────────────────

/**
 * A capability-gated button. `allowed=false` renders the reason instead of a
 * dead control: an administrator who cannot manage subscriptions should read that
 * from the screen, not discover it through a 403 after clicking.
 */
export function ActionButton({
  label,
  onClick,
  allowed = true,
  busy = false,
  tone = 'neutral',
  title,
}: {
  label: string
  onClick: () => void
  allowed?: boolean
  busy?: boolean
  tone?: 'neutral' | 'good' | 'warn' | 'bad'
  title?: string
}) {
  const tones = {
    neutral: 'border-[#DDE6F0] bg-white text-slate-700 hover:border-[#0B5D3B] hover:text-[#0B5D3B]',
    good: 'border-[#0B5D3B] bg-[#0B5D3B] text-white hover:bg-[#08482E]',
    warn: 'border-[#FEDF89] bg-[#FFFAEB] text-[#B54708] hover:border-[#B54708]',
    bad: 'border-[#FECDCA] bg-[#FEF3F2] text-[#B42318] hover:border-[#B42318]',
  }
  if (!allowed) {
    return (
      <span
        title={title || 'Your PLATFORM_ADMIN role does not include this capability'}
        className="px-3 py-1.5 rounded-lg border border-dashed border-[#DDE6F0] text-[10px] font-extrabold uppercase tracking-wider text-slate-400"
      >
        {label} · restricted
      </span>
    )
  }
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      title={title}
      className={`px-3 py-1.5 rounded-lg border text-[10px] font-extrabold uppercase tracking-wider transition disabled:opacity-50 ${tones[tone]}`}
    >
      {busy ? 'Working…' : label}
    </button>
  )
}

/**
 * The outcome of one platform mutation, stated in the backend's own words.
 * A failure keeps its error `code` visible — `LAST_ADMIN` and
 * `ENTERPRISE_ACTIVATION_REQUIRED` mean very different things to an operator,
 * and a generic "something went wrong" would hide that.
 */
export function ActionFeedback({
  ok,
  message,
  code,
  onDismiss,
}: {
  ok: boolean
  message: string
  code?: string | null
  onDismiss?: () => void
}) {
  return (
    <div className={`rounded-[12px] border p-3 text-xs leading-relaxed flex items-start justify-between gap-3 ${
      ok ? 'border-[#ABEFC6] bg-[#F0FDF4] text-[#08522B]' : 'border-[#FECDCA] bg-[#FEF3F2] text-[#B42318]'
    }`}
    >
      <div className="min-w-0">
        <span className="font-extrabold uppercase tracking-wider text-[10px]">{ok ? 'Recorded' : 'Refused'}</span>
        {code ? <span className="ml-2 font-mono font-bold text-[10px]">{code}</span> : null}
        <p className="mt-1 break-words">{message}</p>
      </div>
      {onDismiss ? (
        <button type="button" onClick={onDismiss} className="text-[10px] font-extrabold uppercase tracking-wider opacity-70 hover:opacity-100">
          Dismiss
        </button>
      ) : null}
    </div>
  )
}

/** A labelled form field for the mutation drawers — one visual grammar everywhere. */
export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">{label}</span>
      {children}
    </label>
  )
}

export const INPUT_CLASS = 'px-2.5 py-1.5 rounded-lg border border-[#DDE6F0] bg-white text-xs text-slate-800 focus:outline-none focus:border-[#0B5D3B]'
