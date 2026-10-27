import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { LoaderCircle, LogOut, Settings, UserRound } from 'lucide-react'
import { ROLE_LABEL, type User } from '@/lib/data'

export function UserMenu({ user, onSettings, onSignOut, signingOut }: {
  user?: User; onSettings: () => void; onSignOut: () => void; signingOut: boolean
}) {
  return <DropdownMenu.Root>
    <DropdownMenu.Trigger asChild><button type="button" aria-label={user ? `Account menu for ${user.name}` : 'Account menu'} title="Your account" disabled={signingOut} aria-busy={signingOut} className="flex size-10 items-center justify-center rounded-full border bg-surface text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground disabled:cursor-wait disabled:opacity-60">
      {signingOut ? <LoaderCircle className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" /> : <UserRound className="size-4" aria-hidden="true" />}
    </button></DropdownMenu.Trigger>
    <DropdownMenu.Portal><DropdownMenu.Content align="end" sideOffset={8} collisionPadding={12} className="z-50 w-64 max-w-[calc(100vw-24px)] rounded-lg border bg-panel p-1 shadow-xl shadow-black/50">
      <div className="px-2 py-2"><p className="truncate text-sm font-medium">{user?.name ?? 'Your account'}</p>{user && <><p className="truncate text-xs text-muted-foreground">{user.username}</p><p className="mt-1 text-xs text-muted-foreground">{ROLE_LABEL[user.role]}</p></>}</div>
      <DropdownMenu.Separator className="my-1 h-px bg-border" />
      <DropdownMenu.Item onSelect={onSettings} className="flex min-h-10 cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-sm outline-none data-[highlighted]:bg-surface-hover"><Settings className="size-4" aria-hidden="true" />Settings</DropdownMenu.Item>
      <DropdownMenu.Item onSelect={onSignOut} disabled={signingOut} className="flex min-h-10 cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-sm outline-none data-[highlighted]:bg-surface-hover data-[disabled]:opacity-50"><LogOut className="size-4" aria-hidden="true" />Log out</DropdownMenu.Item>
    </DropdownMenu.Content></DropdownMenu.Portal>
  </DropdownMenu.Root>
}
