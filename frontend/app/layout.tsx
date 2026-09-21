import './globals.css'
import React from 'react'
import AuthSessionProvider from '../components/AuthSessionProvider'

export const metadata = {
  title: 'Kulima OS — Decision Intelligence',
  description: 'Kulima OS: evidence-backed decision intelligence for funds, NGOs, accelerators, and development programs.',
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
