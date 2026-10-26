export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api/v1${path}`, {
      credentials: 'same-origin',
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
      signal: options.signal ?? AbortSignal.timeout(15_000),
    })
  } catch (error) {
    if (options.signal?.aborted) throw error
    throw new ApiError('Cannot reach the API. Check that the Sentinel backend is running.', 0)
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body?.detail
    throw new ApiError(typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map((item: { msg: string }) => item.msg).join(' ')
      : 'The API could not complete this request. Check the backend and try again.', response.status)
  }
  return body as T
}
