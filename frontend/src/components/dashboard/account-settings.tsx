import type { User } from '@/lib/data'
import { ROLE_LABEL } from '@/lib/data'
import { Skeleton } from '@/components/ui/skeleton'

export function AccountSettings({ user, loading, reduceAnimations, onReduceAnimationsChange }: {
  user?: User; loading: boolean; reduceAnimations: boolean; onReduceAnimationsChange: (value: boolean) => void
}) {
  return (
    <section aria-label="Account settings" className="thin-scroll min-w-0 flex-1 overflow-y-auto p-5 sm:p-8">
      <div className="mx-auto max-w-2xl">
        <h2 className="text-xl font-semibold">Account settings</h2>
        <p className="mt-2 text-sm text-muted-foreground">Your profile and interface preferences.</p>

        <div className="mt-8 border-t pt-6">
          <h3 className="text-sm font-semibold">Profile</h3>
          <p className="mt-1 text-sm text-muted-foreground">Account details are managed by your administrator.</p>
          {user ? <dl className="mt-5 divide-y rounded-xl border bg-panel">
            {[['Name', user.name], ['Email address', user.email], ['Role', ROLE_LABEL[user.role]]].map(([label, value]) => <div key={label} className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-baseline sm:justify-between sm:gap-6">
              <dt className="text-sm text-muted-foreground">{label}</dt><dd className="break-all text-sm font-medium sm:text-right">{value}</dd>
            </div>)}
          </dl> : loading ? <div aria-busy="true" className="mt-5 space-y-4 rounded-xl border bg-panel p-4"><p role="status" className="sr-only">Loading account details…</p><Skeleton className="h-4 w-1/2" /><Skeleton className="h-4 w-2/3" /><Skeleton className="h-4 w-1/3" /></div>
            : <p className="mt-5 text-sm text-muted-foreground">Account details are currently unavailable.</p>}
        </div>

        <div className="mt-8 border-t pt-6">
          <h3 className="text-sm font-semibold">Interface</h3>
          <p className="mt-1 text-sm text-muted-foreground">Preferences are saved in this browser.</p>
          <label className="mt-5 flex cursor-pointer items-start justify-between gap-6 rounded-xl border bg-panel p-4">
            <span><span id="motion-label" className="block text-sm font-medium">Reduce animations</span><span id="motion-description" className="mt-1 block text-sm leading-relaxed text-muted-foreground">Use less motion for loading indicators and transitions. Your system’s reduced-motion preference is always respected.</span></span>
            <input type="checkbox" checked={reduceAnimations} onChange={event => onReduceAnimationsChange(event.target.checked)} aria-labelledby="motion-label" aria-describedby="motion-description" className="mt-1 size-4 shrink-0 accent-primary" />
          </label>
        </div>
      </div>
    </section>
  )
}
