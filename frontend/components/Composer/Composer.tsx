import React, { useState } from 'react'
import AttachmentPills from '../AttachmentPills/AttachmentPills'
import { Button } from '../shadcn/Button'
import { uploadDocument } from '../../lib/api'

export default function Composer({ onSend, runId }: { onSend?: (text: string, attachments?: Array<{ id: string; name: string; url?: string }>) => void; runId?: string | null }) {
  const [text, setText] = useState('')
  const [attachments, setAttachments] = useState<Array<{ id: string; name: string; url?: string }>>([])
  const [uploading, setUploading] = useState(false)

  async function onAttach(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files) return
    const file = files[0]
    setUploading(true)
    try {
      const res = await uploadDocument(file, runId)
      // res: {id, name, url}
      setAttachments(prev => [...prev, { id: res.id, name: res.name, url: res.url }])
    } catch (err) {
      console.error('Upload failed', err)
      alert('File upload failed: ' + String(err))
    } finally {
      setUploading(false)
    }
  }

  function handleSend() {
    if (!text.trim()) return
    onSend && onSend(text.trim(), attachments)
    setText('')
    setAttachments([])
  }

  return (
    <div>
      <AttachmentPills attachments={attachments} onRemove={(id) => setAttachments(attachments.filter(a => a.id !== id))} />
      <div className="flex gap-2 items-center">
        <label className="p-2 bg-gray-100 rounded cursor-pointer">
          {uploading ? 'Uploading…' : '📎'}
          <input type="file" onChange={onAttach} className="hidden" />
        </label>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
          placeholder="Ask anything..."
          className="flex-1 px-3 py-2 rounded border"
        />
        <Button onClick={handleSend} disabled={uploading}>Send</Button>
      </div>
    </div>
  )
}
