import { Skeleton } from '@/components/ui/skeleton'

export function CameraWorkspaceSkeleton({ loading = true }: { loading?: boolean }) {
  return (
    <section aria-label="Live camera workspace" aria-busy={loading} className="flex min-h-0 min-w-0 flex-1 flex-col">
      {loading && <p role="status" className="sr-only">Loading cameras…</p>}
      <div className="flex flex-wrap items-center gap-3 border-b bg-panel/60 px-4 py-3">
        <h2 className="text-sm font-semibold">Live view</h2>
        <Skeleton className="h-4 w-20" />
        <Skeleton className="ml-auto h-7 w-28" />
      </div>
      <div className="thin-scroll grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-auto p-3 md:grid-cols-2">
        {[0, 1].map(index => (
          <div key={index} aria-hidden="true" className="flex min-h-64 flex-col gap-4 rounded-xl border bg-panel p-4">
            <div className="flex items-center justify-between gap-4">
              <Skeleton className="h-4 w-2/5" />
              <Skeleton className="h-3 w-14" />
            </div>
            <Skeleton className="min-h-40 flex-1 rounded-lg" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        ))}
      </div>
    </section>
  )
}

export function EventListSkeleton({ loading = true }: { loading?: boolean }) {
  return (
    <div className="thin-scroll min-h-0 flex-1 overflow-y-auto">
      {loading && <p role="status" className="sr-only">Loading events…</p>}
      <div aria-hidden="true" className="divide-y divide-border/60">
        {[0, 1, 2, 3, 4].map(index => (
          <div key={index} className="flex gap-3 px-3 py-4">
            <Skeleton className="h-16 w-[84px] shrink-0" />
            <div className="min-w-0 flex-1 space-y-3 py-1">
              <div className="flex items-center justify-between gap-4">
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-3 w-10" />
              </div>
              <Skeleton className="h-3 w-5/6" />
              <Skeleton className="h-2.5 w-1/2" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
