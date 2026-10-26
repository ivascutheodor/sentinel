import { useState, type FormEvent } from 'react'
import { api } from '@/lib/api'
import type { Camera } from '@/lib/data'

export function CameraSettings({ cameras, onChange }: { cameras: Camera[]; onChange: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    setBusy(true); setError('')
    try {
      await api('/cameras', { method: 'POST', body: JSON.stringify({ name: data.get('name'), location: data.get('location'), stream_url: data.get('stream_url'), credentials_ref: data.get('credentials_ref') || null }) })
      form.reset(); onChange()
    } catch (error) { setError((error as Error).message) }
    finally { setBusy(false) }
  }
  async function toggle(camera: Camera) {
    setBusy(true); setError('')
    try {
      await api(`/cameras/${encodeURIComponent(camera.id)}`, { method: 'PATCH', body: JSON.stringify({ enabled: !camera.enabled }) })
      onChange()
    } catch (error) { setError((error as Error).message) }
    finally { setBusy(false) }
  }
  const field = 'mt-1.5 block w-full rounded-lg border bg-surface px-3 py-2 text-base'
  return (
    <section aria-label="Camera configuration" className="thin-scroll min-w-0 flex-1 overflow-auto p-4 sm:p-6">
      <h2 className="text-xl font-semibold">Cameras</h2>
      <p className="mt-2 text-sm text-muted-foreground">Connect a camera using its RTSP address. Changes are saved on the server.</p>
      {error && <p role="alert" className="mt-4 text-sm text-critical">{error}</p>}
      <ul className="mt-6 divide-y border-y">
        {cameras.map(camera => <li key={camera.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
          <div className="min-w-0"><h3 className="break-words font-medium">{camera.name}</h3><p className="text-sm text-muted-foreground">{camera.location || 'No location set'}</p><p className="mt-1 break-all font-mono text-xs text-muted-foreground">{camera.id}</p></div>
          <button disabled={busy} onClick={() => toggle(camera)} className="rounded-lg border bg-surface px-3 py-2 text-sm hover:bg-surface-hover disabled:opacity-50">{camera.enabled ? 'Disable monitoring' : 'Enable monitoring'}</button>
        </li>)}
        {!cameras.length && <li className="py-5 text-sm text-muted-foreground">No cameras configured. Add your first camera below.</li>}
      </ul>
      <form onSubmit={add} className="mt-8 max-w-xl space-y-4">
        <h3 className="text-base font-semibold">Add camera</h3>
        <label className="block text-sm">Name<input name="name" required maxLength={200} className={field} /></label>
        <label className="block text-sm">Location<input name="location" maxLength={500} className={field} /></label>
        <label className="block text-sm">RTSP address<input name="stream_url" required placeholder="rtsp://192.168.1.100:554/stream" maxLength={2048} className={field} aria-describedby="rtsp-help" /></label>
        <p id="rtsp-help" className="text-xs text-muted-foreground">Use the camera’s network address. Keep passwords out of this URL.</p>
        <label className="block text-sm">Saved credentials name (optional)<input name="credentials_ref" pattern="[a-z][a-z0-9_]{0,63}" className={field} aria-describedby="credentials-help" /></label>
        <p id="credentials-help" className="text-xs text-muted-foreground">For cameras requiring a password, use the credentials name configured by your installation administrator.</p>
        <button disabled={busy} className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50">{busy ? 'Saving…' : 'Add camera'}</button>
      </form>
    </section>
  )
}
