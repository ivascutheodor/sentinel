import { useEffect, useRef, useState } from 'react'
import { CameraOff, Maximize2, Minimize2 } from 'lucide-react'
import type { Camera } from '@/lib/data'
import { cn } from '@/lib/utils'

export type TileVariant = 'grid' | 'focus' | 'strip'
interface CameraTileProps {
  camera: Camera; variant: TileVariant; clock: number; showBoxes: boolean; showZones: boolean
  highlighted?: boolean; onExpand?: () => void; onCollapse?: () => void; onSelect?: () => void; className?: string
}

export function CameraTile({ camera, variant, highlighted, onExpand, onCollapse, onSelect, className }: CameraTileProps) {
  const [image, setImage] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [loadedAt, setLoadedAt] = useState<Date | null>(null)
  const imageRef = useRef<string | null>(null)
  useEffect(() => {
    setImage(null); setLoadedAt(null); setError('')
    if (!camera.enabled || !camera.image) return
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function load() {
      try {
        const response = await fetch(camera.image!, { credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12_000)]) })
        if (response.status === 401) window.dispatchEvent(new Event('sentinel-session-ended'))
        if (!response.ok) {
          const body = await response.json().catch(() => null)
          throw new Error(typeof body?.detail === 'string' ? body.detail : 'Cannot reach this camera. Check its connection.')
        }
        if (!response.headers.get('content-type')?.startsWith('image/jpeg')) throw new Error('The camera returned an invalid frame.')
        const blob = await response.blob()
        if (controller.signal.aborted) return
        const next = URL.createObjectURL(blob)
        if (imageRef.current) URL.revokeObjectURL(imageRef.current)
        imageRef.current = next
        setImage(next); setError('')
      } catch (error) {
        if (controller.signal.aborted) return
        setImage(null); setLoadedAt(null); setError((error as Error).message)
        if (imageRef.current) URL.revokeObjectURL(imageRef.current)
        imageRef.current = null
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(load, 3000)
      }
    }
    void load()
    return () => { controller.abort(); clearTimeout(timer); if (imageRef.current) URL.revokeObjectURL(imageRef.current); imageRef.current = null }
  }, [camera.id, camera.image, camera.enabled])
  const live = Boolean(image && loadedAt)
  const strip = variant === 'strip'
  return <article aria-label={`${camera.name}, ${live ? 'Connected' : camera.enabled ? 'Connecting or unavailable' : 'Disabled'}`} onDoubleClick={strip ? undefined : onExpand ?? onCollapse} className={cn('group relative min-h-0 min-w-0 overflow-hidden rounded-xl border border-border-strong bg-black', highlighted && 'ring-2 ring-primary', className)}>
    {image && <img src={image} alt={`Camera view of ${camera.name}`} onLoad={() => setLoadedAt(new Date())} onError={() => { setLoadedAt(null); setImage(null); setError('The camera frame could not be decoded.') }} className="absolute inset-0 size-full object-contain" />}
    {!live && <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center"><CameraOff className="size-7 text-muted-foreground" aria-hidden="true" /><p className="text-sm font-medium">{!camera.enabled ? 'Monitoring disabled' : error ? 'Camera unavailable' : 'Connecting to camera…'}</p>{!strip && error && <p role="status" className="max-w-sm text-xs text-muted-foreground">{error}</p>}</div>}
    <div className="absolute inset-x-0 top-0 flex items-start justify-between gap-2 bg-black/70 p-2.5"><div className="min-w-0"><h3 className="truncate text-[13px] font-semibold text-white">{camera.name}</h3>{!strip && <p className="truncate text-[11px] text-white/70">{camera.location || 'Location not set'}</p>}</div><span className={cn('shrink-0 text-[10px] font-medium', live ? 'text-success' : 'text-muted-foreground')}>{live ? 'Connected' : !camera.enabled ? 'Disabled' : error ? 'Unavailable' : 'Connecting'}</span></div>
    {!strip && <div className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-2 bg-black/70 p-2.5"><p className="text-[10px] text-white/70">{loadedAt ? `Updated ${loadedAt.toLocaleTimeString()}` : 'No current frame'}<span className="block">{camera.inferenceAt ? `Last detection check ${new Date(camera.inferenceAt).toLocaleTimeString()}` : 'Detection worker has not reported'}</span></p>{variant === 'focus' ? <button onClick={onCollapse} className="flex shrink-0 items-center gap-1 rounded-md border border-white/15 px-2 py-1 text-[11px] text-white hover:bg-white/10"><Minimize2 className="size-3.5" aria-hidden="true" />Back to grid</button> : <button onClick={onExpand} aria-label={`Expand ${camera.name}`} className="flex size-8 shrink-0 items-center justify-center rounded-md border border-white/15 text-white hover:bg-white/10"><Maximize2 className="size-3.5" aria-hidden="true" /></button>}</div>}
    {strip && <button onClick={onSelect} aria-label={`Focus ${camera.name}`} className="absolute inset-0 rounded-xl hover:bg-white/5" />}
  </article>
}
