import { useState, type FormEvent } from 'react'
import { ShieldCheck } from 'lucide-react'
import { api } from '@/lib/api'

export function Login({ onSuccess }: { onSuccess: () => void }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    setBusy(true)
    setError('')
    try {
      await api('/session', { method: 'POST', body: JSON.stringify({ email: fields.get('email'), password: fields.get('password') }) })
      onSuccess()
    } catch (error) { setError((error as Error).message) }
    finally { setBusy(false) }
  }
  return (
    <main className="flex min-h-dvh items-center justify-center bg-background p-6">
      <form onSubmit={submit} className="w-full max-w-sm space-y-5">
        <ShieldCheck className="size-10 text-primary" aria-hidden="true" />
        <div><h1 className="text-2xl font-semibold">Sign in to Sentinel</h1><p className="mt-2 text-sm text-muted-foreground">Access your cameras and recorded events.</p></div>
        <label className="block text-sm">Email<input name="email" type="email" autoComplete="username" required className="mt-2 block w-full rounded-lg border bg-surface px-3 py-2.5 text-base" /></label>
        <label className="block text-sm">Password<input name="password" type="password" autoComplete="current-password" required className="mt-2 block w-full rounded-lg border bg-surface px-3 py-2.5 text-base" /></label>
        {error && <p role="alert" className="text-sm text-critical">{error}</p>}
        <button disabled={busy} className="w-full rounded-lg bg-primary px-4 py-2.5 font-semibold text-primary-foreground disabled:opacity-50">{busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
    </main>
  )
}
