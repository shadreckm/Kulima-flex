import React, { useEffect, useRef } from 'react'
import Link from 'next/link'

/**
 * The analyst answers with citation labels that come straight from the context
 * pack it was given (see kulima/signals/ask_signals.py). Rendering them as
 * labelled chips instead of raw bracket text turns every answer into something
 * a user can verify — inline evidence, not a claim they have to trust.
 */
const CITATION_META: Record<string, { label: string; href: string }> = {
  SG: { label: 'Signal', href: '/signals' },
  S: { label: 'Research source', href: '/evidence' },
  D: { label: 'Document', href: '/evidence' },
  C: { label: 'Contradiction', href: '/decision' },
  U: { label: 'Unsupported claim', href: '/decision' },
  TRUST_GRAPH: { label: 'Trust graph', href: '/trust' },
  EVIDENCE_INTEGRITY: { label: 'Evidence integrity', href: '/trust' },
}

const CITATION_RE = /(\[(?:SG\d+|S\d+|D\d+|C\d+|U\d+)\]|\[TRUST_GRAPH\]|\[EVIDENCE_INTEGRITY\])/g
const NEXT_QUESTION_RE = /^(?:\s*)(?:\*\*)?(Next question I['’]d ask|Before making a decision, I['’]d verify|Before acting, verify):(?:\*\*)?\s*(.+)$/im

export default function MessageList({
  messages,
  streamingMessageId,
  showCursor,
  onAskQuestion,
}: {
  messages: Array<{ id: string; role: string; content: string }>
  streamingMessageId?: string | null
  showCursor?: boolean
  /** Sends the analyst's own suggested next question when the user accepts it. */
  onAskQuestion?: (question: string) => void
}) {
  const listRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    // subtle entrance animation by toggling a class after mount
    const el = listRef.current
    if (!el) return
    const items = el.querySelectorAll('.message-item')
    items.forEach((it: Element, idx: number) => {
      const node = it as HTMLElement
      node.style.opacity = '0'
      node.style.transform = 'translateY(6px)'
      setTimeout(() => {
        node.style.transition = 'opacity 220ms ease, transform 220ms ease'
        node.style.opacity = '1'
        node.style.transform = 'translateY(0)'
      }, 40 * idx)
    })
  }, [messages])

  return (
    <div ref={listRef} className="flex flex-col gap-3">
      {messages.map((m) => (
        <div key={m.id} className={`${m.role === 'user' ? 'flex justify-end' : 'flex justify-start'} message-item`}>
          <div className={`${m.role === 'user' ? 'kulima-message-user' : 'kulima-message-assistant'}`}>
            <MessageContent
              content={m.content}
              showCursor={showCursor && streamingMessageId === m.id}
              suggestNext={m.role === 'assistant' && streamingMessageId !== m.id}
              onAskQuestion={onAskQuestion}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

function MessageContent({
  content,
  showCursor,
  suggestNext,
  onAskQuestion,
}: {
  content: string
  showCursor?: boolean
  /** Only finished analyst answers offer the next question — never a half-streamed line. */
  suggestNext?: boolean
  onAskQuestion?: (question: string) => void
}) {
  // The analyst closes some answers with its own recommended follow-up question
  // or verification step. Surfacing it as a button keeps the conversation moving
  // without the user having to invent the next prompt.
  let body = content
  let nextQuestion: string | null = null
  let nextQuestionLabel = 'Suggested next question'
  if (suggestNext) {
    const match = NEXT_QUESTION_RE.exec(content)
    if (match) {
      nextQuestion = match[2].trim().replace(/[*_]+$/g, '')
      if (!match[1].toLowerCase().startsWith('next question')) {
        nextQuestionLabel = 'Worth verifying before you act'
      }
      body = content.replace(match[0], '').trimEnd()
    }
  }

  const parts = body.split(CITATION_RE)

  return (
    <div className="whitespace-pre-wrap">
      {parts.map((part, idx) => {
        const token = /^\[(.+)\]$/.exec(part)
        if (!token) return <React.Fragment key={idx}>{part}</React.Fragment>
        const meta = CITATION_META[token[1]]
        if (!meta) return <React.Fragment key={idx}>{part}</React.Fragment>
        const key = /^(SG|S|D|C|U)(\d+)$/.exec(token[1])
        const ref = key ? `${meta.label} ${key[2]}` : meta.label
        return (
          <Link
            key={idx}
            href={meta.href}
            title={`${ref} — open the ${meta.label.toLowerCase()} this answer is based on`}
            className="mx-0.5 inline-flex items-center align-middle px-1.5 py-0.5 rounded border border-[#D6E8FF] bg-[#EAF3FF] text-[10px] font-bold text-[#004085] hover:bg-white no-underline whitespace-nowrap"
          >
            {ref}
          </Link>
        )
      })}
      {showCursor ? <span className="inline-block ml-1 text-gray-600" style={{ fontWeight: 600 }}>▋</span> : null}
      {nextQuestion && onAskQuestion ? (
        <div className="mt-3 pt-2.5 border-t border-[#DDE6F0]">
          <div className="text-[9px] font-black uppercase tracking-wider text-slate-400">{nextQuestionLabel}</div>
          <button
            type="button"
            onClick={() => onAskQuestion(nextQuestion as string)}
            className="mt-1 px-2.5 py-1.5 rounded-lg border border-[#A6F4C5] bg-[#ECFDF3] text-[11px] font-bold text-[#027A48] hover:bg-white transition text-left"
          >
            {nextQuestion}
          </button>
        </div>
      ) : null}
    </div>
  )
}
