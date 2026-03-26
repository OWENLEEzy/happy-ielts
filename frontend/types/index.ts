export type LessonPhase = 'review' | 'reading' | 'writing' | 'feedback'

export interface UserProfile {
  goal: string
  interests: string[]
  level: number
  bandwidth_minutes: number
  writing_mode: 'professional' | 'ielts_task1' | 'ielts_task2'
}

export interface Article {
  id: number
  date: string
  source_url: string
  original_title: string
  full_text: string
  highlight_indices: number[]
  article_logic: 'compare' | 'cause_effect' | 'argumentation'
  topic_tags: string[]
}

export interface WritingTask {
  id: number
  article_id: number
  mode: 'professional' | 'ielts_task1' | 'ielts_task2'
  instruction: string
  min_words: number
}

export interface ChinglishFlag {
  original: string
  issue: 'word_choice' | 'sentence_structure' | 'logic_connector'
  explanation_zh: string
  native_alternative: string
}

export interface GrammarError {
  original: string
  correction: string
  explanation_zh: string
}

export interface WritingFeedback {
  overall_score: number
  grammar_errors: GrammarError[]
  chinglish_flags: ChinglishFlag[]
  rewrite_suggestions: string[]
}

export interface VocabItem {
  id: number
  word: string
  context_sentence: string
  source: 'reading_click' | 'writing_error'
  next_review: string
  fsrs_state: Record<string, unknown>
  article_id: number | null
}

export type SSEChunk =
  | { type: 'fill_blank'; question: string; word: string }
  | { type: 'word_explanation'; result: string }
  | { type: 'sentence_analysis'; result: string }
  | { type: 'feedback'; result: WritingFeedback }
  | { type: 'writing_task'; instruction: string; min_words: number }
  | {
      type: 'awaiting_action'
      article_full_text: string
      highlight_indices: number[]
      user_level: number
    }
  | { type: 'error'; message: string }
  | { type: 'token'; content: string }

export type LessonAction =
  | { type: 'explain_word'; word: string; context: string }
  | { type: 'analyze_sentence'; sentence: string }
  | { type: 'done_reading' }
  | { type: 'fill_blank_answer'; answer: string; response_seconds: number }
  | { type: 'submit_writing'; text: string }
