import './globals.css'
import React from 'react'
import AuthSessionProvider from '../components/AuthSessionProvider'

export const metadata = {
  title: 'Kulima FLEX — Defensible Decisions from Documents',
  description: 'Turn reports, proposals, business plans, and financial statements into evidence-backed decision intelligence.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthSessionProvider>
          <div className="min-h-screen">
            {children}
          </div>
        </AuthSessionProvider>
      </body>
    </html>
  )
}
