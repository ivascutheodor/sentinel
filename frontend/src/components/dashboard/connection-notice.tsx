import { RefreshCw, Unplug } from 'lucide-react'

interface ConnectionNoticeProps {
  reconnecting: boolean
  onReconnect: () => void
}

export function ConnectionNotice({ reconnecting, onReconnect }: ConnectionNoticeProps) {
  return (
    <section
      aria-label="Dashboard connection"
      className="mx-3 mt-3 flex shrink-0 flex-col gap-4 rounded-xl border bg-panel p-4 sm:mx-4 sm:mt-4 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex min-w-0 items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-surface text-muted-foreground">
          <Unplug className="size-4" aria-hidden="true" />
        </span>
        <div role="status" className="min-w-0 space-y-1">
          <h2 className="text-sm font-semibold text-foreground">Unable to connect</h2>
          <p className="max-w-lg text-sm leading-relaxed text-muted-foreground">
            Camera feeds and events are temporarily unavailable. We’ll keep trying to reconnect.
          </p>
        </div>
      </div>
      <button
        type="button"
        onClick={onReconnect}
        disabled={reconnecting}
        aria-busy={reconnecting}
        className="flex min-h-10 w-full shrink-0 items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-[filter] hover:brightness-110 disabled:cursor-wait disabled:opacity-60 sm:w-auto sm:min-w-40"
      >
        <RefreshCw className={`size-4 ${reconnecting ? 'animate-spin motion-reduce:animate-none' : ''}`} aria-hidden="true" />
        {reconnecting ? 'Reconnecting…' : 'Reconnect'}
      </button>
    </section>
  )
}
