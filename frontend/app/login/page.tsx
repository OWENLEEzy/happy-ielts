'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const router = useRouter()
  const [key, setKey] = useState('')
  const [error, setError] = useState('')

  function handleSubmit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault()
    const trimmed = key.trim()
    if (!trimmed) {
      setError('请输入访问密钥')
      return
    }
    // Store api_key cookie for 30 days
    const maxAge = 30 * 24 * 60 * 60
    document.cookie = `api_key=${encodeURIComponent(trimmed)}; path=/; max-age=${maxAge}; SameSite=Lax`
    router.replace('/')
  }

  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'sans-serif',
        background: '#f5f5f5',
      }}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '2.5rem 2rem',
          boxShadow: '0 2px 16px rgba(0,0,0,0.08)',
          width: '100%',
          maxWidth: 360,
        }}
      >
        <h1 style={{ marginBottom: '1.5rem', fontSize: '1.4rem', textAlign: 'center' }}>
          DynamicLingo
        </h1>
        <form onSubmit={handleSubmit}>
          <label
            htmlFor="api-key"
            style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', color: '#555' }}
          >
            访问密钥
          </label>
          <input
            id="api-key"
            type="password"
            value={key}
            onChange={(e) => {
              setKey(e.target.value)
              setError('')
            }}
            placeholder="输入密钥..."
            style={{
              width: '100%',
              padding: '0.6rem 0.75rem',
              fontSize: '1rem',
              border: '1px solid #ddd',
              borderRadius: 8,
              boxSizing: 'border-box',
              marginBottom: '0.75rem',
              outline: 'none',
            }}
            autoFocus
          />
          {error && (
            <p style={{ color: '#e53e3e', fontSize: '0.85rem', marginBottom: '0.5rem' }}>{error}</p>
          )}
          <button
            type="submit"
            style={{
              width: '100%',
              padding: '0.65rem',
              background: '#2563eb',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              fontSize: '1rem',
              cursor: 'pointer',
            }}
          >
            进入
          </button>
        </form>
      </div>
    </main>
  )
}
