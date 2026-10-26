import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatClock(totalSeconds: number) {
  return new Date(totalSeconds * 1000).toLocaleTimeString([], { hour12: false })
}

export function formatAgo(seconds: number) {
  if (seconds < 10) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`
  return `${Math.floor(seconds / 3600)} h ago`
}
