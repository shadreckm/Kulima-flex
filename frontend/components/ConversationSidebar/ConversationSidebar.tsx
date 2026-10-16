'use client'

/**
 * ConversationSidebar — ChatGPT-style conversation management for the
 * AI Analyst (Phases 2, 5, 6).
 *
 * Sections:
 *   + New Conversation  → create a new chat inside the ACTIVE assessment
 *   History             → conversations of the active assessment only
 *   Recent Assessments  → assessment history (name, type, trust, date,
 *                         conversation count) with switch/reopen
 */

import React, { useEffect, useState } from 'react'
import * as api from '../../lib/api'
import type {
  AnalystConversation,
  AnalystAssessmentHistoryRow,
} from '../../lib/api'

export interface ConversationSidebarProps {
  assessmentId: string | null
  activeConversationId: string | null
  onSelectConversation: (conversationId: string) => void
  onAssessmentSwitch: (assessmentId: string) => void
}

export default function ConversationSidebar({
  assessmentId,
  activeConversationId,
  onSelectConversation,
  onAssessmentSwitch,
}: ConversationSidebarProps) {
  const [conversations, setConversations] = useState<AnalystConversation[]>([])
  const [assessments, setAssessments] = useState<AnalystAssessmentHistoryRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')

  useEffect(() => {
    api.getAssessmentChatHistory(20)
      .then(res => setAssessments(res.assessments || []))
      .catch(() => setAssessments([]))
  }, [])

  useEffect(() => {
    if (!assessmentId) {
      setConversations([])
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    api.listConversations(assessmentId)
      .then(res => {
        if (!cancelled) setConversations(res.conversations || [])
      })
      .catch(err => {
        if (!cancelled) setError(String(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [assessmentId])

  async function handleNewConversation() {
    if (!assessmentId) return
    try {
      const conv = await api.createConversation(assessmentId)
      setConversations(prev => [conv, ...prev])
      onSelectConversation(conv.conversationId)
    } catch (err) {
      setError(String(err))
    }
  }

  async function handleRename(conversationId: string) {
    const title = renameValue.trim()
    setRenamingId(null)
    if (!title) return
    try {
      await api.renameConversation(conversationId, title)
      setConversations(prev => prev.map(c => c.conversationId === conversationId ? { ...c, title } : c))
    } catch (err) {
      setError(String(err))
    }
  }

  async function handleDelete(conversationId: string) {
    try {
      await api.deleteConversation(conversationId)
      const remaining = conversations.filter(c => c.conversationId !== conversationId)
      setConversations(remaining)
      if (activeConversationId === conversationId) {
        if (remaining.length > 0) onSelectConversation(remaining[0].conversationId)
        else if (assessmentId) {
          // Deleted the last chat — auto-provision a fresh one.
          const conv = await api.createConversation(assessmentId)
          setConversations([conv])
          onSelectConversation(conv.conversationId)
        }
      }
    } catch (err) {
      setError(String(err))
    }
  }

  return (
    <aside className="w-full h-full flex flex-col gap-4 p-3 bg-white border border-[#DDE6F0] rounded-[12px] shadow-saas overflow-y-auto text-sm">
      <div>
        <button
          onClick={handleNewConversation}
          disabled={!assessmentId}
          className="w-full px-3 py-2 rounded-lg bg-[#0B5D3B] text-white font-bold text-xs hover:bg-[#08482E] transition disabled:opacity-40 disabled:cursor-not-allowed"
        >
          + New Conversation
        </button>
      </div>

      <div>
        <div className="text-[11px] font-bold uppercase tracking-wide text-slate-400 mb-2 px-1">
          History {assessmentId ? '' : '(select an assessment)'}
        </div>
        {loading ? (
          <div className="px-2 py-1 text-xs text-slate-400">Loading…</div>
        ) : error ? (
          <div className="px-2 py-1 text-xs text-red-500">{error}</div>
        ) : conversations.length === 0 ? (
          <div className="px-2 py-1 text-xs text-slate-400">No conversations yet.</div>
        ) : (
          <ul className="flex flex-col gap-1">
            {conversations.map(conv => (
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
                    className="w-full px-2 py-1.5 text-xs rounded-md border border-[#0B5D3B] outline-none"
                  />
                ) : (
                  <div
                    className={`group flex items-center justify-between gap-1 px-2 py-1.5 rounded-md cursor-pointer transition ${
                      activeConversationId === conv.conversationId
                        ? 'bg-[#ECFDF5] text-[#064E3B] font-semibold'
                        : 'hover:bg-slate-50 text-slate-700'
                    }`}
                    onClick={() => onSelectConversation(conv.conversationId)}
                  >
                    <span className="truncate flex-1" title={conv.title}>
                      {conv.title}
                    </span>
                    <span className="text-[10px] text-slate-400 shrink-0">{conv.messageCount}</span>
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
                        ✕
                      </button>
                    </span>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <div className="text-[11px] font-bold uppercase tracking-wide text-slate-400 mb-2 px-1">
          Recent Assessments
        </div>
        {assessments.length === 0 ? (
          <div className="px-2 py-1 text-xs text-slate-400">No assessments yet.</div>
        ) : (
          <ul className="flex flex-col gap-1">
            {assessments.map(a => (
              <li key={a.assessmentId}>
                <button
                  onClick={() => onAssessmentSwitch(a.assessmentId)}
                  className={`w-full text-left px-2 py-1.5 rounded-md transition ${
                    assessmentId === a.assessmentId
                      ? 'bg-[#ECFDF5] font-semibold'
                      : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="truncate text-xs font-semibold text-slate-800" title={a.assessmentName}>
                    {a.assessmentName}
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-slate-400">
                    <span className="capitalize">{(a.assessmentType || '').replace('_', ' ')}</span>
                    <span>
                      {a.trustScore != null ? `Trust ${Math.round(a.trustScore)}/100 · ` : ''}
                      {a.conversationCount} chat{a.conversationCount === 1 ? '' : 's'}
                    </span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  )
}
