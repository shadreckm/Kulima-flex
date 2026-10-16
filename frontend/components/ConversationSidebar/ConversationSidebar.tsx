'use client'

/**
 * ConversationSidebar — Conversation UX architecture.
 *
 * Hierarchy (Problem 3): ASSESSMENTS are primary, CONVERSATIONS are
 * secondary. Rendered as a two-level tree:
 *
 *   Assessment A
 *   ├── Chat 1        ← active
 *   ├── Chat 2
 *   Assessment B
 *   ├── Chat 1
 *
 * Actions (Problem 1): two clearly separated primary actions —
 *   [+ New Chat]        another conversation under the SAME assessment
 *   [+ New Assessment]  → landing page / upload workflow / assessment creation
 *
 * Switching (Problem 2/5): clicking an assessment loads the full workspace
 * context (conversations → messages → decision snapshot → trust → signals)
 * via switchAssessmentContext().
 */

import React, { useEffect, useState } from 'react'
import * as api from '../../lib/api'
import type {
  AnalystConversation,
  AnalystAssessmentHistoryRow,
} from '../../lib/api'

export interface ConversationSidebarProps {
  assessmentId: string | null
  assessmentName?: string | null
  activeConversationId: string | null
  /** conversation list for the currently open assessment */
  conversations: AnalystConversation[]
  onSelectConversation: (conversationId: string) => void
  onAssessmentSwitch: (assessmentId: string) => void
  onCreateConversation: () => void
  onNewAssessment: () => void
  onConversationChanged?: () => void
}

