import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowRight, CircleAlert, Eye, EyeOff, LoaderCircle, LockKeyhole, UserRound, ShieldCheck } from 'lucide-react'
import { signIn, signInErrorMessage } from '@/lib/auth'
import { cn } from '@/lib/utils'

interface FieldErrors {
  username?: string
  password?: string
}

export function Login({ onSuccess }: { onSuccess: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const usernameInput = useRef<HTMLInputElement>(null)
  const passwordInput = useRef<HTMLInputElement>(null)
  const request = useRef<AbortController | null>(null)

  useEffect(() => () => request.current?.abort(), [])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (request.current) return

    const errors: FieldErrors = {}
    const normalizedUsername = username.trim().toLowerCase()
    if (!normalizedUsername) errors.username = 'Enter your username.'
    else if (!/^[a-z0-9._-]{3,50}$/.test(normalizedUsername)) {
      errors.username = 'Use 3–50 letters, numbers, dots, underscores or hyphens.'
    }
    if (!password.length) errors.password = 'Enter your password.'
    setFieldErrors(errors)
    setError('')
    if (errors.username || errors.password) {
      if (errors.username) usernameInput.current?.focus()
      else passwordInput.current?.focus()
      return
    }

    const controller = new AbortController()
    request.current = controller
    setBusy(true)
    try {
      await signIn({ username: normalizedUsername, password }, AbortSignal.any([
        controller.signal, AbortSignal.timeout(15_000),
      ]))
      if (!controller.signal.aborted) {
        setPassword('')
        onSuccess()
      }
    } catch (error) {
      if (!controller.signal.aborted) setError(signInErrorMessage(error))
    } finally {
      if (!controller.signal.aborted) setBusy(false)
      if (request.current === controller) request.current = null
    }
  }

  const fieldClass = 'block min-h-12 w-full rounded-lg border bg-surface py-3 pl-10 text-base text-foreground placeholder:text-muted-foreground/60 transition-colors hover:border-border-strong disabled:opacity-60'

  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <header className="flex flex-wrap items-center justify-between gap-4 px-6 py-6 sm:px-10">
        <a href="/login" aria-label="Sentinel sign in" className="flex items-center gap-2.5 rounded-md">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ShieldCheck className="size-5" strokeWidth={2.25} aria-hidden="true" />
          </span>
          <span className="text-lg font-semibold tracking-tight">Sentinel</span>
        </a>
      </header>

      <main className="flex flex-1 items-center justify-center px-5 py-10 sm:px-6 sm:py-16">
        <section aria-labelledby="sign-in-heading" className="w-full max-w-[420px] rounded-2xl border bg-panel p-6 sm:p-8">
          <div className="mb-7">
            <h1 id="sign-in-heading" className="text-2xl font-semibold tracking-tight sm:text-[28px]">Sign in to Sentinel</h1>
            <p id="sign-in-description" className="mt-2 text-sm leading-relaxed text-muted-foreground">Your cameras and recorded events, in one workspace.</p>
          </div>

          <form onSubmit={submit} noValidate aria-labelledby="sign-in-heading" aria-describedby="sign-in-description" aria-busy={busy} className="space-y-5">
            <div>
              <label htmlFor="login-username" className="mb-2 block text-sm font-medium">Username</label>
              <div className="relative">
                <UserRound className="pointer-events-none absolute left-3.5 top-4 size-4 text-muted-foreground" aria-hidden="true" />
                <input
                  ref={usernameInput}
                  id="login-username"
                  name="username"
                  type="text"
                  inputMode="text"
                  autoComplete="username"
                  autoCapitalize="none"
                  autoCorrect="off"
                  spellCheck={false}
                  maxLength={50}
                  required
                  disabled={busy}
                  value={username}
                  onChange={event => { setUsername(event.target.value); setFieldErrors(previous => ({ ...previous, username: undefined })); setError('') }}
                  onBlur={() => setUsername(value => value.trim().toLowerCase())}
                  aria-invalid={Boolean(fieldErrors.username)}
                  aria-describedby={fieldErrors.username ? 'login-username-error' : undefined}
                  className={cn(fieldClass, 'pr-3', fieldErrors.username && 'border-critical/70')}
                />
              </div>
              {fieldErrors.username && <p id="login-username-error" className="mt-2 text-xs text-critical">{fieldErrors.username}</p>}
            </div>

            <div>
              <label htmlFor="login-password" className="mb-2 block text-sm font-medium">Password</label>
              <div className="relative">
                <LockKeyhole className="pointer-events-none absolute left-3.5 top-4 size-4 text-muted-foreground" aria-hidden="true" />
                <input
                  ref={passwordInput}
                  id="login-password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  disabled={busy}
                  value={password}
                  onChange={event => { setPassword(event.target.value); setFieldErrors(previous => ({ ...previous, password: undefined })); setError('') }}
                  aria-invalid={Boolean(fieldErrors.password)}
                  aria-describedby={fieldErrors.password ? 'login-password-error' : undefined}
                  className={cn(fieldClass, 'pr-14', fieldErrors.password && 'border-critical/70')}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(value => !value)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                  aria-controls="login-password"
                  disabled={busy}
                  className="absolute right-1 top-1 flex size-10 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground disabled:opacity-50"
                >
                  {showPassword ? <EyeOff className="size-4" aria-hidden="true" /> : <Eye className="size-4" aria-hidden="true" />}
                </button>
              </div>
              {fieldErrors.password && <p id="login-password-error" className="mt-2 text-xs text-critical">{fieldErrors.password}</p>}
            </div>

            {error && <div role="alert" className="flex items-start gap-2.5 rounded-lg border border-critical/25 bg-critical/5 p-3 text-sm leading-relaxed">
              <CircleAlert className="mt-0.5 size-4 shrink-0 text-critical" aria-hidden="true" />
              <p>{error}</p>
            </div>}

            <button type="submit" disabled={busy} className="flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground transition-[filter] hover:brightness-110 disabled:cursor-wait disabled:opacity-60">
              {busy ? <><LoaderCircle className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />Signing in…</>
                : <>Sign in<ArrowRight className="size-4" aria-hidden="true" /></>}
            </button>
          </form>

          <p className="mt-6 border-t pt-5 text-center text-xs leading-relaxed text-muted-foreground">Need an account or a password reset?<br />Contact your administrator.</p>
        </section>
      </main>

      <footer className="px-6 pb-6 text-center text-xs text-muted-foreground">Sentinel · Monitoring workspace</footer>
    </div>
  )
}
