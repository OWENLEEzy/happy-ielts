import { redirect } from 'next/navigation'

async function getOnboardingStatus() {
  try {
    const res = await fetch('http://localhost:8000/api/onboarding/status', { cache: 'no-store' })
    return res.json()
  } catch {
    return { ready: false }
  }
}

async function getPlannerStatus() {
  try {
    const res = await fetch('http://localhost:8000/api/planner/status', { cache: 'no-store' })
    return res.json()
  } catch {
    return { ready: false }
  }
}

export default async function HomePage() {
  const [onboarding, planner] = await Promise.all([
    getOnboardingStatus(),
    getPlannerStatus(),
  ])

  if (!onboarding.ready) redirect('/onboarding')
  if (!planner.ready) redirect('/lesson?loading=true')
  redirect('/lesson')
}
