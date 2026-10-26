import { useRef, useState } from 'react'
import { Skeleton } from '@/components/ui/skeleton'

export function RecordingPlayer({ url }: { url: string }) {
  return <RecordingContent key={url} url={url} />
}

function RecordingContent({ url }: { url: string }) {
  const video = useRef<HTMLVideoElement>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')

  function retry() {
    setStatus('loading')
    video.current?.load()
  }

  return (
    <div aria-label="Event recording" aria-busy={status === 'loading'} className="relative aspect-video overflow-hidden rounded-lg bg-black">
      <video
        ref={video}
        controls
        preload="metadata"
        src={url}
        aria-label="Event recording player"
        onLoadedMetadata={() => setStatus('ready')}
        onCanPlay={() => setStatus('ready')}
        onWaiting={() => setStatus('loading')}
        onError={() => setStatus('error')}
        className="size-full"
      />
      {status === 'loading' && <div className="pointer-events-none absolute inset-0">
        <Skeleton className="size-full rounded-none" />
        <p role="status" className="sr-only">Loading recording…</p>
      </div>}
      {status === 'error' && <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-panel p-4 text-center">
        <p role="alert" className="text-sm text-muted-foreground">Recording could not be loaded.</p>
        <button type="button" onClick={retry} className="rounded-lg border bg-surface px-3 py-2 text-sm hover:bg-surface-hover">Retry recording</button>
      </div>}
    </div>
  )
}
