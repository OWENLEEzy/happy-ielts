import type { NextRequest } from 'next/server'
import { NextResponse } from 'next/server'

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get('authorization')
  if (!process.env.CRON_SECRET || authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return new NextResponse('Unauthorized', { status: 401 })
  }

  const backend = process.env.BACKEND_URL ?? 'http://localhost:8000'
  const res = await fetch(`${backend}/api/planner/jobs`, { method: 'POST' })

  if (!res.ok) {
    return NextResponse.json({ error: 'Planner trigger failed' }, { status: 502 })
  }

  return NextResponse.json({ ok: true, date: new Date().toISOString() })
}
