'use client'

import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import {
  Check,
  ChevronDown,
  Columns2,
  Grid2x2,
  LayoutGrid,
  PanelRightOpen,
  Square,
  Video,
} from 'lucide-react'
import type { Camera } from '@/lib/data'
import { cn } from '@/lib/utils'
import { CameraTile } from './camera-tile'

const STATUS_DOT = {
  connected: 'bg-success',
  disconnected: 'bg-warning',
  unavailable: 'bg-muted-foreground',
} as const

function gridFor(count: number) {
  if (count <= 1) return { cols: 1, rows: 1 }
  if (count === 2) return { cols: 2, rows: 1 }
  if (count <= 4) return { cols: 2, rows: 2 }
  if (count <= 6) return { cols: 3, rows: 2 }
  return { cols: 3, rows: 3 }
}

interface CameraWorkspaceProps {
  cameras: Camera[]
  visibleIds: string[]
  onVisibleChange: (ids: string[]) => void
  expandedId: string | null
  onExpand: (id: string | null) => void
  highlightedCameraId: string | null
  eventsOpen: boolean
  onOpenEvents: () => void
}

export function CameraWorkspace({
  cameras,
  visibleIds,
  onVisibleChange,
  expandedId,
  onExpand,
  highlightedCameraId,
  eventsOpen,
  onOpenEvents,
}: CameraWorkspaceProps) {
  const visible = cameras.filter((c) => visibleIds.includes(c.id))
  const expanded = expandedId ? visible.find((c) => c.id === expandedId) : undefined

  const presets = [
    {
      key: 'single',
      label: 'Single',
      icon: Square,
      ids: () => {
        return cameras.length ? [cameras[0].id] : []
      },
      active: visible.length === 1,
    },
    {
      key: 'split',
      label: 'Split',
      icon: Columns2,
      ids: () => cameras.slice(0, 2).map((c) => c.id),
      active: visible.length === 2,
    },
    {
      key: 'quad',
      label: 'Quad',
      icon: Grid2x2,
      ids: () => cameras.slice(0, 4).map((c) => c.id),
      active: visible.length === 3 || visible.length === 4,
    },
    {
      key: 'all',
      label: 'All',
      icon: LayoutGrid,
      ids: () => cameras.map((c) => c.id),
      active: visible.length >= 5,
    },
  ]

  const toggleCamera = (camera: Camera, checked: boolean) => {
    if (checked) {
      onVisibleChange(cameras.filter((c) => c.id === camera.id || visibleIds.includes(c.id)).map((c) => c.id))
    } else if (visibleIds.length > 1) {
      onVisibleChange(visibleIds.filter((id) => id !== camera.id))
      if (expandedId === camera.id) onExpand(null)
    }
  }

  const { cols, rows } = gridFor(visible.length)

  return (
    <section aria-label="Live camera workspace" className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b bg-panel/60 px-3 py-2 sm:px-4">
        <div className="mr-1 hidden items-baseline gap-2 sm:flex">
          <h2 className="text-sm font-semibold">Live view</h2>
          <span className="text-xs text-muted-foreground">
            {visible.length} of {cameras.length} cameras
          </span>
        </div>

        <div
          role="group"
          aria-label="Layout"
          className="flex items-center rounded-lg border bg-surface p-0.5"
        >
          {presets.map((p) => (
            <button
              key={p.key}
              type="button"
              onClick={() => {
                onVisibleChange(p.ids())
                onExpand(null)
              }}
              aria-pressed={p.active}
              title={`${p.label} layout`}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium transition-colors',
                p.active
                  ? 'bg-surface-hover text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <p.icon className="size-3.5" aria-hidden="true" />
              <span className="hidden md:inline">{p.label}</span>
            </button>
          ))}
        </div>

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              type="button"
              className="flex items-center gap-1.5 rounded-lg border bg-surface px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-surface-hover data-[state=open]:bg-surface-hover"
            >
              <Video className="size-3.5 text-muted-foreground" aria-hidden="true" />
              Cameras
              <ChevronDown className="size-3 text-muted-foreground" aria-hidden="true" />
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="start"
              sideOffset={6}
              className="z-50 w-64 rounded-lg border border-border-strong bg-panel p-1 shadow-xl shadow-black/50"
            >
              <DropdownMenu.Label className="px-2 py-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Visible cameras
              </DropdownMenu.Label>
              {cameras.map((camera) => (
                <DropdownMenu.CheckboxItem
                  key={camera.id}
                  checked={visibleIds.includes(camera.id)}
                  onCheckedChange={(checked) => toggleCamera(camera, checked)}
                  onSelect={(e) => e.preventDefault()}
                  className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-sm outline-none data-[highlighted]:bg-surface-hover"
                >
                  <span
                    className={cn(
                      'flex size-4 items-center justify-center rounded border',
                      visibleIds.includes(camera.id)
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-border-strong',
                    )}
                  >
                    <DropdownMenu.ItemIndicator>
                      <Check className="size-3" strokeWidth={3} aria-hidden="true" />
                    </DropdownMenu.ItemIndicator>
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate leading-tight">{camera.name}</span>
                    <span className="block truncate font-mono text-[10px] text-muted-foreground">
                      {camera.id}
                    </span>
                  </span>
                  <span
                    className={cn('size-2 rounded-full', STATUS_DOT[camera.status])}
                    title={camera.status}
                  />
                </DropdownMenu.CheckboxItem>
              ))}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        <div className="ml-auto flex items-center gap-2">
          {!eventsOpen && (
            <button
              type="button"
              onClick={onOpenEvents}
              className="flex items-center gap-2 rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-surface-hover"
            >
              <PanelRightOpen className="size-3.5" aria-hidden="true" />
              Events

            </button>
          )}
        </div>
      </div>

      <div className="thin-scroll min-h-0 flex-1 overflow-auto p-3">
        {!visible.length && <p className="p-6 text-sm text-muted-foreground">No cameras selected. Choose a layout or select cameras from the Cameras menu.</p>}
        {expanded ? (
          <div className="flex h-full min-h-[420px] flex-col gap-3">
            <CameraTile
              key={`focus-${expanded.id}`}
              camera={expanded}
              variant="focus"
              highlighted={highlightedCameraId === expanded.id}
              onCollapse={() => onExpand(null)}
              className="flex-1"
            />
            {visible.length > 1 && (
              <div className="thin-scroll flex h-24 shrink-0 gap-3 overflow-x-auto">
                {visible
                  .filter((c) => c.id !== expanded.id)
                  .map((c) => (
                    <CameraTile
                      key={`strip-${c.id}`}
                      camera={c}
                      variant="strip"
                      onSelect={() => onExpand(c.id)}
                      className="aspect-video h-full shrink-0"
                    />
                  ))}
              </div>
            )}
          </div>
        ) : (
          <div
            className="grid h-full gap-3"
            style={{
              gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
              gridTemplateRows: `repeat(${rows}, minmax(0, 1fr))`,
              minHeight: rows * 200 + (rows - 1) * 12,
            }}
          >
            {visible.map((camera, i) => (
              <CameraTile
                key={camera.id}
                camera={camera}
                variant="grid"
                highlighted={highlightedCameraId === camera.id}
                onExpand={() => onExpand(camera.id)}
                className={cn(visible.length === 3 && i === 0 && 'row-span-2')}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
