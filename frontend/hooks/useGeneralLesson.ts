'use client'
import { useState, useCallback, useRef } from 'react'

type Phase = 'reading' | 'quiz' | 'free_qa' | 'done'

interface QuizQuestion {
  q: string
  a: string
}

interface QaEntry {
  q: string
  a: string
}

export function useGeneralLesson(projectId: number, lessonId: number) {
  const [phase, setPhase] = useState<Phase>('reading')
  const [studyGuide, setStudyGuide] = useState('')
  const [lessonTitle, setLessonTitle] = useState('')
  const [quiz, setQuiz] = useState<QuizQuestion[]>([])
  const [qaHistory, setQaHistory] = useState<QaEntry[]>([])
  const abortRef = useRef<AbortController | null>(null)

  const start = useCallback(async () => {
    abortRef.current = new AbortController()
    const res = await fetch('/api/learn/lesson/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, lesson_id: lessonId }),
      signal: abortRef.current.signal,
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
          const event = JSON.parse(line.slice(6))
          if (event.type === 'reading') {
            setStudyGuide(event.study_guide ?? '')
            setLessonTitle(event.title ?? '')
            setPhase('reading')
          }
          if (event.type === 'quiz') {
            setQuiz(event.questions ?? [])
            setPhase('quiz')
          }
          if (event.type === 'free_qa') {
            setPhase('free_qa')
          }
          if (event.type === 'free_qa_answer') {
            setQaHistory(event.history ?? [])
          }
        } catch {
          // skip malformed
        }
      }
    }
  }, [projectId, lessonId])

  const sendAction = useCallback(
    async (payload: Record<string, unknown>) => {
      const res = await fetch('/api/learn/lesson/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId, lesson_id: lessonId, ...payload }),
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
            const event = JSON.parse(line.slice(6))
            if (event.type === 'quiz') {
              setQuiz(event.questions ?? [])
              setPhase('quiz')
            }
            if (event.type === 'free_qa') {
              setPhase('free_qa')
            }
            if (event.type === 'free_qa_answer') {
              setQaHistory(event.history ?? [])
            }
            if (event.type === 'done') {
              setPhase('done')
            }
          } catch {
            // skip
          }
        }
      }
    },
    [projectId, lessonId],
  )

  const abort = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return { phase, studyGuide, lessonTitle, quiz, qaHistory, start, sendAction, abort }
}
