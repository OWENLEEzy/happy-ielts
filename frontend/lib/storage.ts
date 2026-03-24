export function subscribeToStorage(cb: () => void): () => void {
  if (typeof window === 'undefined') return () => {}
  window.addEventListener('storage', cb)
  return () => window.removeEventListener('storage', cb)
}
