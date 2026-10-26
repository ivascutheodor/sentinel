import { useState } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { FRAME_H, FRAME_W, type Box, type Camera, type Severity } from '@/lib/data'
import { cn } from '@/lib/utils'
import { SEVERITY_META } from './severity'

interface SnapshotProps {
  camera: Camera
  box?: Box
  severity: Severity
  aspect?: number
  zoom?: number
  showBox?: boolean
  className?: string
}

const clamp = (v: number, min: number, max: number) => Math.min(Math.max(v, min), max)

export function Snapshot(props: SnapshotProps) {
  return <SnapshotContent key={props.camera.image ?? ''} {...props} />
}

function SnapshotContent({
  camera,
  box = [0, 0, FRAME_W, FRAME_H],
  severity,
  aspect = 0.75,
  zoom = 3.4,
  showBox = false,
  className,
}: SnapshotProps) {
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [x, y, w, h] = box
  let cropW = clamp(Math.max(w * zoom, 300), 1, FRAME_W)
  let cropH = cropW * aspect
  if (cropH > FRAME_H) {
    cropH = FRAME_H
    cropW = cropH / aspect
  }
  const left = clamp(x + w / 2 - cropW / 2, 0, FRAME_W - cropW)
  const top = clamp(y + h / 2 - cropH / 2, 0, FRAME_H - cropH)
  const color = SEVERITY_META[severity].color
  const unavailable = !camera.image || status === 'error'
  const loading = Boolean(camera.image && status === 'loading')

  return (
    <div
      className={cn('relative overflow-hidden bg-black', className)}
      aria-busy={loading}
      style={{ aspectRatio: `${1 / aspect}` }}
    >
      {loading && <Skeleton className="absolute inset-0 rounded-none" />}
      {!unavailable ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={camera.image}
          alt=""
          onLoad={() => setStatus('ready')}
          onError={() => setStatus('error')}
          className={cn(
            'absolute max-w-none select-none',
            loading && 'opacity-0',
            camera.status === 'disconnected' && 'grayscale brightness-75',
          )}
          style={{
            width: `${(FRAME_W / cropW) * 100}%`,
            height: `${(FRAME_H / cropH) * 100}%`,
            left: `${(-left / cropW) * 100}%`,
            top: `${(-top / cropH) * 100}%`,
          }}
          draggable={false}
        />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center p-2 text-center text-[10px] text-muted-foreground">{status === 'error' ? 'Snapshot unavailable' : 'No snapshot'}</div>
      )}
      {showBox && !unavailable && !loading && (
        <div
          className="absolute rounded-[3px] border-2"
          style={{
            borderColor: color,
            boxShadow: `0 0 0 1px rgba(0,0,0,0.4), 0 0 14px ${color}55`,
            left: `${((x - left) / cropW) * 100}%`,
            top: `${((y - top) / cropH) * 100}%`,
            width: `${(w / cropW) * 100}%`,
            height: `${(h / cropH) * 100}%`,
          }}
        />
      )}
    </div>
  )
}
