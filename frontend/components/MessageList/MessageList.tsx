import React, { useEffect, useRef } from 'react'

export default function MessageList({ messages, streamingMessageId, showCursor }: { messages: Array<{ id: string; role: string; content: string }>; streamingMessageId?: string | null; showCursor?: boolean }) {
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
            <MessageContent content={m.content} showCursor={showCursor && streamingMessageId === m.id} />
          </div>
        </div>
      ))}
    </div>
  )
}

function MessageContent({ content, showCursor }: { content: string; showCursor?: boolean }) {
  return (
    <div className="whitespace-pre-wrap">
      {content}
      {showCursor ? <span className="inline-block ml-1 text-gray-600" style={{ fontWeight: 600 }}>▋</span> : null}
    </div>
  )
}
