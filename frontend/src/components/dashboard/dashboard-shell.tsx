import { useCallback, useEffect, useState } from 'react'
import { VideoOff, X } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { DashboardData } from '@/lib/data'
import { CameraWorkspace } from './camera-workspace'
import { CameraSettings } from './camera-settings'
import { EventsPanel } from './events-panel'
import { Header } from './header'
import { Sidebar, type Section } from './sidebar'
import { CameraWorkspaceSkeleton } from './loading'
import { ConnectionNotice } from './connection-notice'
import { AccountSettings } from './account-settings'

interface DashboardShellProps {
  section: Section
  onNavigate: (section: Section) => void
  onRequireAuth: () => void
  reduceAnimations: boolean
  onReduceAnimationsChange: (value: boolean) => void
}

export function DashboardShell({ section, onNavigate, onRequireAuth, reduceAnimations, onReduceAnimationsChange }: DashboardShellProps) {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')
  const [reconnecting, setReconnecting] = useState(false)
  const [revision, setRevision] = useState(0)
  const [signingOut, setSigningOut] = useState(false)
  const [clock, setClock] = useState(() => Date.now() / 1000)
  const [eventsOpen, setEventsOpen] = useState(true)
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null)
  const [visibleIds, setVisibleIds] = useState<string[] | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const refresh = useCallback(() => {
    setReconnecting(true)
    setActionError('')
    setRevision(value => value + 1)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function load() {
      setReconnecting(true)
      try {
        const result = await api<DashboardData>('/dashboard', { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15_000)]) })
        if (controller.signal.aborted) return
        if (!result || !Array.isArray(result.cameras) || !Array.isArray(result.events) || !result.user) {
          throw new ApiError('Dashboard data is not available.', 502)
        }
        setData(result); setError('')
        setVisibleIds(previous => previous === null ? result.cameras.map(camera => camera.id)
          : previous.filter(id => result.cameras.some(camera => camera.id === id)))
      } catch (error) {
        if (controller.signal.aborted) return
        setData(null)
        if (error instanceof ApiError && error.status === 401) onRequireAuth()
        else setError((error as Error).message)
      } finally {
        if (!controller.signal.aborted) {
          setReconnecting(false)
          timer = setTimeout(load, 5000)
        }
      }
    }
    void load()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [revision, onRequireAuth])

  useEffect(() => {
    const timer = setInterval(() => setClock(Date.now() / 1000), 1000)
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !document.querySelector('[role="menu"]')) setExpandedId(null)
    }
    const endSession = () => { setData(null); onRequireAuth() }
    window.addEventListener('sentinel-session-ended', endSession)
    window.addEventListener('keydown', onKey)
    return () => { clearInterval(timer); window.removeEventListener('sentinel-session-ended', endSession); window.removeEventListener('keydown', onKey) }
  }, [onRequireAuth])

  const focusCamera = useCallback((id: string) => {
    setVisibleIds(previous => Array.from(new Set([...(previous ?? []), id])))
    setExpandedId(id); onNavigate('dashboard')
  }, [onNavigate])

  const cameras = data?.cameras ?? []
  const events = data?.events ?? []
  const user = data?.user
  const loading = !data && !error
  const unreviewed = events.filter(event => !event.reviewed).length
  const ids = (visibleIds ?? []).filter(id => cameras.some(camera => camera.id === id))
  const selectedEvent = events.find(event => event.id === selectedEventId)
  async function signOut() {
    if (signingOut) return
    setSigningOut(true)
    setActionError('')
    try {
      await api('/session', { method: 'DELETE' })
      setData(null)
      onRequireAuth()
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) onRequireAuth()
      else setActionError('Couldn’t log out. Please try again.')
    } finally {
      setSigningOut(false)
    }
  }
  async function review(id: string) {
    setActionError('')
    try { await api(`/events/${encodeURIComponent(id)}/review`, { method: 'POST' }); refresh() }
    catch { setActionError('Couldn’t mark this event as reviewed. Please try again.') }
  }
  return <div className="flex h-dvh min-h-[560px] w-full overflow-hidden bg-background">
    <Sidebar user={user} section={section} onNavigate={onNavigate} />
    <div className="flex min-w-0 flex-1 flex-col">
      <Header user={user} title={section[0].toUpperCase() + section.slice(1)} clock={clock} onSettings={() => onNavigate('settings')} onSignOut={signOut} signingOut={signingOut} />
      {error && <ConnectionNotice reconnecting={reconnecting} onReconnect={refresh} />}
      {actionError && <div role="alert" className="mx-3 mt-3 flex items-center justify-between gap-4 rounded-xl border bg-panel px-4 py-3 text-sm text-muted-foreground sm:mx-4">
        <p>{actionError}</p>
        <button type="button" onClick={() => setActionError('')} aria-label="Dismiss message" className="flex size-8 shrink-0 items-center justify-center rounded-md hover:bg-surface-hover"><X className="size-4" aria-hidden="true" /></button>
      </div>}
      <main className="relative flex min-h-0 flex-1">
        {section === 'settings' ? <AccountSettings user={user} loading={loading} reduceAnimations={reduceAnimations} onReduceAnimationsChange={onReduceAnimationsChange} /> : section === 'cameras' && user?.role === 'administrator' ? <CameraSettings cameras={cameras} onChange={() => { setVisibleIds(null); refresh() }} />
          : section !== 'events' && (loading || error ? <CameraWorkspaceSkeleton loading={loading} /> : cameras.length ? <CameraWorkspace cameras={cameras} visibleIds={ids} onVisibleChange={setVisibleIds} expandedId={expandedId} onExpand={setExpandedId} highlightedCameraId={eventsOpen ? selectedEvent?.cameraId ?? null : null} eventsOpen={eventsOpen} unreviewedCount={unreviewed} onOpenEvents={() => setEventsOpen(true)} />
          : <section className="flex min-w-0 flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
              <VideoOff className="size-8 text-muted-foreground" aria-hidden="true" />
              <h2 className="text-lg font-semibold">No cameras connected</h2>
              <p className="max-w-sm text-sm text-muted-foreground">Connected cameras will appear here.</p>
              {data && user?.role === 'administrator' && <button onClick={() => onNavigate('cameras')} className="mt-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground">Add camera</button>}
            </section>)}
        {section !== 'cameras' && section !== 'settings' && <EventsPanel loading={loading} loadError={!data && Boolean(error)} cameras={cameras} open={section === 'events' || eventsOpen} fullWidth={section === 'events'} events={events} clock={clock} selectedId={selectedEventId} onSelect={setSelectedEventId} onClose={() => { setEventsOpen(false); onNavigate('dashboard') }} onMarkReviewed={review} onViewCamera={focusCamera} onViewAll={() => onNavigate('events')} />}
      </main>
    </div>
  </div>
}
