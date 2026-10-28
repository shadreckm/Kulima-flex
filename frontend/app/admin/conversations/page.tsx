'use client'

// Platform Administration Console — Conversations.
//
// Analyst conversations across every workspace, measured rather than read: this
// panel returns titles and message counts, never message bodies. An administrator
// can see that a workspace is using Ask IC, how much, and whether it is stuck to an
// assessment — the questions a customer asked their own analyst are not platform
// data. That boundary is the backend's (admin_ops.conversations_panel selects no
// message column), and the screen states it so nobody assumes the API holds more.

import { useState } from 'react'
import AdminConsoleShell from '../../../components/AdminConsole/AdminConsoleShell'
import {
  BarList,
  DataNotes,
  FetchStatus,
  Metric,
  NO_DATA,
  Panel,
  Pill,
  Table,
  WindowPicker,
  fmtDateTime,
  fmtInt,
  relTime,
  shortId,
} from '../../../components/AdminConsole/adminUi'
import { useAdminFetch } from '../../../hooks/useAdminFetch'
import { getAdminConversations } from '../../../lib/admin'

const LIMITS = [50, 100, 250, 500]

export default function AdminConversationsPage() {
  const [windowDays, setWindowDays] = useState(30)
  const [limit, setLimit] = useState(100)
  const [orgInput, setOrgInput] = useState('')
  const [orgId, setOrgId] = useState('')

  const { data, busy, error, denied, reload } = useAdminFetch(
    () => getAdminConversations({ orgId: orgId || undefined, limit, windowDays }),
    [orgId, limit, windowDays],
  )

  return (
    <AdminConsoleShell
      section="conversations"
      title="Conversations"
      description="Analyst usage across the platform — volumes and linkage only. Message contents stay inside the customer's workspace and are not returned by this API."
      toolbar={(
        <div className="flex items-center gap-2 flex-wrap">
          <form
            onSubmit={e => { e.preventDefault(); setOrgId(orgInput.trim()) }}
            className="flex items-center gap-1"
          >
            <input
              value={orgInput}
              onChange={e => setOrgInput(e.target.value)}
              placeholder="organization id"
              maxLength={120}
              className="w-44 px-2.5 py-1.5 rounded-lg border border-[#DDE6F0] bg-white text-xs text-slate-800 focus:outline-none focus:border-[#0B5D3B]"
            />
            <button
              type="submit"
              className="px-3 py-1.5 rounded-lg bg-[#0B5D3B] hover:bg-[#08482E] text-white text-[10px] font-extrabold uppercase tracking-wider transition"
            >
              Filter
            </button>
            {orgId ? (
              <button
                type="button"
                onClick={() => { setOrgInput(''); setOrgId('') }}
                className="px-2 py-1.5 rounded-lg border border-[#DDE6F0] text-[10px] font-extrabold uppercase tracking-wider text-slate-500 hover:border-[#0B5D3B] transition"
              >
                Clear
              </button>
            ) : null}
          </form>
          <select value={limit} onChange={e => setLimit(Number(e.target.value))} className="px-2 py-1.5 rounded-lg border border-[#DDE6F0] bg-white text-[11px] font-bold text-slate-700 focus:outline-none focus:border-[#0B5D3B]" aria-label="Rows">
            {LIMITS.map(n => <option key={n} value={n}>top {n}</option>)}
          </select>
          <WindowPicker value={windowDays} onChange={setWindowDays} />
        </div>
      )}
      onReload={reload}
      busy={busy}
    >
      <FetchStatus busy={busy} error={error} denied={denied} hasData={!!data} section="Conversations" />

      {data ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric label="Conversations" value={fmtInt(data.totals.conversations)} hint={`${fmtInt(data.totals.createdInWindow)} created in ${data.windowDays}d · ${fmtInt(data.totals.listed)} listed here`} />
            <Metric label="Messages" value={fmtInt(data.totals.messages)} hint="questions and answers together, platform-wide" />
            <Metric label="Questions in window" value={fmtInt(data.totals.questionsInWindow)} hint="messages authored by a user role inside the selected window" />
            <Metric
              label="Not linked to an assessment"
              value={fmtInt(data.totals.withoutAssessment)}
              hint="a conversation with no assessment id — standalone AI Analyst use"
              tone={data.totals.withoutAssessment ? 'warn' : 'good'}
            />
          </div>

          <Panel
            title="Conversations"
            note="Newest activity first. Titles are the customer's own labels. Message bodies are deliberately absent from this response."
          >
            <Table
              headers={['Conversation', 'Workspace', 'User', 'Messages', 'Questions', 'Last message', 'Updated', '']}
              rows={data.conversations.map(c => [
                (
                  <div>
                    <div className="text-[11px] font-bold text-slate-800">{c.title || <span className="italic text-slate-400">untitled</span>}</div>
                    <div className="text-[10px] font-mono text-slate-400">{shortId(c.conversationId, 24)}</div>
                    <div className="text-[10px] font-mono text-slate-400">assessment {shortId(c.assessmentId, 16)}</div>
                  </div>
                ),
                (
                  <div>
                    <div className="text-[11px] font-bold text-slate-700">{c.orgName || shortId(c.orgId, 14)}</div>
                    <div className="text-[10px] font-mono text-slate-400">{shortId(c.orgId, 20)}</div>
                  </div>
                ),
                <span className="text-[10px] font-mono text-slate-500">{shortId(c.userId, 18)}</span>,
                fmtInt(c.messages),
                fmtInt(c.questions),
                <span title={fmtDateTime(c.lastMessageAt)}>{c.lastMessageAt ? relTime(c.lastMessageAt) : 'never'}</span>,
                <span title={fmtDateTime(c.updatedAt)}>{c.updatedAt ? relTime(c.updatedAt) : NO_DATA}</span>,
                c.isDefault ? <Pill tone="info">default</Pill> : null,
              ])}
            />
          </Panel>

          <Panel
            title="Busiest conversations"
            note="Top five by message count among the rows listed here — a proxy for where the analyst is doing real work, not a ranking of quality."
          >
            <BarList
              items={data.busiest.map(b => ({ label: `${b.orgName ? `${b.orgName} — ` : ''}${b.title || shortId(b.conversationId, 12)}`, value: b.messages }))}
              emptyLabel="NO DATA — no conversations in this view."
            />
          </Panel>

          <DataNotes notes={data.dataNotes} />
        </>
      ) : null}
    </AdminConsoleShell>
  )
}
