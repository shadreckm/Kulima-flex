import { NextRequest, NextResponse } from 'next/server'
import { SignJWT } from 'jose'
import { getToken } from 'next-auth/jwt'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'
export const maxDuration = 60
export const fetchCache = 'force-no-store'

// 25 MB file + multipart overhead. Next.js 13.5 App Router has no next.config
// `api.bodyParser.sizeLimit`; enforce the limit in this route handler instead.
const MAX_REQUEST_BYTES = 26 * 1024 * 1024

const BACKEND_API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').replace('http://localhost:8000', 'http://127.0.0.1:8000')

async function proxy(request: NextRequest) {
  const upstreamUrl = new URL(request.nextUrl.pathname + request.nextUrl.search, BACKEND_API_URL)

  const declaredLength = Number(request.headers.get('content-length') || 0)
  if (declaredLength > MAX_REQUEST_BYTES) {
    return NextResponse.json({ error: true, message: 'Request exceeds the 25 MB upload limit' }, { status: 413 })
  }

  const headers = new Headers(request.headers)

  headers.delete('host')
  headers.delete('connection')
  headers.delete('content-length')
  headers.delete('authorization')

  const secret = process.env.NEXTAUTH_SECRET
  if (!secret) {
    // Fail loudly: a missing server-side secret would otherwise surface as a
    // generic upstream 401 with no way to diagnose it from the client.
    console.error('[kulima-proxy] NEXTAUTH_SECRET is not set on the server — cannot mint backend token')
    return NextResponse.json(
      { error: true, code: 'FRONTEND_SECRET_MISSING', message: 'Server authentication is not configured (NEXTAUTH_SECRET missing on the deployment). Contact support.' },
      { status: 401 },
    )
  }

  // Explicitly try the __Secure- prefixed cookie name first (always used on
  // HTTPS deployments like Vercel), then fall back to the unprefixed name so
  // local HTTP development still works. getToken() normally infers this from
  // the request protocol, but behind some proxies it sees HTTP and misses the
  // __Secure- cookie entirely — one cause of phantom 401s in production.
  let decodedToken = await getToken({ req: request, secret, cookieName: '__Secure-next-auth.session-token' })
  if (!decodedToken) {
    decodedToken = await getToken({ req: request, secret, cookieName: 'next-auth.session-token' })
  }
  const tokenSub = typeof decodedToken === 'object' && decodedToken && 'sub' in decodedToken ? String((decodedToken as { sub?: unknown }).sub || '') : ''

  if (!decodedToken || !tokenSub) {
    // No valid NextAuth session cookie on this request.
    console.warn('[kulima-proxy] request without valid NextAuth session token', {
      path: request.nextUrl.pathname,
      hasCookieHeader: Boolean(request.headers.get('cookie')),
    })
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

  console.info('[kulima-proxy]', {
    path: request.nextUrl.pathname,
    tokenSub: Boolean(tokenSub),
    authorizationForwarded: true,
  })

  headers.set('authorization', `Bearer ${backendToken}`)

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: 'no-store',
  }

  if (request.method !== 'GET' && request.method !== 'HEAD') {
    init.body = await request.arrayBuffer()
    if (init.body.byteLength > MAX_REQUEST_BYTES) {
      return NextResponse.json({ error: true, message: 'Request exceeds the 25 MB upload limit' }, { status: 413 })
    }
  }

  const upstreamResponse = await fetch(upstreamUrl, init)
  const responseHeaders = new Headers(upstreamResponse.headers)
  responseHeaders.delete('content-encoding')
  responseHeaders.delete('transfer-encoding')
  responseHeaders.delete('connection')

  const contentType = responseHeaders.get('content-type') || ''
  const contentDisposition = responseHeaders.get('content-disposition') || ''
  const isEventStream = contentType.includes('text/event-stream')
  const isFileDownload =
    contentType.includes('application/pdf') ||
    contentType.includes('text/plain') ||
    contentType.includes('application/octet-stream') ||
    contentDisposition.toLowerCase().includes('attachment')
  const isEmptyBody = upstreamResponse.status === 204 || upstreamResponse.body === null

  if (isEventStream || isFileDownload || isEmptyBody) {
    return new NextResponse(upstreamResponse.body, {
      status: upstreamResponse.status,
      headers: responseHeaders,
    })
  }

  const bodyText = await upstreamResponse.text()

  if (contentType.includes('application/json')) {
    responseHeaders.delete('content-length')
    return new NextResponse(bodyText, {
      status: upstreamResponse.status,
      headers: responseHeaders,
    })
  }

  const payload = {
    error: upstreamResponse.status >= 400,
    status: upstreamResponse.status,
    message: bodyText || upstreamResponse.statusText || 'Upstream response was not JSON',
  }

  responseHeaders.delete('content-type')
  responseHeaders.delete('content-length')

  return NextResponse.json(payload, {
    status: upstreamResponse.status,
    headers: responseHeaders,
  })
}

export async function GET(request: NextRequest) {
  return proxy(request)
}

export async function POST(request: NextRequest) {
  return proxy(request)
}

export async function PUT(request: NextRequest) {
  return proxy(request)
}

export async function PATCH(request: NextRequest) {
  return proxy(request)
}

export async function DELETE(request: NextRequest) {
  return proxy(request)
}

export async function OPTIONS(request: NextRequest) {
  return proxy(request)
}
