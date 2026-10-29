'use client'

import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  createCollectionConnection,
  disconnectCollectionConnection,
  listCollectionConnections,
  syncCollectionConnection,
  type ChannelStatus,
  type CollectionBatch,
  type CollectionConnection,
  type CollectionGuidance,
  type CollectionSyncResult,
} from '../../lib/api'

/**
 * Collection Sources (Forms Integration V1).
 *
 * A channel is an ingress, not a pipeline. This card only ever ADDS evidence:
 * a Google Form or response sheet is authorised by its owner, synced, and each
 * ripe sync window becomes ONE ordinary evidence document on the existing
 * Assessment Context. Documents and forms coexist — nothing here replaces the
 * upload trigger above, and nothing here re-derives a trust score of its own.
 *
 * Honesty rules this component is built on:
 *  - An unenabled channel is reported as unavailable, never as an empty list.
 *  - Response volume is never presented as confidence (the caveat is verbatim
 *    from the backend contract, not written here).
 *  - Any number this screen cannot read from the API is shown as NO DATA.
 */

type CollectionSourcesProps = {
  assessmentId: string | null
  /** Called after a batch is attached so the workspace re-reads its context. */
  onEvidenceChanged?: () => void | Promise<void>
  canManage?: boolean
}

const STATUS_TONE: Record<string, string> = {
  active: 'bg-[#ECFDF3] text-[#027A48] border-[#A6F4C5]',
  pending_auth: 'bg-[#FFFAEB] text-[#B54708] border-[#FEDF89]',
  error: 'bg-[#FEF3F2] text-[#B42318] border-[#FECDCA]',
  revoked: 'bg-slate-100 text-slate-600 border-slate-200',
}

