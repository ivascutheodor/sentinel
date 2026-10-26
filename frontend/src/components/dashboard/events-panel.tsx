'use client'

import { useState } from 'react'
import { ArrowRight, Bell, PanelRightClose } from 'lucide-react'
import { type Camera, type SecurityEvent } from '@/lib/data'
import { cn, formatAgo, formatClock } from '@/lib/utils'
import { EventDetail } from './event-detail'
import { SeverityBadge, SEVERITY_META } from './severity'
import { Snapshot } from './snapshot'

interface EventsPanelProps {
  cameras: Camera[]
  fullWidth?: boolean
  onViewAll: () => void
  open: boolean
  events: SecurityEvent[]
  clock: number
  selectedId: string | null
  onSelect: (id: string | null) => void
  onClose: () => void
  onMarkReviewed: (id: string) => void
  onViewCamera: (cameraId: string) => void
}

export function EventsPanel({
  cameras,
  fullWidth,
  onViewAll,
  open,
  events,
  clock,
  selectedId,
  onSelect,
  onClose,
  onMarkReviewed,
  onViewCamera,
}: EventsPanelProps) {
  const [filter, setFilter] = useState<'all' | 'unreviewed'>('all')
  const unreviewed = events.filter((e) => !e.reviewed).length
  const list = filter === 'all' ? events : events.filter((e) => !e.reviewed)
  const selected = selectedId ? events.find((e) => e.id === selectedId) : undefined

  return (
    <aside
      aria-label="Recent events"
      aria-hidden={!open}
      inert={!open}
      className={cn(
        'absolute inset-y-0 right-0 z-30 shrink-0 overflow-hidden border-l bg-panel transition-[width] duration-300 ease-out lg:relative lg:z-auto',
        fullWidth ? 'relative w-full' : open ? 'w-[min(22rem,100%)]' : 'w-0 border-l-0',
      )}
    >
      <div className={cn("flex h-full flex-col", fullWidth ? "w-full" : "w-[min(22rem,100vw)]")}>
        <header className="flex items-center justify-between gap-2 border-b px-4 py-3">
          <div className="flex items-center gap-2">
            <Bell className="size-4 text-muted-foreground" aria-hidden="true" />
            <h2 className="text-sm font-semibold">Recent events</h2>
            {unreviewed > 0 && (
              <span className="rounded-full bg-primary/15 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                {unreviewed} new
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Collapse events panel"
            className="flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground"
          >
            <PanelRightClose className="size-4" aria-hidden="true" />
          </button>
        </header>

        {selected ? (
          <EventDetail
            event={selected}
            cameras={cameras}
            clock={clock}
            onBack={() => onSelect(null)}
            onMarkReviewed={() => onMarkReviewed(selected.id)}
            onViewCamera={() => onViewCamera(selected.cameraId)}
          />
        ) : (
          <>
            <div className="flex gap-1 border-b px-3 py-2" role="tablist" aria-label="Filter events">
              {(['all', 'unreviewed'] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  role="tab"
                  aria-selected={filter === f}
                  onClick={() => setFilter(f)}
                  className={cn(
                    'rounded-md px-2.5 py-1 text-xs font-medium capitalize transition-colors',
                    filter === f
                      ? 'bg-surface-hover text-foreground'
                      : 'text-muted-foreground hover:text-foreground',
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
            <ul className="thin-scroll min-h-0 flex-1 divide-y divide-border/60 overflow-y-auto">
              {list.length === 0 && (
                <li className="px-4 py-10 text-center text-sm text-muted-foreground">
                  {filter === 'all' ? 'No recorded events yet.' : 'No unreviewed events.'}
                </li>
              )}
              {list.map((event) => {
                const camera = cameras.find((c) => c.id === event.cameraId)
                if (!camera) return null
                const meta = SEVERITY_META[event.severity]
                return (
                  <li key={event.id} className={cn(event.isNew && 'animate-event-in')}>
                    <button
                      type="button"
                      onClick={() => onSelect(event.id)}
                      className="group relative flex w-full gap-3 px-3 py-3 text-left transition-colors hover:bg-surface"
                    >
                      <span
                        className="absolute inset-y-3 left-0 w-0.5 rounded-r"
                        style={{ backgroundColor: meta.color }}
                        aria-hidden="true"
                      />
                      <Snapshot
                        camera={{ ...camera, image: event.snapshotUrl }}
                        box={event.box}
                        severity={event.severity}
                        className={cn(
                          'w-[84px] shrink-0 self-start rounded-md border',
                          event.reviewed && 'opacity-70',
                        )}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <SeverityBadge severity={event.severity} />
                          <span className="flex items-center gap-1.5 font-mono text-[10px] text-muted-foreground">
                            {!event.reviewed && (
                              <span
                                className="size-1.5 rounded-full bg-primary"
                                role="img"
                                aria-label="Unreviewed"
                              />
                            )}
                            {formatClock(event.ts)}
                          </span>
                        </div>
                        <p
                          className={cn(
                            'mt-1.5 truncate text-[13px] font-medium leading-tight',
                            event.reviewed && 'text-foreground/80',
                          )}
                        >
                          {event.title}
                        </p>
                        <p className="mt-0.5 truncate text-xs text-muted-foreground">
                          {camera.name}
                        </p>
                        <p className="mt-0.5 text-[11px] text-muted-foreground/70">
                          {formatAgo(Math.max(0, clock - event.ts))}
                        </p>
                      </div>
                    </button>
                  </li>
                )
              })}
            </ul>
          </>
        )}

        <footer className="border-t p-3">
          <button
            type="button"
            onClick={onViewAll}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2.5 text-sm font-semibold text-primary-foreground transition-[filter] hover:brightness-110"
          >
            View all events
            <ArrowRight className="size-4" aria-hidden="true" />
          </button>
        </footer>
      </div>
    </aside>
  )
}
