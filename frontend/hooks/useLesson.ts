import useSWR from 'swr'
import type { paths } from '@/types/api'
import type { Article, WritingTask, VocabItem, UserProfile } from '@/types'

// URL is validated against the OpenAPI spec at compile time
const apiFetch = <T>(url: keyof paths) => fetch(url as string).then((r) => r.json() as Promise<T>)

export function useTodayLesson() {
  return useSWR<{ article: Article; task: WritingTask }>(
    '/api/lessons/today' satisfies keyof paths,
    apiFetch<{ article: Article; task: WritingTask }>,
  )
}

export function usePlannerStatus() {
  return useSWR<{ ready: boolean; status: string; error: string | null }>(
    '/api/planner/status' satisfies keyof paths,
    apiFetch<{ ready: boolean; status: string; error: string | null }>,
    { refreshInterval: (data) => (data?.ready || data?.status === 'error' ? 0 : 3000) },
  )
}

export function useOnboardingStatus() {
  return useSWR<{ ready: boolean }>(
    '/api/onboarding/status' satisfies keyof paths,
    apiFetch<{ ready: boolean }>,
    { refreshInterval: (data) => (data?.ready ? 0 : 2000) },
  )
}

export function useVocab() {
  return useSWR<VocabItem[]>('/api/vocab' satisfies keyof paths, apiFetch<VocabItem[]>)
}

export function useProfile() {
  return useSWR<UserProfile>('/api/profile' satisfies keyof paths, apiFetch<UserProfile>)
}
