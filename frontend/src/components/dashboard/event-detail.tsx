import { ArrowLeft, CheckCircle2, Video } from 'lucide-react'
import { type Camera, type SecurityEvent } from '@/lib/data'
import { formatAgo, formatClock } from '@/lib/utils'
import { SeverityBadge } from './severity'
import { Snapshot } from './snapshot'

interface EventDetailProps {
  cameras: Camera[]
  event: SecurityEvent
  clock: number
  onBack: () => void
  onMarkReviewed: () => void
  onViewCamera: () => void
}

export function EventDetail({ cameras, event, clock, onBack, onMarkReviewed, onViewCamera }: EventDetailProps) {
  const camera = cameras.find((c) => c.id === event.cameraId)!
  const canViewLive = camera.status === 'connected'

  const rows: [string, string][] = [
    ['Camera', `${camera.name} (${camera.id})`],
    ['Location', camera.location],
    ['Detected', `${new Date(event.ts * 1000).toLocaleDateString()}, ${formatClock(event.ts)}`],
    ['Zone', event.zoneName ?? 'Outside monitored zones'],

  ]
  if (event.confidence != null) rows.push(['Confidence', `${Math.round(event.confidence * 100)}%`])
  if (event.captureStatus) rows.push(['Capture status', event.captureStatus])
  if (event.dwell) rows.push(['Dwell time', event.dwell])

  return (
    <div className="thin-scroll flex min-h-0 flex-1 flex-col overflow-y-auto">
      <div className="px-3 pt-3">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1.5 rounded-md px-1.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" aria-hidden="true" />
          All events
        </button>
      </div>

      <div className="space-y-4 p-4">
        <Snapshot
          camera={{ ...camera, image: event.snapshotUrl }}
          box={event.box}
          severity={event.severity}
          aspect={0.5625}
          zoom={4.2}
          showBox
          className="w-full rounded-lg border"
        />

        <div>
          <div className="flex items-center justify-between gap-2">
            <SeverityBadge severity={event.severity} />
            <span className="font-mono text-[11px] text-muted-foreground">{event.id}</span>
          </div>
          <h3 className="mt-2 text-base font-semibold leading-snug text-balance">{event.title}</h3>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{event.description}</p>
          <p className="mt-1 text-xs text-muted-foreground/70">
            {formatAgo(Math.max(0, clock - event.ts))}
          </p>
        </div>

        <dl className="divide-y divide-border/60 rounded-lg border bg-surface/60 text-sm">
          {rows.map(([label, value]) => (
            <div key={label} className="flex items-baseline justify-between gap-4 px-3 py-2">
              <dt className="shrink-0 text-xs text-muted-foreground">{label}</dt>
              <dd className="min-w-0 text-right text-[13px] font-medium">{value}</dd>
            </div>
          ))}
        </dl>

        {event.clips.map(clip => <div key={clip.id}>
          {clip.url ? <video controls preload="metadata" src={clip.url} className="w-full rounded-lg bg-black" aria-label="Event recording" />
            : <p className="text-sm text-muted-foreground">Recording {clip.status === 'ready' ? 'expired' : clip.status}.</p>}
        </div>)}
        {!event.clips.length && <p className="text-sm text-muted-foreground">No recording is available for this event.</p>}
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={onViewCamera}
            disabled={!canViewLive}
            className="flex items-center justify-center gap-2 rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm font-medium transition-colors hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Video className="size-4" aria-hidden="true" />
            {canViewLive ? 'View live feed' : 'Camera offline'}
          </button>
          <button
            type="button"
            onClick={onMarkReviewed}
            disabled={event.reviewed}
            className="flex items-center justify-center gap-2 rounded-lg border border-primary/40 bg-primary/10 px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-default disabled:border-border disabled:bg-transparent disabled:text-muted-foreground disabled:hover:bg-transparent"
          >
            <CheckCircle2 className="size-4" aria-hidden="true" />
            {event.reviewed ? 'Reviewed' : 'Mark as reviewed'}
          </button>
        </div>
      </div>
    </div>
  )
}
