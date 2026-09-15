'use client'

import React, { useEffect, useState, Suspense } from 'react'
import { useSession, signIn } from 'next-auth/react'
import { useSearchParams } from 'next/navigation'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import {
  listStoredRuns,
  submitRunFeedback,
  getRunFeedback,
  listAllFeedback,
  type StoredRunRecord,
  type FeedbackRecord,
} from '../../lib/api'
import { isDemoRunRecord, loadCurrentRun, resolveStoredRunId } from '../../lib/current-run'
import TrustGauge from '../../components/TrustGauge/TrustGauge'
import Link from 'next/link'

type Tab = 'submit' | 'review' | 'dashboard'

function StarDisplay({ rating }: { rating: number }) {
  return (
    <span className="inline-flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map(n => (
        <svg key={n} className={`w-3.5 h-3.5 ${n <= rating ? 'text-amber-400' : 'text-slate-200'}`} fill="currentColor" viewBox="0 0 20 20">
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      ))}
      <span className="ml-1 text-[11px] font-bold text-slate-700">{rating}/5</span>
    </span>
  )
}

function RatingBar({ value, total }: { value: number; total: number }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-[#F5F8FC] rounded-full border border-[#DDE6F0] overflow-hidden">
        <div className="h-full bg-[#0B5D3B] rounded-full transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[11px] font-bold text-slate-600 w-8 text-right">{value}</span>
    </div>
  )
}

