import { api, ApiError } from './api.ts'
import { parseUser } from './backend.ts'

export interface SignInCredentials {
  username: string
  password: string
}

export async function signIn(credentials: SignInCredentials, signal: AbortSignal): Promise<void> {
  const response = await api<unknown>('/auth/login', {
    method: 'POST',
    signal,
    body: JSON.stringify({
      username: credentials.username.trim().toLowerCase(),
      password: credentials.password,
    }),
  })
  parseUser(response)
}

export function signInErrorMessage(error: unknown): string {
  if (error instanceof DOMException && error.name === 'TimeoutError') {
    return 'Sign-in took too long. Please try again.'
  }
  if (error instanceof ApiError) {
    switch (error.status) {
      case 401:
        return 'The username or password is incorrect. Please try again.'
      case 403:
        return 'This account cannot access the workspace. Contact your administrator.'
      case 400:
      case 422:
        return 'Check your username and password, then try again.'
      case 429:
        return 'Too many sign-in attempts. Please wait before trying again.'
      case 404:
      case 405:
      case 501:
        return 'Sign-in is not available right now. Please try again later.'
      case 0:
        return 'We couldn’t connect right now. Please try again in a moment.'
    }
  }
  return 'We couldn’t sign you in. Please try again in a moment.'
}
