import './globals.css'
import React from 'react'
import AuthSessionProvider from '../components/AuthSessionProvider'

export const metadata = {
  title: 'Kulima Frontend Prototype',
  description: 'Chat-first UX prototype for Kulima'
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
