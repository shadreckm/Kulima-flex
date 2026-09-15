import { NextRequest, NextResponse } from 'next/server'
import { SignJWT } from 'jose'
import { getToken } from 'next-auth/jwt'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'
// Raise the body-size limit to 26 MB so files up to 25 MB clear the proxy.
// The default Next.js App Router limit is 4 MB, which caused 413 on large PDFs.
export const maxDuration = 60
export const fetchCache = 'force-no-store'

// Override the Next.js body-size cap for this catch-all API route.
export const config = {
  api: {
    bodyParser: {
      sizeLimit: '26mb',
    },
    responseLimit: false,
  },
}

const BACKEND_API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').replace('http://localhost:8000', 'http://127.0.0.1:8000')

async function proxy(request: NextRequest) {
  const upstreamUrl = new URL(request.nextUrl.pathname + request.nextUrl.search, BACKEND_API_URL)
  const headers = new Headers(request.headers)

  headers.delete('host')
  headers.delete('connection')
  headers.delete('content-length')
  headers.delete('authorization')

  const decodedToken = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET })
  const tokenSub = typeof decodedToken === 'object' && decodedToken && 'sub' in decodedToken ? String((decodedToken as { sub?: unknown }).sub || '') : ''
  const secret = process.env.NEXTAUTH_SECRET

  let backendToken: string | null = null
  if (tokenSub && secret) {
    backendToken = await new SignJWT({})
      .setProtectedHeader({ alg: 'HS256', typ: 'JWT' })
      .setSubject(tokenSub)
      .setIssuedAt()
      .setExpirationTime('1h')
      .sign(new TextEncoder().encode(secret))
  }

  console.info('[kulima-proxy]', {
    path: request.nextUrl.pathname,
    tokenExists: Boolean(decodedToken),
    tokenSub: Boolean(tokenSub),
    authorizationForwarded: Boolean(backendToken),
  })

  if (backendToken) {
    headers.set('authorization', `Bearer ${backendToken}`)
  }

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: 'no-store',
  }

  if (request.method !== 'GET' && request.method !== 'HEAD') {
    init.body = await request.arrayBuffer()
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