function FeedbackPageInner() {
  const { status: authStatus } = useSession()
  const searchParams = useSearchParams()
  const [activeTab, setActiveTab] = useState<Tab>('submit')

  // Submit tab state
  const [runs, setRuns] = useState<StoredRunRecord[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string>('')
  const [userName, setUserName] = useState('')
  const [rating, setRating] = useState(4)
  const [comment, setComment] = useState('')
  const [submitMessage, setSubmitMessage] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Review tab state
  const [runFeedback, setRunFeedback] = useState<FeedbackRecord[]>([])
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewError, setReviewError] = useState<string | null>(null)

  // Dashboard tab state
  const [allFeedback, setAllFeedback] = useState<FeedbackRecord[]>([])
  const [dashLoading, setDashLoading] = useState(false)
  const [dashError, setDashError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function loadRuns() {
      const res = await listStoredRuns(50, true)
      if (cancelled) return
      const userRuns = res.runs.filter(run => !isDemoRunRecord(run))
      setRuns(userRuns)
      const paramRun = searchParams.get('run')
      const stored = loadCurrentRun()
      const nextSelected = resolveStoredRunId(userRuns, paramRun || stored?.runId || '', stored)
      setSelectedRunId(nextSelected)
    }
    if (authStatus === 'authenticated') {
      loadRuns().catch(err => setSubmitError(String(err)))
    }
    return () => { cancelled = true }
  }, [authStatus, searchParams])

  // Load review data when switching to Review tab or when selectedRunId changes
  useEffect(() => {
    if (activeTab !== 'review' || !selectedRunId || authStatus !== 'authenticated') return
    let cancelled = false
    setReviewLoading(true)
    setReviewError(null)
    getRunFeedback(selectedRunId)
      .then(res => { if (!cancelled) setRunFeedback(res.feedback) })
      .catch(err => { if (!cancelled) setReviewError(String(err)) })
      .finally(() => { if (!cancelled) setReviewLoading(false) })
    return () => { cancelled = true }
  }, [activeTab, selectedRunId, authStatus])

  // Load dashboard data when switching to Dashboard tab
  useEffect(() => {
    if (activeTab !== 'dashboard' || authStatus !== 'authenticated') return
    let cancelled = false
    setDashLoading(true)
    setDashError(null)
    listAllFeedback(200)
      .then(res => { if (!cancelled) setAllFeedback(res.feedback) })
      .catch(err => { if (!cancelled) setDashError(String(err)) })
      .finally(() => { if (!cancelled) setDashLoading(false) })
    return () => { cancelled = true }
  }, [activeTab, authStatus])

  if (authStatus === 'loading') {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">
        Checking session…
      </div>
    )
  }

  if (authStatus === 'unauthenticated') {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex flex-col items-center justify-center gap-4">
        <div className="text-lg font-bold text-slate-900">Sign in to use Kulima FLEX</div>
        <button
          onClick={() => signIn()}
          className="px-5 py-2.5 rounded-lg bg-[#0B5D3B] text-white font-bold hover:bg-[#08482E] transition shadow-sm"
        >
          Sign in
        </button>
      </div>
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setSubmitError(null)
    setSubmitMessage(null)
    try {
      await submitRunFeedback(selectedRunId, { userName, rating, comment })
      setSubmitMessage('Feedback recorded successfully.')
      setComment('')
      setRating(4)
      // Refresh review and dashboard data silently
      if (selectedRunId) {
        getRunFeedback(selectedRunId).then(res => setRunFeedback(res.feedback)).catch(() => {})
      }
      listAllFeedback(200).then(res => setAllFeedback(res.feedback)).catch(() => {})
    } catch (err) {
      setSubmitError(String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const selectedRun = runs.find(run => String(run.runId) === String(selectedRunId))

  // Dashboard aggregates
  const totalFeedback = allFeedback.length
  const avgRating = totalFeedback > 0 ? (allFeedback.reduce((s, f) => s + f.rating, 0) / totalFeedback) : 0
  const ratingCounts = [1, 2, 3, 4, 5].map(r => allFeedback.filter(f => f.rating === r).length)
  const topRated = [...allFeedback].sort((a, b) => b.rating - a.rating).slice(0, 5)

  const TABS: Array<{ id: Tab; label: string; count?: number }> = [
    { id: 'submit', label: 'Submit Feedback' },
    { id: 'review', label: 'Review Evaluation', count: runFeedback.length || undefined },
    { id: 'dashboard', label: 'Feedback Dashboard', count: totalFeedback || undefined },
  ]

  return (
    <PilotWorkspaceShell
      workspace="Feedback"
      title="Evaluation Feedback"
      description="Submit reviewer feedback, review per-evaluation history, and monitor the feedback dashboard."
      runId={selectedRunId || null}
      status={selectedRun?.archivedAt ? 'archived' : 'active'}
      startupName={selectedRun?.startupName}
      recommendation={selectedRun?.recommendation}
      trustScore={selectedRun?.trustScore}
    >
      {/* Tab Bar */}
      <div className="flex gap-1 p-1 bg-[#F5F8FC] rounded-[10px] border border-[#DDE6F0]">
        {TABS.map(tab => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 flex-1 justify-center px-4 py-2 rounded-lg text-xs font-extrabold uppercase tracking-wider transition ${
              activeTab === tab.id
                ? 'bg-white text-[#0B5D3B] shadow-sm border border-[#DDE6F0]'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {tab.label}
            {tab.count !== undefined && tab.count > 0 ? (
              <span className="px-1.5 py-0.5 rounded-full bg-[#0B5D3B] text-white text-[10px] font-black">
                {tab.count}
              </span>
            ) : null}
          </button>
        ))}
      </div>

      {/* ── TAB: SUBMIT ── */}
      {activeTab === 'submit' && (
        <>
          {submitError && (
            <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">
              {submitError}
            </div>
          )}
          {submitMessage && (
            <div className="p-4 bg-emerald-50 text-emerald-800 rounded-[12px] border border-emerald-200 text-sm font-bold flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#12B76A]" />
              <span>{submitMessage}</span>
            </div>
          )}

          {runs.length === 0 ? (
            <div className="p-8 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas text-center">
              <div className="text-sm font-bold text-slate-700">No documents uploaded yet</div>
              <div className="text-xs text-slate-500 mt-1">Upload your first pitch deck, NGO report, survey, business plan, or program report.</div>
              <Link href="/runs" className="mt-4 inline-block px-4 py-2 rounded-lg bg-[#0B5D3B] text-white text-xs font-bold hover:bg-[#08482E] transition">
                Go to Runs
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <form onSubmit={handleSubmit} className="p-6 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas space-y-5">
                  <div className="pb-3 border-b border-[#DDE6F0]">
                    <h2 className="text-base font-extrabold text-slate-900">Submit Evaluation Feedback</h2>
                    <p className="text-xs text-slate-500 mt-0.5">Captures decision committee input for institutional review tracking.</p>
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-700">Select Evaluation Target</label>
                    <select
                      className="mt-1.5 w-full p-2.5 border border-[#DDE6F0] rounded-lg bg-[#F5F8FC] text-sm text-slate-900 font-medium focus:outline-none focus:border-[#0B5D3B]"
                      value={selectedRunId}
                      onChange={(e) => setSelectedRunId(e.target.value)}
                    >
                      <option value="">Select Evaluation Target…</option>
                      {runs.map(run => (
                        <option key={run.runId} value={run.runId}>
                          #{run.runId} · {run.startupName} · {run.founderName} (Trust: {run.trustScore ?? '—'})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-700">Reviewer Name / Title</label>
                    <input
                      value={userName}
                      onChange={(e) => setUserName(e.target.value)}
                      className="mt-1.5 w-full p-2.5 border border-[#DDE6F0] rounded-lg bg-[#F5F8FC] text-sm text-slate-900 focus:outline-none focus:border-[#0B5D3B]"
                      placeholder="e.g. Investment Committee Member / Program Officer"
                    />
                  </div>

                  <div>
                    <div className="flex items-center justify-between">
                      <label className="block text-xs font-bold uppercase tracking-wider text-slate-700">Evaluation Confidence Rating</label>
                      <span className="px-2 py-0.5 rounded bg-[#EAF3FF] text-[#004085] text-xs font-extrabold border border-[#D6E8FF]">
                        {rating} / 5 Stars
                      </span>
                    </div>
                    <input
                      type="range"
                      min={1}
                      max={5}
                      value={rating}
                      onChange={(e) => setRating(Number(e.target.value))}
                      className="mt-2 w-full accent-[#0B5D3B] cursor-pointer"
                    />
                    <div className="flex justify-between text-[10px] text-slate-400 font-medium mt-0.5">
                      <span>Low</span><span>High</span>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-700">Reviewer Comments & Rationale</label>
                    <textarea
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                      className="mt-1.5 w-full p-3 border border-[#DDE6F0] rounded-lg bg-[#F5F8FC] text-sm text-slate-900 min-h-32 focus:outline-none focus:border-[#0B5D3B]"
                      placeholder="Assess evidence integrity, confidence score accuracy, risk signals, or thesis alignment..."
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={submitting || !selectedRunId}
                    className="w-full sm:w-auto px-6 py-2.5 rounded-lg bg-[#0B5D3B] text-white text-xs font-extrabold uppercase tracking-wider hover:bg-[#08482E] transition disabled:opacity-50 shadow-sm"
                  >
                    {submitting ? 'Recording Feedback…' : 'Submit Review Feedback'}
                  </button>
                </form>
              </div>

              <div className="space-y-6">
                <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
                  <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-700 mb-3 pb-2 border-b border-[#DDE6F0]">
                    Trust Assessment
                  </h3>
                  {selectedRun ? (
                    <div className="space-y-4">
                      <TrustGauge score={selectedRun.trustScore} size="lg" showLabel={true} />
                      <div className="pt-3 border-t border-[#DDE6F0] text-xs text-slate-600 space-y-1.5">
                        <div className="flex justify-between">
                          <span className="text-slate-400">Entity:</span>
                          <span className="font-bold text-slate-900">{selectedRun.startupName}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Recommendation:</span>
                          <span className="font-bold text-slate-900">{selectedRun.recommendation || '—'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Integrity Grade:</span>
                          <span className="font-bold text-slate-900">{selectedRun.integrityGrade || '—'}</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500 italic py-4">
                      Select an evaluation target to view trust score and verification telemetry.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* ── TAB: REVIEW ── */}
      {activeTab === 'review' && (
        <div className="space-y-4">
          {/* Run selector for review */}
          <div className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas flex items-center gap-4">
            <div className="flex-1">
              <label className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1">
                Select Evaluation to Review Feedback
              </label>
              <select
                className="w-full p-2.5 border border-[#DDE6F0] rounded-lg bg-[#F5F8FC] text-sm text-slate-900 font-medium focus:outline-none focus:border-[#0B5D3B]"
                value={selectedRunId}
                onChange={(e) => setSelectedRunId(e.target.value)}
              >
                <option value="">Select Evaluation…</option>
                {runs.map(run => (
                  <option key={run.runId} value={run.runId}>
                    #{run.runId} · {run.startupName} (Trust: {run.trustScore ?? '—'})
                  </option>
                ))}
              </select>
            </div>
            {selectedRun && (
              <div className="shrink-0 text-right text-xs">
                <div className="font-extrabold text-slate-900">{selectedRun.startupName}</div>
                <div className="text-slate-500">{selectedRun.recommendation || '—'} · Grade {selectedRun.integrityGrade || '—'}</div>
              </div>
            )}
          </div>

          {reviewError && (
            <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">{reviewError}</div>
          )}

          {reviewLoading ? (
            <div className="p-8 text-center text-sm text-slate-400">Loading feedback…</div>
          ) : !selectedRunId ? (
            <div className="p-8 bg-white rounded-[12px] border border-[#DDE6F0] text-center text-sm text-slate-500">
              Select an evaluation to view its feedback history.
            </div>
          ) : runFeedback.length === 0 ? (
            <div className="p-8 bg-white rounded-[12px] border border-[#DDE6F0] text-center">
              <div className="text-sm font-bold text-slate-700">No feedback recorded for this evaluation.</div>
              <div className="text-xs text-slate-400 mt-1">Submit feedback using the Submit Feedback tab.</div>
              <button
                onClick={() => setActiveTab('submit')}
                className="mt-3 text-xs font-bold text-[#0B5D3B] hover:underline"
              >
                Submit first feedback →
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-extrabold text-slate-900">
                  {runFeedback.length} Feedback {runFeedback.length === 1 ? 'Record' : 'Records'} — {selectedRun?.startupName}
                </h3>
                <div className="text-xs text-slate-500">
                  Avg: {(runFeedback.reduce((s, f) => s + f.rating, 0) / runFeedback.length).toFixed(1)}/5
                </div>
              </div>
              {runFeedback.map(fb => (
                <div key={fb.id} className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-sm font-extrabold text-slate-900">{fb.userName || 'Anonymous'}</div>
                      <div className="text-[11px] text-slate-400 mt-0.5">
                        {fb.createdAt ? new Date(fb.createdAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}
                      </div>
                    </div>
                    <StarDisplay rating={fb.rating} />
                  </div>
                  {fb.comment && (
                    <p className="mt-3 text-xs text-slate-700 leading-relaxed border-t border-[#DDE6F0] pt-3">
                      {fb.comment}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── TAB: DASHBOARD ── */}
      {activeTab === 'dashboard' && (
        <div className="space-y-6">
          {dashError && (
            <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">{dashError}</div>
          )}

          {dashLoading ? (
            <div className="p-8 text-center text-sm text-slate-400">Loading feedback dashboard…</div>
          ) : (
            <>
              {/* Summary KPIs */}
              <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Total Feedback</div>
                  <div className="text-2xl font-black text-slate-900 mt-1">{totalFeedback}</div>
                </div>
                <div className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Average Rating</div>
                  <div className="text-2xl font-black text-slate-900 mt-1">{totalFeedback > 0 ? avgRating.toFixed(1) : '—'}</div>
                  <div className="text-[10px] text-slate-400">out of 5.0</div>
                </div>
                <div className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">5-Star Reviews</div>
                  <div className="text-2xl font-black text-[#12B76A] mt-1">{ratingCounts[4]}</div>
                </div>
                <div className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Evaluations Reviewed</div>
                  <div className="text-2xl font-black text-slate-900 mt-1">
                    {new Set(allFeedback.map(f => f.runId)).size}
                  </div>
                </div>
              </section>

              <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Rating Distribution */}
                <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
                  <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-900 mb-4 pb-2 border-b border-[#DDE6F0]">
                    Rating Distribution
                  </h3>
                  <div className="space-y-2.5">
                    {[5, 4, 3, 2, 1].map(r => (
                      <div key={r} className="flex items-center gap-3">
                        <span className="text-xs font-bold text-slate-600 w-10 shrink-0">{r} ★</span>
                        <RatingBar value={ratingCounts[r - 1]} total={totalFeedback} />
                        <span className="text-[11px] text-slate-400 w-8 shrink-0">
                          {totalFeedback > 0 ? `${Math.round((ratingCounts[r - 1] / totalFeedback) * 100)}%` : '0%'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Top Rated Evaluations */}
                <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
                  <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-900 mb-4 pb-2 border-b border-[#DDE6F0]">
                    Top Rated Evaluations
                  </h3>
                  {topRated.length === 0 ? (
                    <div className="text-xs text-slate-400 py-4 text-center">No feedback recorded yet.</div>
                  ) : (
                    <div className="space-y-2.5">
                      {topRated.map(fb => (
                        <div key={fb.id} className="flex items-center justify-between gap-3 p-2.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                          <div>
                            <div className="text-xs font-bold text-slate-900">{fb.startupName || `Run #${fb.runId}`}</div>
                            <div className="text-[11px] text-slate-500">{fb.userName}</div>
                          </div>
                          <StarDisplay rating={fb.rating} />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>

              {/* Full Feedback Log */}
              <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
                <div className="flex items-center justify-between mb-4 pb-2 border-b border-[#DDE6F0]">
                  <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-900">
                    All Feedback Records
                  </h3>
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                    {totalFeedback} Total
                  </span>
                </div>

                {allFeedback.length === 0 ? (
                  <div className="py-8 text-center text-xs text-slate-400">
                    No feedback submitted yet.
                    <button onClick={() => setActiveTab('submit')} className="ml-2 font-bold text-[#0B5D3B] hover:underline">
                      Be the first →
                    </button>
                  </div>
                ) : (
                  <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
                    {allFeedback.map(fb => (
                      <div key={fb.id} className="p-4 border border-[#DDE6F0] rounded-lg bg-[#F5F8FC]">
                        <div className="flex items-start justify-between gap-4 flex-wrap">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-extrabold text-slate-900">{fb.userName || 'Anonymous'}</span>
                              {fb.recommendation && (
                                <span className={`text-[10px] px-2 py-0.5 rounded font-extrabold uppercase ${
                                  fb.recommendation === 'Invest' ? 'bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]' :
                                  fb.recommendation === 'Observe' ? 'bg-[#FFFAEB] text-[#B54708] border border-[#FEDF89]' :
                                  'bg-[#FEF3F2] text-[#B42318] border border-[#FECDCA]'
                                }`}>
                                  {fb.recommendation}
                                </span>
                              )}
                            </div>
                            <div className="text-[11px] text-slate-500 mt-0.5">
                              <span className="font-bold text-slate-700">{fb.startupName || `Run #${fb.runId}`}</span>
                              {fb.founderName ? ` · ${fb.founderName}` : ''}
                            </div>
                          </div>
                          <div className="text-right">
                            <StarDisplay rating={fb.rating} />
                            <div className="text-[10px] text-slate-400 mt-0.5">
                              {fb.createdAt ? new Date(fb.createdAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}
                            </div>
                          </div>
                        </div>
                        {fb.comment && (
                          <p className="mt-2.5 text-xs text-slate-700 leading-relaxed border-t border-[#DDE6F0] pt-2.5">
                            {fb.comment}
                          </p>
                        )}
                        {fb.trustScore != null && (
                          <div className="mt-2 text-[10px] text-slate-400">
                            Trust Score: <strong className="text-slate-600">{fb.trustScore}/100</strong>
                            {fb.integrityGrade ? ` · Grade ${fb.integrityGrade}` : ''}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      )}
    </PilotWorkspaceShell>
  )
}

export default function FeedbackPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">Loading…</div>}>
      <FeedbackPageInner />
    </Suspense>
  )
}
