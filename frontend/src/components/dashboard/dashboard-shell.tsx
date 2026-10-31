import { useCallback, useEffect, useState } from 'react'
import { VideoOff, X } from 'lucide-react'
import { ApiError } from '@/lib/api'
import { getCurrentUser, getEvents, signOut as logOut } from '@/lib/backend'
import type { DashboardData, User } from '@/lib/data'
import { CameraWorkspace } from './camera-workspace'
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
  const [currentUser, setCurrentUser] = useState<User | undefined>()
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
        const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(15_000)])
        const authenticatedUser = await getCurrentUser(signal)
        if (controller.signal.aborted) return
        setCurrentUser(authenticatedUser)
        const events = await getEvents(signal)
        if (controller.signal.aborted) return
        const result: DashboardData = { user: authenticatedUser, cameras: [], events }
        setData(result)
        setError('')
        setVisibleIds(previous => previous === null ? result.cameras.map(camera => camera.id)
          : previous.filter(id => result.cameras.some(camera => camera.id === id)))
      } catch (error) {
        if (controller.signal.aborted) return
        setData(null)
        if (error instanceof ApiError && error.status === 401) { setCurrentUser(undefined); onRequireAuth() }
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
    const endSession = () => { setCurrentUser(undefined); setData(null); onRequireAuth() }
    window.addEventListener('sentinel-session-ended', endSession)
    window.addEventListener('keydown', onKey)
    return () => { clearInterval(timer); window.removeEventListener('sentinel-session-ended', endSession); window.removeEventListener('keydown', onKey) }
  }, [onRequireAuth])

  const cameras = data?.cameras ?? []
  const events = data?.events ?? []
  const user = currentUser
  const loading = !data && !error
  const ids = (visibleIds ?? []).filter(id => cameras.some(camera => camera.id === id))
  const selectedEvent = events.find(event => event.id === selectedEventId)
  async function signOut() {
    if (signingOut) return
    setSigningOut(true)
    setActionError('')
    try {
      await logOut()
      setData(null)
      setCurrentUser(undefined)
      onRequireAuth()
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) { setCurrentUser(undefined); onRequireAuth() }
      else setActionError('Couldn’t log out. Please try again.')
    } finally {
      setSigningOut(false)
    }
  }
  function eventDeleted(id: string) {
    setSelectedEventId(null)
    setData(previous => previous ? { ...previous, events: previous.events.filter(event => event.id !== id) } : null)
    refresh()
  }
  return <div className="flex h-dvh min-h-[560px] w-full overflow-hidden bg-background">
    <Sidebar section={section} onNavigate={onNavigate} />
    <div className="flex min-w-0 flex-1 flex-col">
      <Header user={user} title={section[0].toUpperCase() + section.slice(1)} clock={clock} onSettings={() => onNavigate('settings')} onSignOut={signOut} signingOut={signingOut} />
      {error && <ConnectionNotice reconnecting={reconnecting} onReconnect={refresh} />}
      {actionError && <div role="alert" className="mx-3 mt-3 flex items-center justify-between gap-4 rounded-xl border bg-panel px-4 py-3 text-sm text-muted-foreground sm:mx-4">
        <p>{actionError}</p>
        <button type="button" onClick={() => setActionError('')} aria-label="Dismiss message" className="flex size-8 shrink-0 items-center justify-center rounded-md hover:bg-surface-hover"><X className="size-4" aria-hidden="true" /></button>
      </div>}
      <main className="relative flex min-h-0 flex-1">
        {section === 'settings' ? <AccountSettings user={user} loading={!user && loading} reduceAnimations={reduceAnimations} onReduceAnimationsChange={onReduceAnimationsChange} />
          : section !== 'events' && (loading || error ? <CameraWorkspaceSkeleton loading={loading} /> : cameras.length ? <CameraWorkspace cameras={cameras} visibleIds={ids} onVisibleChange={setVisibleIds} expandedId={expandedId} onExpand={setExpandedId} highlightedCameraId={eventsOpen ? selectedEvent?.cameraId ?? null : null} eventsOpen={eventsOpen} onOpenEvents={() => setEventsOpen(true)} />
          : <section className="flex min-w-0 flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
              <VideoOff className="size-8 text-muted-foreground" aria-hidden="true" />
              <h2 className="text-lg font-semibold">Live view is not available yet</h2>
              <p className="max-w-sm text-sm text-muted-foreground">You can browse recorded events and available recordings in Events.</p>
              <button onClick={() => onNavigate('events')} className="mt-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground">View events</button>
            </section>)}
        {section !== 'cameras' && section !== 'settings' && <EventsPanel loading={loading} loadError={!data && Boolean(error)} cameras={cameras} open={section === 'events' || eventsOpen} fullWidth={section === 'events'} events={events} clock={clock} selectedId={selectedEventId} onSelect={setSelectedEventId} onClose={() => { setEventsOpen(false); onNavigate('dashboard') }} canDelete={user?.role === 'administrator'} onDeleted={eventDeleted} onViewAll={() => onNavigate('events')} />}
      </main>
    </div>
  </div>
}
