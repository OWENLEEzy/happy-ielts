import useSWR from 'swr'
import type { Article, WritingTask, VocabItem, UserProfile } from '@/types'

const fetcher = (url: string) => fetch(url).then((r) => r.json())

export function useTodayLesson() {
  return useSWR<{ article: Article; task: WritingTask }>('/api/lesson/today', fetcher)
}

export function usePlannerStatus() {
  return useSWR<{ ready: boolean; status: string; error: string | null }>(
    '/api/planner/status',
    fetcher,
    { refreshInterval: (data) => (data?.ready || data?.status === 'error' ? 0 : 3000) },
  )
}

export function useOnboardingStatus() {
  return useSWR<{ ready: boolean }>('/api/onboarding/status', fetcher, {
    refreshInterval: (data) => (data?.ready ? 0 : 2000),
  })
}

export function useVocab() {
  return useSWR<VocabItem[]>('/api/vocab', fetcher)
}

export function useProfile() {
  return useSWR<UserProfile>('/api/profile', fetcher)
}
