import { api, ApiError } from './api.ts'
import type { SecurityEvent, User } from './data.ts'

function invalidResponse(): never {
  throw new ApiError('The server returned an unsupported response.', 502)
}

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return invalidResponse()
  return value as Record<string, unknown>
}

function text(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) return invalidResponse()
  return value
}

function uuid(value: unknown): string {
  const result = text(value)
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(result)) return invalidResponse()
  return result
}

function timestamp(value: unknown): number {
  const result = text(value)
  if (!/T.*(?:Z|[+-]\d{2}:\d{2})$/i.test(result)) return invalidResponse()
  const milliseconds = Date.parse(result)
  if (!Number.isFinite(milliseconds)) return invalidResponse()
  return milliseconds / 1000
}

export function parseUser(value: unknown): User {
  const raw = object(value)
  const username = text(raw.username)
  if (!/^[a-z0-9._-]{3,50}$/.test(username)) return invalidResponse()
  if (raw.role !== 'admin' && raw.role !== 'user') return invalidResponse()
  const name = text(raw.display_name)
  return {
    id: uuid(raw.id), name, username,
    role: raw.role === 'admin' ? 'administrator' : 'operator',
    initials: name.trim().split(/\s+/).slice(0, 2).map(word => Array.from(word)[0]).join('').toUpperCase(),
  }
}

// The existing video route takes a single filename, never a filesystem path or external URL.
export function recordingUrl(path: string | null): string | null {
  if (path === null) return null
  if (typeof path !== 'string' || !path || Array.from(path).some(character => character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127) || /^[a-z][a-z\d+.-]*:\/\//i.test(path)) return null
  const parts = path.replace(/\\/g, '/').split('/')
  if (parts.some(part => part === '.' || part === '..')) return null
  const filename = parts.at(-1)
  return filename ? `/api/v1/videos/${encodeURIComponent(filename)}` : null
}

export function parseEvent(value: unknown, now = Date.now() / 1000): SecurityEvent {
  const raw = object(value)
  const id = uuid(raw.id)
  const base = {
    id, cameraId: uuid(raw.camera_id), title: 'Person presence',
    description: 'This event was registered by the monitoring service.',
  }

  // The authenticated server returns one recording with optional capture metadata.
  if (!Object.hasOwn(raw, 'clips')) {
    if (raw.video_path !== null && typeof raw.video_path !== 'string') return invalidResponse()
    const hasCapture = Object.hasOwn(raw, 'started_at')
    if (hasCapture && (!['capturing', 'completed', 'interrupted'].includes(text(raw.status))
      || (raw.clip_status !== null && !['pending', 'ready', 'failed', 'deleting', 'deleted'].includes(text(raw.clip_status))))) return invalidResponse()
    const status = hasCapture ? raw.clip_status as string | null : 'unknown'
    const url = status === 'ready' || status === 'unknown' ? recordingUrl(raw.video_path as string | null) : null
    return {
      ...base,
      ts: timestamp(hasCapture ? raw.started_at : raw.created_at),
      timestampLabel: hasCapture ? 'Started' : 'Registered',
      ...(hasCapture ? {
        captureStatus: raw.status as string,
        description: `Person-presence capture ${raw.status}.`,
        closedAt: raw.closed_at === null ? undefined : timestamp(raw.closed_at),
      } : {}),
      clips: raw.video_path || (hasCapture && status !== null) ? [{
        id: `${id}-recording`,
        status: (status === 'ready' || status === 'unknown') && !url ? 'unavailable' : status ?? 'unavailable',
        url,
      }] : [],
    }
  }

  // app/main.py exposes richer database events; preserve lifecycle and clip availability.
  if (!['capturing', 'completed', 'interrupted'].includes(text(raw.status)) || raw.event_type !== 'person_presence' || !Array.isArray(raw.clips)) return invalidResponse()
  const clips = raw.clips.map(value => {
    const clip = object(value)
    let status = text(clip.status)
    if (!['pending', 'ready', 'failed', 'deleting', 'deleted'].includes(status)) return invalidResponse()
    const expires = timestamp(clip.expires_at)
    if (!Number.isInteger(clip.part_number) || (clip.part_number as number) < 1) return invalidResponse()
    if (clip.filepath !== null && typeof clip.filepath !== 'string') return invalidResponse()
    const url = status === 'ready' && expires > now ? recordingUrl(clip.filepath as string | null) : null
    if (expires <= now && status === 'ready') status = 'expired'
    else if (status === 'ready' && !url) status = 'unavailable'
    return { id: uuid(clip.id), partNumber: clip.part_number as number, status, url }
  }).sort((a, b) => a.partNumber - b.partNumber)
  return {
    ...base, ts: timestamp(raw.started_at), timestampLabel: 'Started',
    captureStatus: raw.status as string,
    description: `Person-presence capture ${raw.status}.`,
    closedAt: raw.closed_at == null ? undefined : timestamp(raw.closed_at),
    endReason: raw.end_reason == null ? undefined : text(raw.end_reason),
    clips,
  }
}

export async function getCurrentUser(signal: AbortSignal): Promise<User> {
  return parseUser(await api<unknown>('/auth/me', { signal }))
}

export async function getEvents(signal: AbortSignal): Promise<SecurityEvent[]> {
  const response = await api<unknown>('/events', { signal })
  if (!Array.isArray(response)) return invalidResponse()
  return response.map(value => parseEvent(value)).sort((a, b) => b.ts - a.ts || a.id.localeCompare(b.id))
}

export async function getEvent(id: string, signal: AbortSignal): Promise<SecurityEvent> {
  return parseEvent(await api<unknown>(`/events/${encodeURIComponent(uuid(id))}`, { signal }))
}

export async function deleteEvent(id: string, signal: AbortSignal): Promise<void> {
  await api(`/events/${encodeURIComponent(uuid(id))}`, { method: 'DELETE', signal })
}

export async function signOut(): Promise<void> {
  await api('/auth/logout', { method: 'POST' })
}
