/**
 * Catch-all proxy route.
 * Forwards GET/POST requests to the FastAPI backend, injecting the API key
 * server-side so it is never exposed to the browser.
 */
import { NextRequest, NextResponse } from 'next/server'

const BACKEND = process.env.BACKEND_URL ?? 'http://localhost:8000'
const API_KEY = process.env.API_SECRET ?? ''

async function proxy(req: NextRequest, path: string[]): Promise<NextResponse> {
  const endpoint = path.join('/')
  const search   = req.nextUrl.search
  const url      = `${BACKEND}/${endpoint}${search}`

  const headers: Record<string, string> = { 'X-API-Key': API_KEY }
  if (req.method === 'POST') headers['Content-Type'] = 'application/json'

  const body = req.method === 'POST' ? req.body : undefined

  const upstream = await fetch(url, {
    method:  req.method,
    headers,
    body,
    // @ts-expect-error — Node 18 fetch supports duplex
    duplex: 'half',
  })

  const data = await upstream.json()
  return NextResponse.json(data, { status: upstream.status })
}

export async function GET(
  req: NextRequest,
  { params }: { params: { path: string[] } },
) {
  return proxy(req, params.path)
}

export async function POST(
  req: NextRequest,
  { params }: { params: { path: string[] } },
) {
  return proxy(req, params.path)
}