export default function ConversationSidebar({
  assessmentId,
  assessmentName,
  activeConversationId,
  conversations,
  onSelectConversation,
  onAssessmentSwitch,
  onCreateConversation,
  onNewAssessment,
  onConversationChanged,
}: ConversationSidebarProps) {
  const [assessments, setAssessments] = useState<AnalystAssessmentHistoryRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [deletingId, setDeletingId] = useState<string | null>(null)

  // Phase 5: assessment history — name, type, trust score, date, chat count.
  useEffect(() => {
    let cancelled = false
    api.getAssessmentChatHistory(20)
      .then(res => { if (!cancelled) setAssessments(res.assessments || []) })
      .catch(() => { if (!cancelled) setAssessments([]) })
    return () => { cancelled = true }
  }, [assessmentId])

  async function handleRename(conversationId: string) {
    const title = renameValue.trim()
    setRenamingId(null)
    if (!title) return
    try {
      await api.renameConversation(conversationId, title)
      onConversationChanged?.()
    } catch (err) {
      setError(String(err))
    }
  }

  async function handleDelete(conversationId: string) {
    setDeletingId(conversationId)
    setError(null)
    try {
      const res = await api.deleteConversation(conversationId)
      if (!res?.deleted) throw new Error('Delete did not complete')
      onConversationChanged?.()
    } catch (err) {
      setError(String(err))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <aside className="w-full h-full flex flex-col bg-white border border-[#DDE6F0] rounded-[12px] shadow-saas overflow-hidden text-sm">
      {/* ── Two clearly separated primary actions (Problem 1) ─────────────── */}
      <div className="p-3 flex flex-col gap-2 border-b border-[#DDE6F0]">
        <button
          onClick={onCreateConversation}
          disabled={!assessmentId}
          className="w-full px-3 py-2 rounded-lg bg-[#0B5D3B] text-white font-bold text-xs hover:bg-[#08482E] transition disabled:opacity-40 disabled:cursor-not-allowed"
          title="Creates another conversation under the current assessment"
        >
          + New Chat
        </button>
        <button
          onClick={onNewAssessment}
          className="w-full px-3 py-2 rounded-lg border-2 border-[#0B5D3B] text-[#0B5D3B] font-bold text-xs hover:bg-[#ECFDF5] transition"
          title="Upload documents and create a new assessment"
        >
          + New Assessment
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-3">
        {error ? (
          <div className="px-2 py-1 mb-2 text-xs text-red-500">{error}</div>
        ) : null}

        {/* ── Hierarchy: assessments primary, chats nested (Problem 3) ────── */}
        {assessments.length === 0 ? (
          <div className="px-2 py-1 text-xs text-slate-400">No assessments yet.</div>
        ) : (
          <ul className="flex flex-col gap-2">
            {assessments.map(a => {
              const isCurrent = a.assessmentId === assessmentId
              return (
                <li key={a.assessmentId}>
                  {/* Assessment (primary node) — click loads full workspace */}
                  <button
                    onClick={() => onAssessmentSwitch(a.assessmentId)}
                    className={`w-full text-left px-2 py-2 rounded-md transition ${
                      isCurrent
                        ? 'bg-[#ECFDF5] border border-[#A7F3D0]'
                        : 'hover:bg-slate-50 border border-transparent'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span
                        className="truncate text-xs font-extrabold text-slate-900"
                        title={a.assessmentName}
                      >
                        {a.assessmentName}
                      </span>
                      <span className="text-[10px] shrink-0 font-bold text-[#0B5D3B]">
                        {a.trustScore != null ? `${Math.round(a.trustScore)}` : '—'}
                        <span className="font-normal text-slate-400">/100</span>
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-slate-400 mt-0.5">
                      <span className="capitalize truncate">
                        {(a.assessmentType || '').replace('_', ' ')}
                        {a.createdAt ? ` · ${new Date(a.createdAt).toLocaleDateString()}` : ''}
                      </span>
                      <span className="shrink-0">
                        {a.conversationCount} chat{a.conversationCount === 1 ? '' : 's'}
                      </span>
                    </div>
                  </button>

                  {/* Conversations (secondary nodes) — only under the open assessment */}
                  {isCurrent ? (
                    <ul className="mt-1 ml-3 pl-2 border-l-2 border-[#D1D5DB] flex flex-col gap-0.5">
                      {conversations.length === 0 ? (
                        <li className="px-2 py-1 text-[11px] text-slate-400">No chats yet.</li>
                      ) : (
                        conversations.map(conv => (
                          <li key={conv.conversationId}>
                            {renamingId === conv.conversationId ? (
                              <input
                                autoFocus
                                value={renameValue}
                                onChange={e => setRenameValue(e.target.value)}
                                onBlur={() => handleRename(conv.conversationId)}
                                onKeyDown={e => {
                                  if (e.key === 'Enter') handleRename(conv.conversationId)
                                  if (e.key === 'Escape') setRenamingId(null)
                                }}
                                className="w-full px-2 py-1 text-xs rounded-md border border-[#0B5D3B] outline-none"
                              />
                            ) : (
                              <div
                                className={`group flex items-center gap-1 px-2 py-1 rounded-md cursor-pointer transition ${
                                  activeConversationId === conv.conversationId
                                    ? 'bg-[#D1FAE5] font-semibold'
                                    : 'hover:bg-slate-50'
                                }`}
                                onClick={() => onSelectConversation(conv.conversationId)}
                              >
                                <span className="truncate flex-1 text-[11px] text-slate-700" title={conv.title}>
                                  {conv.title}
                                </span>
                                <span className="text-[9px] text-slate-400 shrink-0">{conv.messageCount}</span>
                                <span className="hidden group-hover:flex items-center gap-0.5 shrink-0">
                                  <button
                                    title="Rename"
                                    onClick={e => {
                                      e.stopPropagation()
                                      setRenamingId(conv.conversationId)
                                      setRenameValue(conv.title)
                                    }}
                                    className="p-0.5 text-[10px] text-slate-400 hover:text-[#0B5D3B]"
                                  >
                                    ✎
                                  </button>
                                  <button
                                    title="Delete"
                                    onClick={e => {
                                      e.stopPropagation()
                                      handleDelete(conv.conversationId)
                                    }}
                                    className="p-0.5 text-[10px] text-slate-400 hover:text-red-500"
                                  >
                                    {deletingId === conv.conversationId ? '…' : '✕'}
                                  </button>
                                </span>
                              </div>
                            )}
                          </li>
                        ))
                      )}
                    </ul>
                  ) : null}
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </aside>
  )
}
