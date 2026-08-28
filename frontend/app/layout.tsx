import './globals.css'
import React from 'react'
import AuthSessionProvider from '../components/AuthSessionProvider'

export const metadata = {
  title: 'Kulima OS — Decision Intelligence',
  description: 'Kulima OS: evidence-backed investment decision intelligence for funds, NGOs, accelerators, and development finance programs.',
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
