import type { NextRequest } from 'next/server'

const BACKEND = process.env.BACKEND_URL ?? 'http://localhost:8000'

export async function GET(_req: NextRequest, { params }: { params: Promise<{ proxy: string[] }> }) {
  const { proxy } = await params
  const path = proxy.join('/')
  return fetch(`${BACKEND}/api/${path}`)
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ proxy: string[] }> }) {
  const { proxy } = await params
  const path = proxy.join('/')
  return fetch(`${BACKEND}/api/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: await req.text(),
  })
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ proxy: string[] }> },
) {
  const { proxy } = await params
  const path = proxy.join('/')
  return fetch(`${BACKEND}/api/${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: await req.text(),
  })
}
