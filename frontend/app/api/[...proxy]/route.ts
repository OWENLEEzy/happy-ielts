import { cookies } from 'next/headers'
import type { NextRequest } from 'next/server'

const BACKEND = process.env.BACKEND_URL ?? 'http://localhost:8000'

async function getApiKeyHeader(): Promise<Record<string, string>> {
  const cookieStore = await cookies()
  const apiKey = cookieStore.get('api_key')?.value
  return apiKey ? { 'X-API-Key': apiKey } : {}
}

export async function GET(_req: NextRequest, { params }: { params: Promise<{ proxy: string[] }> }) {
  const { proxy } = await params
  const path = proxy.join('/')
  const apiKeyHeader = await getApiKeyHeader()
  return fetch(`${BACKEND}/api/${path}`, { headers: apiKeyHeader })
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ proxy: string[] }> }) {
  const { proxy } = await params
  const path = proxy.join('/')
  const apiKeyHeader = await getApiKeyHeader()
  return fetch(`${BACKEND}/api/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...apiKeyHeader },
    body: await req.text(),
  })
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ proxy: string[] }> },
) {
  const { proxy } = await params
  const path = proxy.join('/')
  const apiKeyHeader = await getApiKeyHeader()
  return fetch(`${BACKEND}/api/${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...apiKeyHeader },
    body: await req.text(),
  })
}
