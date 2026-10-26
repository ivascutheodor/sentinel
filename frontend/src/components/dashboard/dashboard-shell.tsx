import { useCallback, useEffect, useState } from 'react'
import { VideoOff } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { DashboardData } from '@/lib/data'
import { CameraWorkspace } from './camera-workspace'
import { CameraSettings } from './camera-settings'
import { EventsPanel } from './events-panel'
import { Header } from './header'
import { Sidebar, type Section } from './sidebar'
import { Login } from './login'

export function DashboardShell() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [needsLogin, setNeedsLogin] = useState(false)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [section, setSection] = useState<Section>('dashboard')
  const [clock, setClock] = useState(Date.now() / 1000)
  const [eventsOpen, setEventsOpen] = useState(true)
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null)
  const [visibleIds, setVisibleIds] = useState<string[] | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [showBoxes, setShowBoxes] = useState(true)
  const [showZones, setShowZones] = useState(true)
  const refresh = useCallback(() => setRevision(value => value + 1), [])

  useEffect(() => {
    if (needsLogin) return
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function load() {
      try {
        const result = await api<DashboardData>('/dashboard', { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15_000)]) })
        if (controller.signal.aborted) return
        setData(result); setError('')
        setVisibleIds(previous => previous === null ? result.cameras.map(camera => camera.id)
          : previous.filter(id => result.cameras.some(camera => camera.id === id)))
      } catch (error) {
        if (controller.signal.aborted) return
        setData(null)
        if (error instanceof ApiError && error.status === 401) setNeedsLogin(true)
        else setError((error as Error).message)
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(load, 5000)
      }
    }
    void load()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [revision, needsLogin])

  useEffect(() => {
    const timer = setInterval(() => setClock(Date.now() / 1000), 1000)
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !document.querySelector('[role="menu"]')) setExpandedId(null)
    }
    const endSession = () => { setData(null); setNeedsLogin(true) }
    window.addEventListener('sentinel-session-ended', endSession)
    window.addEventListener('keydown', onKey)
    return () => { clearInterval(timer); window.removeEventListener('sentinel-session-ended', endSession); window.removeEventListener('keydown', onKey) }
  }, [])

  const focusCamera = useCallback((id: string) => {
    setVisibleIds(previous => Array.from(new Set([...(previous ?? []), id])))
    setExpandedId(id); setSection('dashboard')
  }, [])

  if (needsLogin) return <Login onSuccess={() => { setVisibleIds(null); setNeedsLogin(false); refresh() }} />
  if (!data) return <main className="flex min-h-dvh items-center justify-center p-6"><div className="max-w-md space-y-4">
    <h1 className="text-xl font-semibold">{error ? 'Dashboard unavailable' : 'Connecting to Sentinel…'}</h1>
    <p role={error ? 'alert' : 'status'} className="text-sm text-muted-foreground">{error || 'Loading your cameras and recent events.'}</p>
    {error && <button onClick={refresh} className="rounded-lg border bg-surface px-4 py-2 text-sm hover:bg-surface-hover">Try again</button>}
  </div></main>

  const { cameras, events, user } = data
  const unreviewed = events.filter(event => !event.reviewed).length
  const ids = (visibleIds ?? []).filter(id => cameras.some(camera => camera.id === id))
  const selectedEvent = events.find(event => event.id === selectedEventId)
  async function signOut() {
    try { await api('/session', { method: 'DELETE' }); setData(null); setNeedsLogin(true) }
    catch (error) { setError((error as Error).message) }
  }
  async function review(id: string) {
    try { await api(`/events/${encodeURIComponent(id)}/review`, { method: 'POST' }); refresh() }
    catch (error) { setError((error as Error).message) }
  }
  return <div className="flex h-dvh min-h-[560px] w-full overflow-hidden bg-background">
    <Sidebar user={user} section={section} onNavigate={setSection} onSignOut={signOut} />
    <div className="flex min-w-0 flex-1 flex-col">
      <Header user={user} cameras={cameras} clock={clock} unreviewedCount={unreviewed} onSignOut={signOut} onOpenEvents={() => { setEventsOpen(true); setSection('events') }} />
      {error && <div role="alert" className="border-b bg-panel px-4 py-3 text-sm text-critical">{error}<button onClick={() => setError('')} className="ml-4 underline">Dismiss</button></div>}
      <main className="relative flex min-h-0 flex-1">
        {section === 'cameras' && user.role === 'administrator' ? <CameraSettings cameras={cameras} onChange={() => { setVisibleIds(null); refresh() }} />
          : section !== 'events' && (cameras.length ? <CameraWorkspace cameras={cameras} visibleIds={ids} onVisibleChange={setVisibleIds} expandedId={expandedId} onExpand={setExpandedId} clock={clock} showBoxes={showBoxes} showZones={showZones} onToggleBoxes={() => setShowBoxes(value => !value)} onToggleZones={() => setShowZones(value => !value)} highlightedCameraId={eventsOpen ? selectedEvent?.cameraId ?? null : null} eventsOpen={eventsOpen} unreviewedCount={unreviewed} onOpenEvents={() => setEventsOpen(true)} />
          : <section className="flex min-w-0 flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
              <VideoOff className="size-8 text-muted-foreground" aria-hidden="true" />
              <h2 className="text-lg font-semibold">{user.role === 'administrator' ? 'No cameras configured' : 'No cameras assigned'}</h2>
              <p className="max-w-sm text-sm text-muted-foreground">{user.role === 'administrator' ? 'Add a camera to start viewing real footage.' : 'Ask your administrator to assign a camera to your account.'}</p>
              {user.role === 'administrator' && <button onClick={() => setSection('cameras')} className="mt-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground">Add camera</button>}
            </section>)}
        {section !== 'cameras' && <EventsPanel cameras={cameras} open={section === 'events' || eventsOpen} fullWidth={section === 'events'} events={events} clock={clock} selectedId={selectedEventId} onSelect={setSelectedEventId} onClose={() => { setEventsOpen(false); setSection('dashboard') }} onMarkReviewed={review} onViewCamera={focusCamera} onViewAll={() => setSection('events')} />}
      </main>
    </div>
  </div>
}
