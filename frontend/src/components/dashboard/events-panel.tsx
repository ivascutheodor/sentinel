import { ArrowRight, Bell, PanelRightClose } from 'lucide-react'
import type { Camera, SecurityEvent } from '@/lib/data'
import { cn, formatAgo, formatClock } from '@/lib/utils'
import { EventDetail } from './event-detail'
import { Snapshot } from './snapshot'
import { EventListSkeleton } from './loading'

interface EventsPanelProps {
  cameras: Camera[]
  fullWidth?: boolean
  loading?: boolean
  loadError?: boolean
  canDelete: boolean
  onDeleted: (id: string) => void
  onViewAll: () => void
  open: boolean
  events: SecurityEvent[]
  clock: number
  selectedId: string | null
  onSelect: (id: string | null) => void
  onClose: () => void
}

export function EventsPanel({ cameras, fullWidth, loading, loadError, canDelete, onDeleted, onViewAll, open, events, clock, selectedId, onSelect, onClose }: EventsPanelProps) {
  const selected = selectedId ? events.find(event => event.id === selectedId) : undefined
  return (
    <aside aria-label="Recent events" aria-hidden={!open} aria-busy={Boolean(loading)} inert={!open}
      className={cn('absolute inset-y-0 right-0 z-30 shrink-0 overflow-hidden border-l bg-panel transition-[width] duration-300 ease-out lg:relative lg:z-auto', fullWidth ? 'relative w-full' : open ? 'w-[min(22rem,100%)]' : 'w-0 border-l-0')}>
      <div className="flex h-full w-full flex-col">
        <header className="flex items-center justify-between gap-2 border-b px-4 py-3">
          <div className="flex items-center gap-2"><Bell className="size-4 text-muted-foreground" aria-hidden="true" /><h2 className="text-sm font-semibold">Recent events</h2></div>
          <button type="button" onClick={onClose} aria-label="Collapse events panel" className="flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-surface-hover hover:text-foreground"><PanelRightClose className="size-4" aria-hidden="true" /></button>
        </header>
        {loading || loadError ? <EventListSkeleton loading={Boolean(loading)} /> : selected ? (
          <EventDetail key={selected.id} eventId={selected.id} clock={clock} canDelete={canDelete} onBack={() => onSelect(null)} onDeleted={onDeleted} />
        ) : (
          <ul className="thin-scroll min-h-0 flex-1 divide-y divide-border/60 overflow-y-auto">
            {!events.length && <li className="px-4 py-10 text-center text-sm text-muted-foreground">No recorded events yet.</li>}
            {events.map(event => {
              const camera = cameras.find(camera => camera.id === event.cameraId)
              return <li key={event.id}>
                <button type="button" onClick={() => onSelect(event.id)} className="flex w-full gap-3 px-3 py-4 text-left transition-colors hover:bg-surface">
                  <Snapshot image={event.snapshotUrl} box={event.box} severity={event.severity} className="w-[84px] shrink-0 self-start rounded-md border" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2 text-[10px] text-muted-foreground">
                      <span className="capitalize">{event.captureStatus ?? 'Event'}</span><span className="font-mono">{formatClock(event.ts)}</span>
                    </div>
                    <p className="mt-1.5 truncate text-[13px] font-medium leading-tight">{event.title}</p>
                    <p title={camera?.name ?? event.cameraId} className="mt-1 truncate font-mono text-[11px] text-muted-foreground">{camera?.name ?? event.cameraId}</p>
                    <p className="mt-1 text-[11px] text-muted-foreground">{formatAgo(clock - event.ts)}</p>
                  </div>
                </button>
              </li>
            })}
          </ul>
        )}
        {!loading && !loadError && !fullWidth && <footer className="border-t p-3">
          <button type="button" onClick={onViewAll} className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2.5 text-sm font-semibold text-primary-foreground hover:brightness-110">View all events<ArrowRight className="size-4" aria-hidden="true" /></button>
        </footer>}
      </div>
    </aside>
  )
}
