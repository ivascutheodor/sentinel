import { LayoutDashboard, ListChecks, ShieldCheck, Video } from 'lucide-react'
import type { User } from '@/lib/data'
import { cn } from '@/lib/utils'
import { UserMenu } from './user-menu'

export type Section = 'dashboard' | 'cameras' | 'events'
export function Sidebar({ user, section, onNavigate, onSignOut }: {
  user: User; section: Section; onNavigate: (section: Section) => void; onSignOut: () => void
}) {
  const items = [
    { key: 'dashboard' as const, label: 'Dashboard', icon: LayoutDashboard },
    ...(user.role === 'administrator' ? [{ key: 'cameras' as const, label: 'Cameras', icon: Video }] : []),
    { key: 'events' as const, label: 'Events', icon: ListChecks },
  ]
  return <aside className="flex w-16 shrink-0 flex-col border-r bg-panel xl:w-60">
    <div className="flex h-14 items-center justify-center gap-2.5 border-b px-4 xl:justify-start"><span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground"><ShieldCheck className="size-5" aria-hidden="true" /></span><span className="hidden text-lg font-semibold xl:block">Sentinel</span></div>
    <nav aria-label="Primary" className="flex-1 space-y-1 overflow-y-auto px-2.5 py-4">
      {items.map(item => <button key={item.key} onClick={() => onNavigate(item.key)} aria-current={section === item.key ? 'page' : undefined} title={item.label} className={cn('flex w-full items-center justify-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors xl:justify-start', section === item.key ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-surface hover:text-foreground')}><item.icon className="size-[18px] shrink-0" aria-hidden="true" /><span className="sr-only xl:not-sr-only">{item.label}</span></button>)}
    </nav>
    <div className="border-t p-2.5"><UserMenu user={user} onSignOut={onSignOut} variant="sidebar" /></div>
  </aside>
}
