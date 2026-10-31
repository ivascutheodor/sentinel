export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}

export function resolveApiOrigin(configured: string | undefined, pageUrl: string): string {
  const url = new URL(configured?.trim() || pageUrl)
  if (!configured?.trim()) url.port = '8000'
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password
    || (configured?.trim() && (url.pathname !== '/' || url.search || url.hash))) {
    throw new Error('VITE_API_ORIGIN must be an HTTP or HTTPS origin, for example http://homie:8000.')
  }
  return url.origin
}

export function apiUrl(path: string): string {
  const pageUrl = typeof window === 'undefined' ? 'http://localhost:5173' : window.location.href
  return `${resolveApiOrigin(import.meta.env?.VITE_API_ORIGIN, pageUrl)}/api/v1${path}`
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  const headers = new Headers(options.headers)
  if (options.body !== undefined && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  try {
    response = await fetch(apiUrl(path), {
      credentials: 'include',
      cache: 'no-store',
      ...options,
      headers,
      signal: options.signal ? AbortSignal.any([options.signal, AbortSignal.timeout(15_000)]) : AbortSignal.timeout(15_000),
    })
  } catch (error) {
    if (options.signal?.aborted) throw error
    throw new ApiError('Cannot reach the API. Check that the Sentinel backend is running.', 0)
  }
  if (response.status === 204 && response.ok) return undefined as T
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body?.detail
    throw new ApiError(typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map((item: { msg: string }) => item.msg).join(' ')
      : 'The API could not complete this request. Check the backend and try again.', response.status)
  }
  if (body === null) throw new ApiError('The server returned an unsupported response.', 502)
  return body as T
}
