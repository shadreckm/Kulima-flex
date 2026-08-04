/*
Standalone SSE streaming test script for Kulima OS Web.
Run with: node frontend/test-stream.js
*/

const fetch = require('node-fetch')
const { AbortController } = require('abort-controller')

const BASE = process.env.KULIMA_API_URL || 'http://localhost:8000'
const URL = `${BASE}/api/v1/ask/ic/stream`

function now() {
  return Date.now()
}

async function runTest() {
  const payload = { runId: 'ts-test-run', question: 'Please provide a mock recommendation.', history: [] }
  const controller = new AbortController()
  const start = now()
  console.log('POST', URL)
  const res = await fetch(URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: controller.signal,
  })
  if (!res.ok) {
    const t = await res.text()
    console.error('Unexpected status', res.status, t)
    return
  }

  const reader = res.body.readable.getReader ? res.body.readable.getReader() : res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  let firstChunkAt = null
  const events = []

  setTimeout(() => {
    console.log('Aborting stream after 3s')
    controller.abort()
  }, 3000)

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value, { stream: true })
      if (!firstChunkAt) firstChunkAt = (now() - start) / 1000
      buf += chunk
      while (buf.indexOf('\n\n') !== -1) {
        const idx = buf.indexOf('\n\n')
        const raw = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        const lines = raw.split(/\r?\n/)
        let ev = null
        let data = ''
        for (const line of lines) {
          if (line.startsWith('event:')) ev = line.slice(6).trim()
          else if (line.startsWith('data:')) data += line.slice(5)
        }
        const t = (now() - start) / 1000
        console.log(`[${t.toFixed(3)}s] event=${ev}, data=${data.replace(/\n/g, '\n')}`)
        events.push({ ev, data, t })
      }
    }
  } catch (err) {
    console.log('Stream error / aborted:', err.message || err)
  }

  const total = (now() - start) / 1000
  const deltas = events.filter(e => e.ev === 'delta')
  const complete = events.find(e => e.ev === 'complete')
  const chunkCount = deltas.length
  const totalChars = deltas.reduce((s, e) => s + e.data.length, 0)
  const avgChunk = chunkCount ? totalChars / chunkCount : 0

  console.log('--- Summary ---')
  console.log('first chunk at (s):', firstChunkAt)
  console.log('chunk count:', chunkCount)
  console.log('avg chunk size:', avgChunk)
  console.log('complete event present:', !!complete)
  console.log('total duration (s):', total)
}

runTest().catch(err => console.error('Fatal', err))
