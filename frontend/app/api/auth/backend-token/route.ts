import { NextRequest, NextResponse } from 'next/server'
import { SignJWT } from 'jose'
import { getToken } from 'next-auth/jwt'
import { createHash } from 'node:crypto'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

/**
 * Mint a short-lived backend JWT for DIRECT browser→backend requests
 * (large-file uploads that bypass the /api/v1 proxy). The backend validates
 * this token with the shared NEXTAUTH_SECRET — the exact same validation the
 * proxied path receives, so both paths carry identical auth context.
 */
export async function GET(request: NextRequest) {
  const secret = process.env.NEXTAUTH_SECRET
  if (!secret) {
    return NextResponse.json(
      { error: true, code: 'FRONTEND_SECRET_MISSING', message: 'Server authentication is not configured (NEXTAUTH_SECRET missing on the deployment).' },
      { status: 401 },
    )
  }

  let decodedToken = await getToken({ req: request, secret, cookieName: '__Secure-next-auth.session-token' })
  if (!decodedToken) {
    decodedToken = await getToken({ req: request, secret, cookieName: 'next-auth.session-token' })
  }
  const tokenSub = typeof decodedToken === 'object' && decodedToken && 'sub' in decodedToken
    ? String((decodedToken as { sub?: unknown }).sub || '')
    : ''

  if (!decodedToken || !tokenSub) {
    return NextResponse.json(
      { error: true, code: 'SESSION_MISSING', message: 'Your session has expired. Please sign in again.' },
      { status: 401 },
    )
  }

  const backendToken = await new SignJWT({})
    .setProtectedHeader({ alg: 'HS256', typ: 'JWT' })
    .setSubject(tokenSub)
    .setIssuedAt()
    .setExpirationTime('1h')
    .sign(new TextEncoder().encode(secret))

  return NextResponse.json({
    token: backendToken,
    // Same fingerprint the proxy sends, so the backend's secret-mismatch
    // diagnostic behaves identically on both paths.
    fingerprint: createHash('sha256').update(secret, 'utf8').digest('hex').slice(0, 16),
    expiresIn: 3600,
  })
}
