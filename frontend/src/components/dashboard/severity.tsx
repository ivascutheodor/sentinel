import { AlertOctagon, AlertTriangle, ScanEye } from 'lucide-react'
import type { Severity } from '@/lib/data'
import { cn } from '@/lib/utils'

export const SEVERITY_META: Record<
  Severity,
  { label: string; color: string; text: string; bg: string; border: string }
> = {
  critical: {
    label: 'Critical',
    color: 'var(--critical)',
    text: 'text-critical',
    bg: 'bg-critical/15',
    border: 'border-critical/40',
  },
  warning: {
    label: 'Warning',
    color: 'var(--warning)',
    text: 'text-warning',
    bg: 'bg-warning/15',
    border: 'border-warning/40',
  },
  info: {
    label: 'Detection',
    color: 'var(--info)',
    text: 'text-info',
    bg: 'bg-info/15',
    border: 'border-info/40',
  },
}

export function SeverityIcon({ severity, className }: { severity: Severity; className?: string }) {
  const Icon = severity === 'critical' ? AlertOctagon : severity === 'warning' ? AlertTriangle : ScanEye
  return <Icon className={cn(SEVERITY_META[severity].text, className)} aria-hidden="true" />
}

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  const meta = SEVERITY_META[severity]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
        meta.bg,
        meta.text,
        meta.border,
        className,
      )}
    >
      <SeverityIcon severity={severity} className="size-3" />
      {meta.label}
    </span>
  )
}
