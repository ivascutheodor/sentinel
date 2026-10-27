import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, LoaderCircle, Trash2 } from 'lucide-react'
import type { SecurityEvent } from '@/lib/data'
import { ApiError } from '@/lib/api'
import { deleteEvent, getEvent } from '@/lib/backend'
import { formatAgo, formatClock } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'
import { Snapshot } from './snapshot'
import { RecordingPlayer } from './recording-player'

const recordingMessages: Record<string, string> = {
  pending: 'This recording is being prepared.',
  failed: 'This recording could not be processed.',
  deleting: 'This recording is being removed.',
  deleted: 'This recording has been removed.',
  expired: 'This recording has expired.',
  unavailable: 'This recording is not available.',
}

interface EventDetailProps {
  eventId: string
  clock: number
  canDelete: boolean
  onBack: () => void
  onDeleted: (id: string) => void
}

export function EventDetail({ eventId, clock, canDelete, onBack, onDeleted }: EventDetailProps) {
  const [event, setEvent] = useState<SecurityEvent | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [loadError, setLoadError] = useState('')
  const [revision, setRevision] = useState(0)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const deletion = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function load() {
      try {
        const result = await getEvent(eventId, controller.signal)
        if (!controller.signal.aborted) { setEvent(result); setLoadError('') }
      } catch (error) {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.status === 401) window.dispatchEvent(new Event('sentinel-session-ended'))
        else {
          if (error instanceof ApiError && error.status === 404) setEvent(null)
          setLoadError(error instanceof ApiError && error.status === 404 ? 'This event is no longer available.' : 'Event details could not be loaded. Please try again.')
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
          timer = setTimeout(load, 5000)
        }
      }
    }
    void load()
    return () => { controller.abort(); clearTimeout(timer); deletion.current?.abort() }
  }, [eventId, revision])

  async function remove() {
    if (deletion.current) return
    const controller = new AbortController()
    deletion.current = controller
    setDeleting(true); setError('')
    try {
      await deleteEvent(eventId, controller.signal)
      if (!controller.signal.aborted) onDeleted(eventId)
    } catch (error) {
      if (controller.signal.aborted) return
      if (error instanceof ApiError && error.status === 401) window.dispatchEvent(new Event('sentinel-session-ended'))
      else setError(error instanceof ApiError && error.status === 409 ? 'This event still has related records and cannot be deleted.' : 'This event could not be deleted. Please try again.')
    } finally {
      if (!controller.signal.aborted) setDeleting(false)
      if (deletion.current === controller) deletion.current = null
    }
  }

  const rows: [string, string][] = event ? [
    ['Camera ID', event.cameraId],
    [event.timestampLabel, `${new Date(event.ts * 1000).toLocaleDateString()}, ${formatClock(event.ts)}`],
  ] : []
  if (event?.captureStatus) rows.push(['Capture status', event.captureStatus])
  if (event?.closedAt !== undefined) rows.push(['Ended', `${new Date(event.closedAt * 1000).toLocaleDateString()}, ${formatClock(event.closedAt)}`])
  if (event?.endReason) rows.push(['End reason', event.endReason.replaceAll('_', ' ')])

  return <div className="thin-scroll min-h-0 flex-1 overflow-y-auto">
    <div className="px-3 pt-3"><button type="button" onClick={onBack} className="flex items-center gap-1.5 rounded-md px-1.5 py-1 text-xs font-medium text-muted-foreground hover:bg-surface-hover hover:text-foreground"><ArrowLeft className="size-3.5" aria-hidden="true" />All events</button></div>
    {loading ? <div aria-busy="true" className="space-y-4 p-4"><p role="status" className="sr-only">Loading event details…</p><Skeleton className="aspect-video w-full" /><Skeleton className="h-5 w-2/3" /><Skeleton className="h-3 w-full" /><Skeleton className="h-24 w-full" /></div> : <div className="space-y-5 p-4">
      {(loadError || error) && <div role="alert" className="space-y-3 text-sm text-muted-foreground"><p>{loadError || error}</p>{!event && <button onClick={() => { setLoading(true); setLoadError(''); setRevision(value => value + 1) }} className="rounded-lg border bg-surface px-3 py-2 hover:bg-surface-hover">Retry event details</button>}</div>}
      {event && <>
        <div><h3 className="text-lg font-semibold">{event.title}</h3><p className="mt-2 text-sm leading-relaxed text-muted-foreground">{event.description}</p><p className="mt-1 text-xs text-muted-foreground">{formatAgo(clock - event.ts)}</p></div>
        <p className="break-all font-mono text-[11px] text-muted-foreground">{event.id}</p>
        {event.snapshotUrl && <Snapshot image={event.snapshotUrl} box={event.box} severity={event.severity} aspect={0.5625} className="w-full rounded-lg border" />}
        <dl className="divide-y divide-border/60 rounded-lg border bg-surface/60">
          {rows.map(([label, value]) => <div key={label} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-3 py-2"><dt className="text-xs text-muted-foreground">{label}</dt><dd className="min-w-0 break-all text-right text-[13px] font-medium">{value}</dd></div>)}
        </dl>
        {event.clips.map(clip => <div key={clip.id} className="space-y-2">
          <h4 className="text-sm font-medium">Recording{event.clips.length > 1 && clip.partNumber ? ` ${clip.partNumber}` : ''}</h4>
          {clip.url ? <RecordingPlayer url={clip.url} /> : <p className="text-sm text-muted-foreground">{recordingMessages[clip.status] ?? 'This recording is not available.'}</p>}
        </div>)}
        {!event.clips.length && <p className="text-sm text-muted-foreground">No recording is available for this event.</p>}
        {canDelete && <div className="border-t pt-4">
          {confirmDelete ? <div role="group" aria-label="Confirm event deletion" className="space-y-3">
            <p className="text-sm font-medium">Delete this event?</p><p className="text-xs leading-relaxed text-muted-foreground">This removes the event from history. Saved video files are not deleted.</p>
            <div className="flex flex-wrap gap-2"><button onClick={remove} disabled={deleting} className="flex min-h-10 items-center justify-center gap-2 rounded-lg bg-critical px-3 py-2 text-sm font-medium text-background disabled:opacity-50">{deleting && <LoaderCircle className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />}{deleting ? 'Deleting…' : 'Delete event'}</button><button disabled={deleting} onClick={() => setConfirmDelete(false)} className="rounded-lg border px-3 py-2 text-sm hover:bg-surface-hover disabled:opacity-50">Cancel</button></div>
          </div> : <button onClick={() => setConfirmDelete(true)} className="flex min-h-10 items-center gap-2 rounded-lg px-2 py-2 text-sm text-critical hover:bg-critical/10"><Trash2 className="size-4" aria-hidden="true" />Delete event</button>}
        </div>}
      </>}
    </div>}
  </div>
}
