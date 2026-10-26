import { Bell, Video } from 'lucide-react'
import type { Camera, User } from '@/lib/data'
import { formatClock } from '@/lib/utils'
import { UserMenu } from './user-menu'

export function Header({ user, cameras, clock, unreviewedCount, onSignOut, onOpenEvents }: {
  user: User; cameras: Camera[]; clock: number; unreviewedCount: number; onSignOut: () => void; onOpenEvents: () => void
}) {
  const online = cameras.filter(camera => camera.enabled && camera.status === 'connected').length
  return <header className="flex min-h-14 shrink-0 flex-wrap items-center gap-3 border-b bg-panel px-4 py-2">
    <div className="min-w-0"><h1 className="text-[15px] font-semibold leading-tight">Dashboard</h1><p className="font-mono text-[11px] leading-tight text-muted-foreground">{new Date(clock * 1000).toLocaleDateString()} · {formatClock(clock)}</p></div>
    <div className="ml-auto flex items-center gap-2">
      <div className="hidden items-center gap-2 rounded-lg border bg-surface px-3 py-1.5 text-xs sm:flex"><Video className="size-3.5 text-muted-foreground" aria-hidden="true" /><span>{online} of {cameras.length} cameras online</span></div>
      <button onClick={onOpenEvents} aria-label={`Notifications, ${unreviewedCount} unreviewed events`} className="relative flex size-9 items-center justify-center rounded-lg border bg-surface text-muted-foreground hover:bg-surface-hover"><Bell className="size-4" aria-hidden="true" />{unreviewedCount > 0 && <span className="absolute -right-1 -top-1 rounded-full bg-primary px-1 text-[10px] text-primary-foreground">{unreviewedCount}</span>}</button>
      <div className="hidden sm:block"><UserMenu user={user} onSignOut={onSignOut} variant="header" /></div>
    </div>
  </header>
}