function metric(value: unknown, fallback = 'NO DATA'): string {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

function when(iso: string): string {
  if (!iso) return 'never'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Plain-language result of one sync, taken from the backend's own state. */
function describeSync(result: CollectionSyncResult): { tone: string; text: string } {
  if (result.materialised) {
    // The backend message already carries the count, the minimum shortfall and
    // the contract's honesty caveat — quoting it keeps this screen from
    // restating evidence strength in its own words.
    return {
      tone: 'border-[#A6F4C5] bg-[#ECFDF3] text-[#027A48]',
      text:
        result.message ||
        `Attached ${metric(result.responseCount)} response(s) as one evidence batch ` +
          `(${metric(result.evidenceStatus, 'status not reported')}, median response trust ` +
          `${metric(result.medianResponseTrust, 'not scored')}/100 — self-reported, capped below VERIFIED).`,
    }
  }
  if (result.status === 'awaiting_primary_documents') {
    return { tone: 'border-[#FEDF89] bg-[#FFFAEB] text-[#B54708]', text: result.message || 'Upload a primary document first.' }
  }
  if (result.status === 'pending_below_minimum') {
    return { tone: 'border-[#FEDF89] bg-[#FFFAEB] text-[#B54708]', text: result.message || 'Not enough responses yet.' }
  }
  if (result.status === 'no_new_responses') {
    return {
      tone: 'border-[#DDE6F0] bg-[#F5F8FC] text-slate-600',
      text: `No new responses (${result.fetched} fetched, ${result.newResponses} new). Collected responses are retained for the next batch.`,
    }
  }
  return { tone: 'border-[#DDE6F0] bg-white text-slate-700', text: result.message || 'Sync completed.' }
}

export default function CollectionSources({ assessmentId, onEvidenceChanged, canManage = true }: CollectionSourcesProps) {
  const [connections, setConnections] = useState<CollectionConnection[]>([])
  const [batches, setBatches] = useState<CollectionBatch[]>([])
  const [status, setStatus] = useState<ChannelStatus | null>(null)
  const [guidance, setGuidance] = useState<CollectionGuidance | null>(null)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [banner, setBanner] = useState<{ tone: string; text: string } | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [formUrl, setFormUrl] = useState('')
  const [sheetUrl, setSheetUrl] = useState('')
  const [purpose, setPurpose] = useState<'evidence' | 'follow_up'>('evidence')
  const [note, setNote] = useState('')

  const load = useCallback(async () => {
    if (!assessmentId) return
    setLoading(true)
    setError(null)
    try {
      const payload = await listCollectionConnections(assessmentId)
      setConnections(payload.connections)
      setBatches(payload.batches)
      setStatus(payload.status)
      setGuidance(payload.guidance)
    } catch (err: any) {
      setError(err?.message || String(err))
    } finally {
      setLoading(false)
    }
  }, [assessmentId])

  useEffect(() => {
    void load()
  }, [load])

  // The Google consent round-trip lands here as a top-level redirect:
  //   /evidence?collection=connected|failed&…
  // The message comes from the backend verbatim; the query params are then
  // stripped so a refresh cannot replay a completed authorisation.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const outcome = params.get('collection')
    if (!outcome) return
    if (outcome === 'connected') {
      setBanner({
        tone: 'border-[#A6F4C5] bg-[#ECFDF3] text-[#027A48]',
        text: `Google authorised this collection source (${metric(params.get('questions'), '0')} questions discovered). Sync it to import responses.`,
      })
    } else {
      setBanner({
        tone: 'border-[#FECDCA] bg-[#FEF3F2] text-[#B42318]',
        text: params.get('message') || `Google returned an authorisation error (${metric(params.get('code'), 'no code')}).`,
      })
    }
    window.history.replaceState({}, '', window.location.pathname)
    void load()
  }, [load])

  async function handleConnect() {
    if (!assessmentId) return
    setBusy('connect')
    setError(null)
    setNotice(null)
    try {
      const created = await createCollectionConnection({
        assessmentId,
        formUrl: formUrl.trim(),
        sheetUrl: sheetUrl.trim(),
        purpose,
        note: note.trim(),
      })
      // Consent is a full browser redirect: Google must be able to send the
      // code back to the backend, which then returns the browser here.
      window.location.href = created.authorizeUrl
    } catch (err: any) {
      setError(err?.message || String(err))
      setBusy(null)
    }
  }

  async function handleSync(conn: CollectionConnection) {
    if (!assessmentId) return
    setBusy(conn.id)
    setError(null)
    setNotice(null)
    try {
      const result = await syncCollectionConnection(conn.id, assessmentId)
      const described = describeSync(result)
      setBanner(described)
      if (result.materialised) {
        // The digest is what the signals layer actually read — showing it here
        // proves the batch entered the pipeline as evidence, not as a claim.
        setNotice(result.digestPreview ? `What the pipeline received:\n${result.digestPreview}` : null)
        await onEvidenceChanged?.()
      }
      await load()
    } catch (err: any) {
      setError(err?.message || String(err))
    } finally {
      setBusy(null)
    }
  }

  async function handleDisconnect(conn: CollectionConnection) {
    setBusy(conn.id)
    setError(null)
    try {
      const result = await disconnectCollectionConnection(conn.id)
      setNotice(result.note || 'Disconnected. Existing evidence batches remain.')
      await load()
    } catch (err: any) {
      setError(err?.message || String(err))
    } finally {
      setBusy(null)
    }
  }

  const batchCountByConnection = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const b of batches) counts[b.connectionId] = (counts[b.connectionId] || 0) + 1
    return counts
  }, [batches])

  const channelLive = Boolean(status?.enabled && status?.configured)

  if (!assessmentId) return null

  // Channel switched off on this deployment: one quiet line, not a broken CTA.
  if (!loading && status && !status.enabled) {
    return (
      <section className="rounded-[12px] border border-[#DDE6F0] bg-white p-4 text-xs shadow-saas">
        <details>
          <summary className="cursor-pointer font-extrabold uppercase tracking-wider text-slate-500">
            Collection Sources (Google Forms) — not enabled on this deployment
          </summary>
          <p className="mt-2 text-slate-600 leading-relaxed">
            {status.message || 'Set KULIMA_FORMS_ENABLED and the Google OAuth secrets to turn this channel on.'}
            {' '}Document upload is unaffected: it remains the primary evidence route.
          </p>
        </details>
      </section>
    )
  }

  return (
    <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas space-y-4">
      <div className="flex items-start justify-between gap-3 pb-3 border-b border-[#DDE6F0]">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-widest bg-[#F4EBFF] text-[#6941C6] border-[#E9D7FE] border">
              Source C
            </span>
            <h2 className="text-base font-extrabold text-slate-900">Collection Sources (Google Forms / Sheets)</h2>
          </div>
          <p className="text-xs text-slate-500 mt-1 max-w-3xl leading-relaxed">
            Live responses from the people an assessment is about. Each sync becomes one evidence document in
            this same Assessment Context — responses are never silently merged with uploaded documents, and
            uploads are never replaced.
          </p>
          {guidance ? (
            <p className="text-[11px] text-slate-500 mt-1.5">
              <strong className="font-bold text-slate-700">{guidance.entityLabel}</strong> — {guidance.purpose}
            </p>
          ) : null}
        </div>
        <span className={`text-xs font-bold px-2.5 py-1 rounded-lg border shrink-0 ${
          channelLive ? 'text-[#027A48] bg-[#ECFDF3] border-[#A6F4C5]' : 'text-[#B54708] bg-[#FFFAEB] border-[#FEDF89]'
        }`}>
          {connections.length} Source{connections.length === 1 ? '' : 's'}
        </span>
      </div>

      {!channelLive && status ? (
        <div className="p-3 rounded-lg border border-[#FEDF89] bg-[#FFFAEB] text-xs text-[#B54708] leading-relaxed">
          <strong className="font-extrabold">Channel not configured on this deployment.</strong>{' '}
          {status.message || `Missing: ${status.missing.join(', ') || 'Google OAuth secrets'}.`}
          {' '}Existing evidence and documents are unaffected.
        </div>
      ) : null}

      {banner ? (
        <div className={`p-3 rounded-lg border text-xs font-semibold leading-relaxed ${banner.tone}`}>{banner.text}</div>
      ) : null}
      {notice ? (
        <div className="p-3 rounded-lg border border-[#DDE6F0] bg-[#F5F8FC] text-xs text-slate-600 leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto">{notice}</div>
      ) : null}
      {error ? (
        <div className="p-3 rounded-lg border border-[#FECDCA] bg-[#FEF3F2] text-xs font-semibold text-[#B42318]">{error}</div>
      ) : null}

      {/* Connected instruments */}
      {connections.length === 0 ? (
        <div className="p-6 text-center bg-[#F5F8FC] rounded-[10px] border border-dashed border-[#DDE6F0]">
          <div className="text-slate-400 text-sm font-semibold">NO DATA: no collection source connected yet.</div>
          <p className="text-xs text-slate-500 mt-1 max-w-xl mx-auto leading-relaxed">
            Connect the form your beneficiaries or customers actually answered. The form owner authorises read-only
            access to responses; Kulima never writes to Google.
            {guidance ? ` Minimum for a directional read on a ${guidance.entityLabel}: ${guidance.minimumResponses} responses.` : ''}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {connections.map(conn => (
            <div key={conn.id} className="p-4 bg-[#F5F8FC] rounded-[10px] border border-[#DDE6F0] space-y-3">
              <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-slate-900 text-white">
                      {conn.kind === 'google_sheet' ? 'SHEET' : 'FORM'}
                    </span>
                    <span className="text-sm font-extrabold text-slate-900 truncate">
                      {conn.title || 'Instrument title not discovered yet'}
                    </span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider border ${STATUS_TONE[conn.status] || STATUS_TONE.revoked}`}>
                      {conn.status.replace(/_/g, ' ')}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-[#EAF3FF] text-[#004085] border border-[#D6E8FF]">
                      {conn.purpose === 'follow_up' ? 'Follow-up / outcomes' : 'Evidence'}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1.5 text-[11px] text-slate-500">
                    <span>Evidence class: {conn.evidenceClass}</span>
                    <span>Schema: {conn.questionCount} question(s) · {conn.schemaHash ? conn.schemaHash.slice(0, 8) : 'not discovered'}</span>
                    <span>Responses: {conn.totalResponses} total · {conn.pendingResponses} awaiting batch</span>
                    <span>Batches: {batchCountByConnection[conn.id] ?? conn.batchCount}</span>
                    <span>Last sync: {when(conn.lastSyncedAt)}</span>
                  </div>
                  {conn.lastError ? (
                    <div className="mt-1.5 text-[11px] font-semibold text-[#B42318]">Last error: {conn.lastError}</div>
                  ) : null}
                </div>

                {canManage ? (
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => void handleSync(conn)}
                      disabled={busy === conn.id || conn.status !== 'active'}
                      title={conn.status !== 'active' ? 'This source needs authorisation before it can be synced.' : 'Import new responses'}
                      className="px-3 py-2 rounded-lg bg-[#0B5D3B] text-white text-[11px] font-extrabold uppercase tracking-wider hover:bg-[#08482E] transition disabled:bg-slate-300 disabled:cursor-not-allowed"
                    >
                      {busy === conn.id ? 'Syncing…' : 'Sync responses'}
                    </button>
                    <button
                      onClick={() => void handleDisconnect(conn)}
                      disabled={busy === conn.id}
                      title="Revoke Google read access. Evidence already attached stays in the assessment."
                      className="px-3 py-2 rounded-lg border border-[#DDE6F0] text-slate-600 text-[11px] font-extrabold uppercase tracking-wider hover:border-[#FECDCA] hover:text-[#B42318] transition disabled:opacity-50"
                    >
                      Disconnect
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add a source */}
      {canManage && channelLive ? (
        showForm ? (
          <div className="p-4 border border-[#DDE6F0] rounded-[10px] bg-white space-y-3">
            <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">Connect a collection source</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label className="block text-xs">
                <span className="font-bold text-slate-700">Google Form link</span>
                <input
                  value={formUrl}
                  onChange={e => setFormUrl(e.target.value)}
                  placeholder="https://docs.google.com/forms/d/e/…/viewform"
                  className="mt-1 w-full p-2.5 border border-[#DDE6F0] rounded-lg text-sm focus:outline-none focus:border-[#0B5D3B]"
                />
              </label>
              <label className="block text-xs">
                <span className="font-bold text-slate-700">…or response sheet link</span>
                <input
                  value={sheetUrl}
                  onChange={e => setSheetUrl(e.target.value)}
                  placeholder="https://docs.google.com/spreadsheets/d/…/edit"
                  className="mt-1 w-full p-2.5 border border-[#DDE6F0] rounded-lg text-sm focus:outline-none focus:border-[#0B5D3B]"
                />
              </label>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label className="block text-xs">
                <span className="font-bold text-slate-700">Purpose</span>
                <select
                  value={purpose}
                  onChange={e => setPurpose(e.target.value as 'evidence' | 'follow_up')}
                  className="mt-1 w-full p-2.5 border border-[#DDE6F0] rounded-lg text-sm bg-white focus:outline-none focus:border-[#0B5D3B]"
                >
                  <option value="evidence">Evidence — feeds the current assessment</option>
                  <option value="follow_up">Follow-up — outcome tracking, no re-decision</option>
                </select>
              </label>
              <label className="block text-xs">
                <span className="font-bold text-slate-700">Note for the audit trail (optional)</span>
                <input
                  value={note}
                  onChange={e => setNote(e.target.value)}
                  maxLength={400}
                  placeholder="Beneficiary feedback, Mzimba district, round 2"
                  className="mt-1 w-full p-2.5 border border-[#DDE6F0] rounded-lg text-sm focus:outline-none focus:border-[#0B5D3B]"
                />
              </label>
            </div>
            {guidance?.requiredBlocks?.length ? (
              <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0] text-[11px] text-slate-600 leading-relaxed">
                <div className="font-extrabold uppercase tracking-wider text-slate-500 mb-1">
                  A {guidance.entityLabel} form should cover
                </div>
                {guidance.requiredBlocks.map(block => <div key={block}>· {block}</div>)}
                <div className="mt-1.5 font-semibold text-slate-700">{guidance.honestyCaveat}</div>
              </div>
            ) : null}
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setShowForm(false)}
                className="px-3 py-2 rounded-lg border border-[#DDE6F0] text-slate-600 text-[11px] font-extrabold uppercase tracking-wider"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleConnect()}
                disabled={busy === 'connect' || (!formUrl.trim() && !sheetUrl.trim())}
                className="px-4 py-2 rounded-lg bg-[#0B5D3B] text-white text-[11px] font-extrabold uppercase tracking-wider hover:bg-[#08482E] transition disabled:bg-slate-300 disabled:cursor-not-allowed"
              >
                {busy === 'connect' ? 'Preparing consent…' : 'Authorise with Google →'}
              </button>
            </div>
            <p className="text-[10px] text-slate-400 leading-relaxed">
              Read-only scopes only (Form responses / Spreadsheet). The owner&apos;s Google account is the one that
              authorises; credentials are sealed with this deployment&apos;s encryption key and never leave it.
            </p>
          </div>
        ) : (
          <button
            onClick={() => setShowForm(true)}
            className="w-full px-4 py-3 rounded-lg border border-dashed border-[#DDE6F0] text-[11px] font-extrabold uppercase tracking-wider text-slate-600 hover:border-[#0B5D3B] hover:text-[#0B5D3B] transition"
          >
            + Connect Google Form or response sheet
          </button>
        )
      ) : null}

      {/* Batches: one row per attached response window */}
      {batches.length > 0 ? (
        <div>
          <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-2">
            Imported batches ({batches.length})
          </div>
          <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
            {batches.map(batch => (
              <div key={batch.id} className="border border-[#DDE6F0] rounded-lg p-3 text-xs bg-white">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-bold text-slate-900 truncate">{batch.filename || 'Collection batch'}</div>
                    <div className="text-[10px] text-slate-500 mt-0.5 font-mono">
                      {batch.responseCount} response(s) · window {when(batch.windowStart)} → {when(batch.windowEnd)}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      Evidence document: {batch.documentId ? batch.documentId.slice(0, 8) : 'not recorded'} · Trust:{' '}
                      {metric(batch.trustScore, 'not scored')} · Status:{' '}
                      {String(batch.evidenceStatus || 'not audited').replace(/_/g, ' ')}
                    </div>
                  </div>
                  <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-[#F4EBFF] text-[#6941C6] border border-[#E9D7FE] shrink-0">
                    SELF-REPORTED
                  </span>
                </div>
              </div>
            ))}
          </div>
          <p className="mt-2 text-[10px] text-slate-400 leading-relaxed">
            Repeated syncs of one instrument count as one source in the Trust Engine. Response volume never raises a
            batch above CORROBORATED authority.
          </p>
        </div>
      ) : null}
    </section>
  )
}
