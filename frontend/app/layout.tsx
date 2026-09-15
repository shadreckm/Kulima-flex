import './globals.css'
import React from 'react'
import AuthSessionProvider from '../components/AuthSessionProvider'

export const metadata = {
  title: 'Kulima FLEX — Evidence Intelligence',
  description: 'Kulima FLEX: evidence-backed decision intelligence for funds, NGOs, accelerators, and development programs.',
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
