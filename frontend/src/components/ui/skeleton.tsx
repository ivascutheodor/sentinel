import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  animated?: boolean
}

export function Skeleton({ className, animated = true, ...props }: SkeletonProps) {
  return <div {...props} aria-hidden="true" className={cn('skeleton rounded-md', !animated && 'skeleton-static', className)} />
}
