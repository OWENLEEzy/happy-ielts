'use client'
import { useState, useCallback, useRef } from 'react'
import type { components } from '@/types/api'

type ActionReq = components['schemas']['GeneralLessonActionRequest']

type Phase = 'reading' | 'quiz' | 'quiz_result' | 'quiz_skipped' | 'free_qa' | 'done'

export interface AnswerOption {
  index: number
  text: string
  is_correct: boolean
  rationale: string
}

export interface QuizQuestion {
  question: string
  hint: string
  answerOptions: { text: string; isCorrect: boolean; rationale?: string }[]
}

export interface QuizDetail {
  question: string
  hint: string
  student_answer_index: number | null
  correct_answer_index: number | null
  is_correct: boolean
  options: AnswerOption[]
}

export interface QuizResult {
  score: number
  total: number
  details: QuizDetail[]
}

export interface RetryHintItem {
  question: string
  correct_answer: string
}

interface QaEntry {
  id: string
  q: string
  a: string
}

export function useGeneralLesson(projectId: number, lessonId: number) {
  const [phase, setPhase] = useState<Phase>('reading')
  const [studyGuide, setStudyGuide] = useState('')
  const [lessonTitle, setLessonTitle] = useState('')
  const [retryHint, setRetryHint] = useState<RetryHintItem[]>([])
  const [quiz, setQuiz] = useState<QuizQuestion[]>([])
  const [quizResult, setQuizResult] = useState<QuizResult | null>(null)
  const [qaHistory, setQaHistory] = useState<QaEntry[]>([])
  const abortRef = useRef<AbortController | null>(null)

  const _processEvent = useCallback((event: Record<string, unknown>) => {
    if (event.type === 'reading') {
      setStudyGuide((event.study_guide as string) ?? '')
      setLessonTitle((event.title as string) ?? '')
      setRetryHint((event.retry_hint as RetryHintItem[]) ?? [])
      setPhase('reading')
    }
    if (event.type === 'quiz') {
      setQuiz((event.questions as QuizQuestion[]) ?? [])
      setQuizResult(null)
      setPhase('quiz')
    }
    if (event.type === 'quiz_result') {
      setQuizResult({
        score: event.score as number,
        total: event.total as number,
        details: (event.details as QuizDetail[]) ?? [],
      })
      setPhase('quiz_result')
    }
    if (event.type === 'quiz_skipped') {
      setPhase('quiz_skipped')
    }
    if (event.type === 'free_qa') {
      setPhase('free_qa')
    }
    if (event.type === 'free_qa_answer') {
      setQaHistory(
        ((event.history as { q: string; a: string }[]) ?? []).map((e, i) => ({
          id: `qa-${i}`,
          q: e.q,
          a: e.a,
        })),
      )
    }
    if (event.type === 'done') {
      setPhase('done')
    }
  }, [])

  const start = useCallback(async () => {
    abortRef.current = new AbortController()
    const res = await fetch(`/api/learn/projects/${projectId}/lessons/${lessonId}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
      signal: abortRef.current.signal,
    })
    if (!res.body) return
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const text = decoder.decode(value, { stream: true })
      for (const line of text.split('\n')) {
        if (!line.startsWith('data: ') || line.includes('[DONE]')) continue
        try {
          _processEvent(JSON.parse(line.slice(6)))
        } catch {
          // skip malformed
        }
      }
    }
  }, [projectId, lessonId, _processEvent])

  const sendAction = useCallback(
    async (payload: Record<string, unknown>) => {
      const body = { ...(payload as Partial<ActionReq>) } as ActionReq
      const res = await fetch(`/api/learn/projects/${projectId}/lessons/${lessonId}/actions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: abortRef.current?.signal,
      })
      if (!res.body) return
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const text = decoder.decode(value)
        for (const line of text.split('\n')) {
          if (!line.startsWith('data: ') || line.includes('[DONE]')) continue
          try {
            _processEvent(JSON.parse(line.slice(6)))
          } catch {
            // skip
          }
        }
      }
    },
    [projectId, lessonId, _processEvent],
  )

  const abort = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return {
    phase,
    studyGuide,
    lessonTitle,
    retryHint,
    quiz,
    quizResult,
    qaHistory,
    start,
    sendAction,
    abort,
  }
}
