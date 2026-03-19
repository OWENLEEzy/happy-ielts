'use client'
import type { WritingFeedback } from '@/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface Props {
  feedback: WritingFeedback
}

export function FeedbackView({ feedback }: Props) {
  const scoreColor =
    feedback.overall_score >= 8 ? 'text-green-600' :
    feedback.overall_score >= 5 ? 'text-yellow-600' : 'text-red-600'

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <div className="text-center">
        <span className={`text-5xl font-bold ${scoreColor}`}>{feedback.overall_score}</span>
        <span className="text-gray-400 text-xl">/10</span>
      </div>

      {feedback.grammar_errors.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">语法问题</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {feedback.grammar_errors.slice(0, 2).map((err, i) => (
              <div key={i} className="border-l-4 border-red-300 pl-3">
                <p className="line-through text-gray-400 text-sm">{err.original}</p>
                <p className="text-green-700 text-sm font-medium">{err.correction}</p>
                <p className="text-xs text-gray-500">{err.explanation_zh}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {feedback.chinglish_flags.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Chinglish 识别</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {feedback.chinglish_flags.slice(0, 2).map((flag, i) => (
              <div key={i} className="border-l-4 border-orange-300 pl-3">
                <p className="text-gray-400 text-sm">{flag.original}</p>
                <p className="text-blue-700 text-sm font-medium">→ {flag.native_alternative}</p>
                <p className="text-xs text-gray-500">{flag.explanation_zh}</p>
                <Badge variant="outline" className="text-xs mt-1">{flag.issue}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {feedback.rewrite_suggestions.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">重写建议</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {feedback.rewrite_suggestions.map((suggestion, i) => (
              <div key={i} className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-400 mb-1">版本 {i + 1}</p>
                <p className="text-sm leading-relaxed">{suggestion}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
