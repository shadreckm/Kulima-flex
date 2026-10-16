import React, { useEffect, useRef, useState } from 'react'
import MessageList from '../MessageList/MessageList'
import Composer from '../Composer/Composer'
import ConversationSidebar from '../ConversationSidebar/ConversationSidebar'
import { Card } from '../shadcn/Card'
import { Button } from '../shadcn/Button'
import { Badge } from '../shadcn/Badge'

interface Message { id: string; role: 'user' | 'assistant' | 'system'; content: string }

import * as api from '../../lib/api'
import { loadUseCase, useCaseContextHint } from '../../lib/use-case-store'

export default function ChatShell({ personaName, initialMessages, recommendationCard, runId, assessmentId }: { personaName: string; initialMessages?: Message[]; recommendationCard?: any; runId?: string | null; /** Assessment Context id — scopes every conversation (Phases 1–4). */ assessmentId?: string | null }) {
  const [messages, setMessages] = useState<Message[]>(() => initialMessages || [])
  const [conversations, setConversations] = useState<api.AnalystConversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [typing, setTyping] = useState(false)
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null)

  const [autoScroll, setAutoScroll] = useState(true)
  const [hasNewMessages, setHasNewMessages] = useState(false)

  const containerRef = useRef<HTMLDivElement | null>(null)
  const endRef = useRef<HTMLDivElement | null>(null)

  // Build use-case context hint to send as the first system message
  // This removes the need for AI Analyst to ask the user what they're evaluating.
  const useCaseCtx = useCaseContextHint(loadUseCase())
  const contextHistory: Array<{ role: string; content: string }> = useCaseCtx
    ? [{ role: 'system', content: useCaseCtx }]
    : []

  // ── Phase 2/3: load conversations scoped to THIS assessment only ─────────
  // Never loads another assessment's chats (Phase 4 isolation is enforced
  // server-side; the sidebar list is keyed by assessmentId).
  useEffect(() => {
    if (!assessmentId) {
      setConversations([])
      setActiveConversationId(null)
      return
    }
    let cancelled = false
    api.listConversations(assessmentId)
      .then(res => {
        if (cancelled) return
        const convs = res.conversations || []
        setConversations(convs)
        const preferred = convs[0] || null
        setActiveConversationId(preferred ? preferred.conversationId : null)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [assessmentId])

  // Load the selected conversation's server-persisted messages.
  useEffect(() => {
    if (!assessmentId || !activeConversationId) {
      if (!activeConversationId) setMessages([])
      return
    }
    let cancelled = false
    api.getConversationMessages(assessmentId, activeConversationId)
      .then(res => {
        if (cancelled) return
        const serverMessages: Message[] = (res.messages || []).map(m => ({
          id: `srv_${m.id}`,
          role: (m.role === 'user' ? 'user' : 'assistant') as Message['role'],
          content: m.content,
        }))
        setMessages(serverMessages)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [assessmentId, activeConversationId])

  function selectConversation(conversationId: string) {
    setActiveConversationId(conversationId)
  }

  function handleAssessmentSwitch(nextAssessmentId: string) {
    if (nextAssessmentId === assessmentId) return
    // Full context switch: clear local chat state; the conversation effect
    // refetches only the target assessment's conversations (Phase 4).
    setMessages([])
    setActiveConversationId(null)
    setConversations([])
    window.dispatchEvent(
      new CustomEvent('kulima:switch-assessment', { detail: { assessmentId: nextAssessmentId } }),
    )
  }

  // Scroll lock: detect user scroll
  useEffect(() => {
    function onScroll() {
      const el = containerRef.current
      if (!el) return
      const threshold = 120
      const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= threshold
      if (atBottom) {
        setAutoScroll(true)
        setHasNewMessages(false)
      } else {
        setAutoScroll(false)
      }
    }

    const el = containerRef.current
    if (!el) return
    el.addEventListener('scroll', onScroll)
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    // handle auto-scroll when messages change
    if (autoScroll && containerRef.current) {
      try {
        containerRef.current.scrollTo({ top: containerRef.current.scrollHeight, behavior: 'smooth' })
      } catch (e) {
        containerRef.current.scrollTop = containerRef.current.scrollHeight
      }
    } else {
      if (messages.length > 0) setHasNewMessages(true)
    }
  }, [messages])

  function appendMessage(m: Message) {
    setMessages(prev => [...prev, m])
  }

  // Mock SSE streaming with variable chunks, pauses, and burst typing
  function simulateSSEStreaming(responseText: string) {
    setIsStreaming(true)
    setTyping(true)
    const preTypingDelay = 300 + Math.random() * 500
    setTimeout(() => {
      setTyping(false)

      const assistantId = `a_${Date.now()}`
      setStreamingMessageId(assistantId)
      appendMessage({ id: assistantId, role: 'assistant', content: '' })

      const words = responseText.match(/\S+|\s+/g) || [responseText]

      let i = 0
      function scheduleNextChunk() {
        if (i >= words.length) {
          setIsStreaming(false)
          setStreamingMessageId(null)
          return
        }
        const chunkSize = Math.random() < 0.05 ? 0 : Math.max(1, Math.floor(Math.random() * 5) + 1)
        let chunk = ''
        for (let c = 0; c < chunkSize && i < words.length; c++, i++) chunk += words[i]

        if (chunk.length > 0) {
          setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: m.content + chunk } : m))
        }

        let delay = 20 + Math.random() * 100
        setTimeout(scheduleNextChunk, delay)
      }

      scheduleNextChunk()
    }, preTypingDelay)
  }

  async function handleSend(text: string, attachments?: Array<{ id: string; name: string }>) {
    if (!text || text.trim().length === 0) return
    const userId = `u_${Date.now()}`
    appendMessage({ id: userId, role: 'user', content: text })

    if (runId) {
      setIsStreaming(true)
      setTyping(true)
      let stream: any = null
      let assistantId = `a_${Date.now()}`
      let receivedText = ''
      try {
        if (personaName.toLowerCase().includes('ic')) {
          stream = api.askICStreamWithConversation(runId, text, contextHistory, activeConversationId, assessmentId)
        } else if (personaName.toLowerCase().includes('signal')) {
          stream = api.askSignalsStream(runId, text, contextHistory)
        } else {
          stream = api.askICStreamWithConversation(runId, text, contextHistory, activeConversationId, assessmentId)
        }
      } catch (e) {
        stream = null
      }

      if (stream && typeof stream.addEventListener === 'function') {
        appendMessage({ id: assistantId, role: 'assistant', content: '' })
        const onDelta = (ev: any) => {
          try {
            const payload = JSON.parse(ev.data)
            const chunk = payload.text || ''
            receivedText += chunk
            setMessages((cur) => {
              const last = cur[cur.length - 1]
              if (last && last.role === 'assistant') {
                const updated = [...cur]
                updated[updated.length - 1] = { ...last, content: last.content + chunk }
                return updated
              }
              return [...cur, { id: assistantId, role: 'assistant', content: chunk }]
            })
          } catch (err) {
            console.error('delta parse', err)
          }
        }
        const onComplete = () => {
          setIsStreaming(false)
          setTyping(false)
          try { stream.close() } catch (e) {}
          // Refresh sidebar counters after the exchange completes.
          if (assessmentId) {
            api.listConversations(assessmentId).then(res => setConversations(res.conversations || [])).catch(() => {})
          }
        }
        const onError = (err: any) => {
          console.error('stream error', err)
          try { stream.close() } catch (e) {}
          if (!receivedText) {
            setMessages((cur) => cur.filter(m => m.id !== assistantId))
            const fallbackResponse = "The AI Analyst is currently unavailable. Please try again later."
            simulateSSEStreaming(fallbackResponse)
          } else {
            setIsStreaming(false)
            setTyping(false)
          }
        }
        stream.addEventListener('delta', onDelta)
        stream.addEventListener('complete', onComplete)
        stream.addEventListener('error', onError)
        return
      }

      // Fallback: non-streaming API (conversation-bound)
      try {
        const res = await api.askICWithConversation(runId, text, contextHistory, activeConversationId, assessmentId)
        if (res?.answer) {
          simulateSSEStreaming(res.answer)
        } else {
          const fallbackResponse = "The AI Analyst is currently unavailable. Please try again later."
          simulateSSEStreaming(fallbackResponse)
        }
      } catch (err) {
        console.error('Ask failed', err)
        const fallbackResponse = "The AI Analyst is currently unavailable. Please try again later."
        simulateSSEStreaming(fallbackResponse)
      } finally {
        setIsStreaming(false)
        setTyping(false)
      }
      return
    }

    // No runId: inform user
    const fallbackResponse = "No active assessment selected. Please create or start an assessment to consult the analyst."
    simulateSSEStreaming(fallbackResponse)
  }

  function scrollToLatest() {
    if (!containerRef.current) return
    try { containerRef.current.scrollTo({ top: containerRef.current.scrollHeight, behavior: 'smooth' }) } catch (e) { containerRef.current.scrollTop = containerRef.current.scrollHeight }
    setAutoScroll(true)
    setHasNewMessages(false)
  }

  const activeConversation = conversations.find(c => c.conversationId === activeConversationId) || null

  return (
    <div className="flex-1 min-h-0 flex gap-3">
      {/* Phase 2/5/6: conversation sidebar */}
      {assessmentId ? (
        <div className="hidden md:flex w-[230px] shrink-0">
          <ConversationSidebar
            assessmentId={assessmentId}
            activeConversationId={activeConversationId}
            onSelectConversation={selectConversation}
            onAssessmentSwitch={handleAssessmentSwitch}
          />
        </div>
      ) : null}

      <Card className="flex-1 min-h-0 flex flex-col relative overflow-hidden">
        <header className="p-4 border-b border-[#DDE6F0] flex items-center justify-between bg-white">
          <div>
            <h2 className="text-sm font-extrabold text-slate-900">
              {personaName}
              {activeConversation ? <span className="text-slate-400 font-medium"> — {activeConversation.title}</span> : null}
            </h2>
            <p className="text-xs text-slate-500">
              {runId
                ? `Assessment context loaded${activeConversation ? ` · ${activeConversation.title}` : ''}`
                : 'No evaluation selected'}
            </p>
          </div>
          {recommendationCard ? (
            <div className="flex items-center gap-3">
              <Badge className="bg-green-100 text-green-800">{recommendationCard.verdict}</Badge>
              <div className="text-xs text-gray-600">Score: {recommendationCard.score}</div>
            </div>
          ) : null}
        </header>

        <div ref={containerRef} className="flex-1 p-4 overflow-auto scroll-area" style={{ minHeight: 0 }}>
          <MessageList messages={messages} streamingMessageId={streamingMessageId} showCursor={isStreaming} />
          {typing && (
            <div className="mt-3">
              <div className="kulima-message-assistant inline-block p-2 opacity-90">
                <TypingDots />
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* New messages floating button */}
        {!autoScroll && hasNewMessages && (
          <div className="absolute left-1/2 transform -translate-x-1/2 bottom-20">
            <Button onClick={scrollToLatest} className="shadow">↓ New messages</Button>
          </div>
        )}

        <div id="documents" className="kulima-composer sticky bottom-0 bg-white border-t">
          <div className="p-3">
            <Composer onSend={handleSend} runId={runId} />
          </div>
        </div>
      </Card>
    </div>
  )
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="kulima-typing-dot bg-gray-400 w-2 h-2 rounded-full inline-block" />
      <span className="kulima-typing-dot bg-gray-400 w-2 h-2 rounded-full inline-block" style={{ animationDelay: '200ms' }} />
      <span className="kulima-typing-dot bg-gray-400 w-2 h-2 rounded-full inline-block" style={{ animationDelay: '400ms' }} />
    </span>
  )
}
