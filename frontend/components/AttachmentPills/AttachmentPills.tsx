import React from 'react'

export default function AttachmentPills({ attachments, onRemove }: { attachments: Array<{ id: string; name: string }>; onRemove: (id: string) => void }) {
  if (!attachments || attachments.length === 0) return null
  return (
    <div className="flex gap-2 mb-2">
      {attachments.map(a => (
        <div key={a.id} className="px-3 py-1 bg-gray-100 rounded-full flex items-center gap-2">
          <span>📎</span>
          <span className="text-sm">{a.name}</span>
          <button onClick={() => onRemove(a.id)} className="text-xs text-gray-500">×</button>
        </div>
      ))}
    </div>
  )
}
