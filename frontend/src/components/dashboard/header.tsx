import type { User } from '@/lib/data'
import { formatClock } from '@/lib/utils'
import { UserMenu } from './user-menu'

export function Header({ user, title, clock, onSettings, onSignOut, signingOut }: {
  user?: User; title: string; clock: number; onSettings: () => void; onSignOut: () => void; signingOut: boolean
}) {
  return <header className="flex min-h-14 shrink-0 flex-wrap items-center gap-3 border-b bg-panel px-4 py-2">
    <div className="min-w-0"><h1 className="text-[15px] font-semibold leading-tight">{title}</h1><p className="font-mono text-[11px] leading-tight text-muted-foreground">{new Date(clock * 1000).toLocaleDateString()} · {formatClock(clock)}</p></div>
    <div className="ml-auto"><UserMenu user={user} onSettings={onSettings} onSignOut={onSignOut} signingOut={signingOut} /></div>
  </header>
}
