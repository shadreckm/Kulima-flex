import React from 'react'
import Link from 'next/link'

export default function Home() {
  return (
    <main className="p-8">
      <h1 className="text-2xl font-semibold mb-4">Kulima Frontend Prototype</h1>
      <p className="mb-6">Chat-first UX prototype (mock data). Use the links below to open pages.</p>
      <div className="flex gap-4">
        <Link href="/flex" className="px-4 py-2 bg-blue-600 text-white rounded">Open FLEX (Ask IC)</Link>
        <Link href="/signals" className="px-4 py-2 bg-green-600 text-white rounded">Open SIGNALS (Ask SIGNALS)</Link>
      </div>
    </main>
  )
}
