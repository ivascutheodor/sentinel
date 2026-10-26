import { Camera, FRAME_H, FRAME_W, zoneAlertLevel } from '@/lib/data'
import { cn } from '@/lib/utils'
import { SEVERITY_META } from './severity'

const NORMAL_ZONE = 'var(--primary)'

interface DetectionOverlayProps {
  camera: Camera
  showBoxes: boolean
  showZones: boolean
  compact?: boolean
}

export function DetectionOverlay({ camera, showBoxes, showZones, compact }: DetectionOverlayProps) {
  const pct = (x: number, y: number) => `${(x / FRAME_W) * 100},${(y / FRAME_H) * 100}`

  return (
    <>
      {showZones && (
        <>
          <svg
            className="pointer-events-none absolute inset-0 size-full"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            {camera.zones.map((zone) => {
              const level = zoneAlertLevel(camera, zone.id)
              const color = level ? SEVERITY_META[level].color : NORMAL_ZONE
              return (
                <polygon
                  key={zone.id}
                  points={zone.points.map(([x, y]) => pct(x, y)).join(' ')}
                  fill={color}
                  fillOpacity={level ? 0.16 : 0.09}
                  stroke={color}
                  strokeWidth={level ? 2 : 1.5}
                  strokeDasharray="7 5"
                  strokeLinejoin="round"
                  vectorEffect="non-scaling-stroke"
                />
              )
            })}
          </svg>
          {!compact &&
            camera.zones.map((zone) => {
              const level = zoneAlertLevel(camera, zone.id)
              const color = level ? SEVERITY_META[level].color : NORMAL_ZONE
              return (
                <span
                  key={zone.id}
                  className="pointer-events-none absolute whitespace-nowrap rounded-sm bg-black/60 px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider"
                  style={{
                    left: `${(zone.labelAt[0] / FRAME_W) * 100}%`,
                    top: `${(zone.labelAt[1] / FRAME_H) * 100}%`,
                    color,
                  }}
                >
                  Zone · {zone.name}
                </span>
              )
            })}
        </>
      )}

      {showBoxes &&
        camera.detections.map((d) => {
          const [x, y, w, h] = d.box
          const meta = SEVERITY_META[d.severity]
          const inZone = Boolean(d.zoneId)
          return (
            <div
              key={d.id}
              className="pointer-events-none absolute"
              style={{
                left: `${(x / FRAME_W) * 100}%`,
                top: `${(y / FRAME_H) * 100}%`,
                width: `${(w / FRAME_W) * 100}%`,
                height: `${(h / FRAME_H) * 100}%`,
              }}
            >
              <div
                className="absolute inset-0 rounded-[3px] border-2"
                style={{
                  borderColor: meta.color,
                  boxShadow: `0 0 0 1px rgba(0,0,0,0.45), 0 0 ${inZone ? 18 : 8}px ${meta.color}66`,
                  backgroundColor: inZone ? `color-mix(in oklab, ${meta.color} 10%, transparent)` : undefined,
                }}
              />
              {!compact && (
                <span
                  className={cn(
                    'absolute bottom-full left-[-2px] mb-0.5 flex items-center gap-1 whitespace-nowrap rounded-sm px-1 py-px font-mono text-[10px] font-semibold leading-tight text-black',
                  )}
                  style={{ backgroundColor: meta.color }}
                >
                  {d.label ?? 'Person'} {Math.round(d.confidence * 100)}%
                </span>
              )}
            </div>
          )
        })}
    </>
  )
}
