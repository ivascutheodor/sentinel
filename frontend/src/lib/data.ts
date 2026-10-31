export type Severity = 'critical' | 'warning' | 'info'
export type CameraStatus = 'connected' | 'disconnected' | 'unavailable'
export type Role = 'operator' | 'administrator'

export const FRAME_W = 1376
export const FRAME_H = 768

export type Box = [x: number, y: number, w: number, h: number]

export interface Zone {
  id: string
  name: string
  points: [number, number][]
  labelAt: [number, number]
}

export interface Detection {
  id: string
  box: Box
  confidence: number
  zoneId?: string
  severity: Severity
  label?: string
}

export interface Camera {
  id: string
  name: string
  location: string
  status: CameraStatus
  enabled: boolean
  inferenceAt?: string | null
  image?: string
  statusDetail?: string
  zones: Zone[]
  detections: Detection[]
}

export interface SecurityEvent {
  id: string
  cameraId: string
  severity?: Severity
  title: string
  description: string
  zoneName?: string
  confidence?: number
  captureStatus?: string
  snapshotUrl?: string
  clips: { id: string; status: string; url: string | null; partNumber?: number }[]
  dwell?: string
  box?: Box
  ts: number
  timestampLabel: 'Registered' | 'Started'
  closedAt?: number
  endReason?: string
  isNew?: boolean
}

export interface User {
  id: string
  name: string
  username: string
  role: Role
  initials: string
}

export const ROLE_LABEL: Record<Role, string> = {
  administrator: 'Administrator',
  operator: 'Operator',
}

const SEVERITY_RANK: Record<Severity, number> = { info: 0, warning: 1, critical: 2 }

export function maxSeverity(list: Severity[]): Severity | null {
  return list.length ? list.reduce((a, b) => SEVERITY_RANK[b] > SEVERITY_RANK[a] ? b : a) : null
}

export function cameraAlertLevel(camera: Camera): Severity | null {
  return camera.status === 'connected' ? maxSeverity(camera.detections.filter(d => d.zoneId).map(d => d.severity)) : null
}

export function zoneAlertLevel(camera: Camera, zoneId: string): Severity | null {
  return maxSeverity(camera.detections.filter(d => d.zoneId === zoneId).map(d => d.severity))
}

export function formatDetectionCount(n: number) {
  return `${n} ${n === 1 ? 'person' : 'people'}`
}

export interface DashboardData {
  user: User
  cameras: Camera[]
  events: SecurityEvent[]
}
