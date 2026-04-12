/**
 * Thin wrapper around fetch that automatically injects the Authorization header
 * from sessionStorage. Drop-in replacement for fetch('/api/...').
 */
export function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const pw = sessionStorage.getItem('gradYOU8_pw') ?? ''
  const headers = new Headers(init.headers)
  if (pw) headers.set('Authorization', `Bearer ${pw}`)
  return fetch(url, { ...init, headers })
}
