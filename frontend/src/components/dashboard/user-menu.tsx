import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { LogOut } from 'lucide-react'
import { ROLE_LABEL, type User } from '@/lib/data'

export function UserMenu({ user, onSignOut, variant }: { user: User; onSignOut: () => void; variant: 'sidebar' | 'header' }) {
  return <DropdownMenu.Root>
    <DropdownMenu.Trigger asChild><button type="button" aria-label={`Account menu for ${user.name}`} className="flex w-full items-center gap-2.5 rounded-lg p-1.5 text-left hover:bg-surface">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">{user.initials}</span>
      <span className={variant === 'sidebar' ? 'hidden min-w-0 xl:block' : 'hidden min-w-0 lg:block'}><span className="block truncate text-[13px] font-medium">{user.name}</span><span className="block text-[11px] text-muted-foreground">{ROLE_LABEL[user.role]}</span></span>
    </button></DropdownMenu.Trigger>
    <DropdownMenu.Portal><DropdownMenu.Content align="end" side={variant === 'sidebar' ? 'top' : 'bottom'} sideOffset={8} className="z-50 w-64 rounded-lg border bg-panel p-1 shadow-xl shadow-black/50">
      <div className="px-2 py-2"><p className="truncate text-sm font-medium">{user.name}</p><p className="truncate text-xs text-muted-foreground">{user.email}</p></div>
      <DropdownMenu.Separator className="my-1 h-px bg-border" />
      <DropdownMenu.Item onSelect={onSignOut} className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-sm outline-none data-[highlighted]:bg-surface-hover"><LogOut className="size-4" aria-hidden="true" />Sign out</DropdownMenu.Item>
    </DropdownMenu.Content></DropdownMenu.Portal>
  </DropdownMenu.Root>
}
