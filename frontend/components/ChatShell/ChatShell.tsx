import React, { useEffect, useRef, useState } from 'react'
import MessageList from '../MessageList/MessageList'
import Composer from '../Composer/Composer'
import { Card } from '../shadcn/Card'
import { Button } from '../shadcn/Button'
import { Badge } from '../shadcn/Badge'

interface Message { id: string; role: 'user' | 'assistant' | 'system'; content: string }

const MOCK_REPLY = `Recommendation: PASS. The founding team demonstrates strong domain expertise and early traction. Key factors: product-market fit, efficient unit economics, and a defensible niche. Top risks include runway constraints and competitive pressure. Suggested next steps: validate retention cohorts and secure bridge funding.`

import * as api from '../../lib/api'

export default function ChatShell({ personaName, initialMessages, recommendationCard, runId }: { personaName: string; initialMessages?: Message[]; recommendationCard?: any; runId?: string | null }) {
  const storageKey = `kulima_messages_${personaName.replace(/\s+/g, '_')}`
  const [messages, setMessages] = useState<Message[]>(() => initialMessages || [])
  const [isStreaming, setIsStreaming] = useState(false)
  const [typing, setTyping] = useState(false)
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null)

  const [autoScroll, setAutoScroll] = useState(true)
  const [hasNewMessages, setHasNewMessages] = useState(false)

  const containerRef = useRef<HTMLDivElement | null>(null)
  const endRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    // load persisted messages
    try {
      const raw = localStorage.getItem(storageKey)
      if (raw) setMessages(JSON.parse(raw))
    } catch (e) {
      // ignore
    }
  }, [])

  useEffect(() => {
    // persist
    try { localStorage.setItem(storageKey, JSON.stringify(messages)) } catch (e) {}
  }, [messages])

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
      // debounce reset not necessary here
    }

    const el = containerRef.current
    if (!el) return
    el.addEventListener('scroll', onScroll)
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    // handle auto-scroll when messages change
    if (autoScroll && containerRef.current) {
      // smooth scroll to bottom
      try {
        containerRef.current.scrollTo({ top: containerRef.current.scrollHeight, behavior: 'smooth' })
      } catch (e) {
        containerRef.current.scrollTop = containerRef.current.scrollHeight
      }
    } else {
      // if not auto-scrolling, indicate new messages available
      if (messages.length > 0) setHasNewMessages(true)
    }
  }, [messages])

  function appendMessage(m: Message) {
    setMessages(prev => [...prev, m])
  }

  // Mock SSE streaming with variable chunks, pauses, and burst typing
  function simulateSSEStreaming(responseText: string) {
    setIsStreaming(true)
    // show typing indicator briefly before streaming
    setTyping(true)
    const preTypingDelay = 300 + Math.random() * 700 // 300-1000ms
    setTimeout(() => {
      setTyping(false)

      // create assistant placeholder
      const assistantId = `a_${Date.now()}`
      setStreamingMessageId(assistantId)
      appendMessage({ id: assistantId, role: 'assistant', content: '' })

      // split by words but keep punctuation
      const words = responseText.match(/\S+|\s+/g) || [responseText]

      let i = 0
      function scheduleNextChunk() {
        if (i >= words.length) {
          // done
          setIsStreaming(false)
          setStreamingMessageId(null)
          return
        }
        // chunk size: 1-6 words, but sometimes 0 to simulate pauses
        const chunkSize = Math.random() < 0.05 ? 0 : Math.max(1, Math.floor(Math.random() * 5) + 1)
        let chunk = ''
        for (let c = 0; c < chunkSize && i < words.length; c++, i++) chunk += words[i]

        // append chunk
        if (chunk.length > 0) {
          setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: m.content + chunk } : m))
        }

        // variable delay
        let delay = 20 + Math.random() * 180 // 20-200ms
        // occasional longer pause
        if (Math.random() < 0.08) delay += 200 + Math.random() * 800 // add 200-1000ms
        // simulate burst: smaller delays sometimes for several chunks
        if (Math.random() < 0.15) delay = 10 + Math.random() * 80

        setTimeout(scheduleNextChunk, delay)
      }

      scheduleNextChunk()
    }, preTypingDelay)
  }

  async function handleSend(text: string, attachments?: Array<{ id: string; name: string }>) {
    if (!text || text.trim().length === 0) return
    const userId = `u_${Date.now()}`
    appendMessage({ id: userId, role: 'user', content: text })

      // If runId is provided, try streaming from backend, else fallback to non-streaming
      if (runId) {
        setIsStreaming(true)
        setTyping(true)
        let stream: any = null
        let assistantId = `a_${Date.now()}`
        try {
          if (personaName.toLowerCase().includes('ic')) {
            stream = api.askICStream(runId, text, [])
          } else if (personaName.toLowerCase().includes('signal')) {
            stream = api.askSignalsStream(runId, text, [])
          } else {
            stream = api.askICStream(runId, text, [])
          }
        } catch (e) {
          stream = null
        }

        if (stream && typeof stream.addEventListener === 'function') {
          // create assistant placeholder
          appendMessage({ id: assistantId, role: 'assistant', content: '' })
          const onDelta = (ev: any) => {
            try {
              const payload = JSON.parse(ev.data)
              const chunk = payload.text || ''
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
          }
          const onError = (err: any) => {
            console.error('stream error', err)
            try { stream.close() } catch (e) {}
            setIsStreaming(false)
            setTyping(false)
          }
          stream.addEventListener('delta', onDelta)
          stream.addEventListener('complete', onComplete)
          stream.addEventListener('error', onError)
          return
        }

        // fallback: non-streaming ask endpoint
        try {
          const res = personaName.toLowerCase().includes('signal') ? await api.askSignals(runId, text, []) : await api.askIC(runId, text, [])
          simulateSSEStreaming(res.answer)
        } catch (err) {
          console.error('Ask failed', err)
          appendMessage({ id: `e_${Date.now()}`, role: 'assistant', content: 'Error: failed to get answer from backend.' })
        } finally {
          setIsStreaming(false)
          setTyping(false)
        }
        return
      }

      // No runId: mock mode
      const simulatedResponse = MOCK_REPLY
      simulateSSEStreaming(simulatedResponse)
    }

  function scrollToLatest() {
    if (!containerRef.current) return
    try { containerRef.current.scrollTo({ top: containerRef.current.scrollHeight, behavior: 'smooth' }) } catch (e) { containerRef.current.scrollTop = containerRef.current.scrollHeight }
    setAutoScroll(true)
    setHasNewMessages(false)
  }

  return (
    <Card className="flex-1 flex flex-col relative">
      <header className="p-4 border-b flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">{personaName}</h2>
          <p className="text-sm text-gray-500">IC Analyst</p>
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
