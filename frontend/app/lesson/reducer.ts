import type { LessonPhase, WritingFeedback } from '@/types'

export interface LessonState {
  phase: LessonPhase
  popover: { word: string; explanation: string } | null
  drawer: { sentence: string; analysis: string } | null
  feedback: WritingFeedback | null
  isStreaming: boolean
  fillBlank: { question: string; word: string } | null
}

export type LessonAction =
  | { type: 'FILL_BLANK_RECEIVED'; question: string; word: string }
  | { type: 'REVIEW_DONE' }
  | { type: 'AWAITING_READING' }
  | { type: 'WORD_CLICK'; word: string }
  | { type: 'WORD_EXPLAINED'; word: string; explanation: string }
  | { type: 'POPOVER_CLOSE' }
  | { type: 'SENTENCE_CLICK'; sentence: string }
  | { type: 'SENTENCE_ANALYZED'; analysis: string }
  | { type: 'READING_DONE' }
  | { type: 'WRITING_TASK_RECEIVED' }
  | { type: 'WRITING_STREAM_START' }
  | { type: 'FEEDBACK_DONE'; feedback: WritingFeedback }

export const initialState: LessonState = {
  phase: 'review',
  popover: null,
  drawer: null,
  feedback: null,
  isStreaming: false,
  fillBlank: null,
}

export function lessonReducer(state: LessonState, action: LessonAction): LessonState {
  switch (action.type) {
    case 'FILL_BLANK_RECEIVED':
      return { ...state, phase: 'review', fillBlank: { question: action.question, word: action.word } }
    case 'REVIEW_DONE':
      return { ...state, fillBlank: null }
    case 'AWAITING_READING':
      return { ...state, phase: 'reading' }
    case 'WORD_CLICK':
      return { ...state, isStreaming: true }
    case 'WORD_EXPLAINED':
      return { ...state, isStreaming: false, popover: { word: action.word, explanation: action.explanation } }
    case 'POPOVER_CLOSE':
      return { ...state, popover: null }
    case 'SENTENCE_CLICK':
      return { ...state, isStreaming: true, drawer: { sentence: action.sentence, analysis: '' } }
    case 'SENTENCE_ANALYZED':
      return { ...state, isStreaming: false, drawer: state.drawer ? { ...state.drawer, analysis: action.analysis } : null }
    case 'READING_DONE':
      return { ...state, phase: 'writing', drawer: null, popover: null }
    case 'WRITING_TASK_RECEIVED':
      return { ...state, phase: 'writing' }
    case 'WRITING_STREAM_START':
      return { ...state, isStreaming: true }
    case 'FEEDBACK_DONE':
      return { ...state, phase: 'feedback', isStreaming: false, feedback: action.feedback }
    default:
      return state
  }
}
