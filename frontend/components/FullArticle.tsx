'use client'
import { WordChip } from './WordChip'
import type { Article } from '@/types'

interface Props {
  article: Article
  onSentenceClick: (sentence: string) => void
}

function renderParagraph(text: string, isHighlighted: boolean, onSentenceClick: (s: string) => void) {
  const words = text.split(/(\s+)/)
  return (
    <p
      key={text.slice(0, 20)}
      className={`mb-4 leading-relaxed ${isHighlighted ? 'bg-yellow-50 border-l-4 border-yellow-400 pl-3 py-1' : ''}`}
      onDoubleClick={() => onSentenceClick(text)}
      title="双击分析句子"
    >
      {words.map((token, i) =>
        /\s+/.test(token) ? (
          <span key={i}>{token}</span>
        ) : (
          <WordChip key={i} word={token.replace(/[.,!?;:'"()\[\]]/g, '')} context={text} />
        )
      )}
    </p>
  )
}

export function FullArticle({ article, onSentenceClick }: Props) {
  const paragraphs = article.full_text.split('\n\n')

  return (
    <div className="prose max-w-none">
      <h2 className="text-xl font-bold mb-2">{article.original_title}</h2>
      <div className="flex gap-2 mb-4 flex-wrap">
        {article.topic_tags.map(tag => (
          <span key={tag} className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs">{tag}</span>
        ))}
        <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
          {article.article_logic === 'compare' ? '对比分析' :
           article.article_logic === 'cause_effect' ? '因果推导' : '论证立场'}
        </span>
      </div>
      <p className="text-xs text-gray-400 mb-4">双击任意段落可分析句子结构 · 点击单词获取上下文释义</p>
      {paragraphs.map((para, i) =>
        renderParagraph(para, article.highlight_indices.includes(i), onSentenceClick)
      )}
    </div>
  )
}
