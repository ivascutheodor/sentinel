---
name: Sentinel
description: A conventional security workspace for camera monitoring and presence-event review.
colors:
  primary: "#2563eb"
  primary-hover: "#1d4ed8"
  selection: "#e2ebff"
  surface: "#fff"
  background: "#f5f7fa"
  text: "#1e2c41"
  text-muted: "#536277"
  border: "#e0e6ee"
  nav: "#1d2c3f"
  nav-text: "#e4eaf2"
  nav-hover: "#2a3b51"
  secondary-text: "#2857a7"
  secondary-surface: "#edf3fd"
  secondary-hover: "#dfebff"
  current: "#167243"
  stale: "#8c570b"
  failed: "#a13e39"
  preparing: "#896018"
  unavailable: "#627085"
  field-border: "#cdd6e4"
  field-text: "#263751"
  media-surface: "#1e293b"
  media-text: "#f8fafc"
  media-hover: "#334155"
  media-focus: "#93c5fd"
  media-disabled: "#94a3b8"
typography:
  headline:
    fontFamily: "Arial, 'Helvetica Neue', sans-serif"
    fontSize: "28px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.025em"
  headline-small:
    fontFamily: "Arial, 'Helvetica Neue', sans-serif"
    fontSize: "25px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Arial, 'Helvetica Neue', sans-serif"
    fontSize: "18px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.02em"
  camera-title:
    fontFamily: "Arial, 'Helvetica Neue', sans-serif"
    fontSize: "17px"
    fontWeight: 650
    lineHeight: 1.4
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Arial, 'Helvetica Neue', sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  navigation:
    fontFamily: "Arial, 'Helvetica Neue', sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  field:
    fontFamily: "Arial, 'Helvetica Neue', sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Arial, 'Helvetica Neue', sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
  caption:
    fontFamily: "Arial, 'Helvetica Neue', sans-serif"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.5
  button:
    fontFamily: "Arial, 'Helvetica Neue', sans-serif"
    fontSize: "14px"
    fontWeight: 500
    lineHeight: 1.5
rounded:
  preview: "3px"
  media: "4px"
  control: "5px"
  recording: "6px"
  panel: "8px"
  dialog: "10px"
spacing:
  micro: "4px"
  tight: "6px"
  compact: "8px"
  control: "10px"
  small: "12px"
  panel: "14px"
  base: "16px"
  roomy: "20px"
  section: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "10px 17px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "{colors.secondary-surface}"
    textColor: "{colors.secondary-text}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "10px 17px"
  button-secondary-hover:
    backgroundColor: "{colors.secondary-hover}"
  button-text:
    backgroundColor: "transparent"
    textColor: "#215bbd"
    typography: "{typography.body}"
    rounded: "{rounded.media}"
    padding: "9px"
  button-icon:
    backgroundColor: "transparent"
    textColor: "{colors.text-muted}"
    rounded: "{rounded.control}"
    height: "34px"
    width: "34px"
  demo-label:
    backgroundColor: "#e9eef5"
    textColor: "#354964"
    typography: "{typography.label}"
    rounded: "{rounded.media}"
    padding: "5px 9px"
  filter-select:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.field-text}"
    typography: "{typography.field}"
    rounded: "{rounded.control}"
    padding: "7px 24px 7px 10px"
  navigation-link:
    backgroundColor: "transparent"
    textColor: "{colors.nav-text}"
    typography: "{typography.navigation}"
    rounded: "{rounded.control}"
    padding: "13px 16px"
  navigation-link-current:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
  camera-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.panel}"
    padding: "{spacing.base}"
  event-row-selected:
    backgroundColor: "{colors.selection}"
    textColor: "{colors.text}"
    typography: "{typography.label}"
  media-button:
    backgroundColor: "transparent"
    textColor: "{colors.media-text}"
    rounded: "{rounded.media}"
    height: "44px"
    width: "40px"
---

# Design System: Sentinel

## Overview

**Creative North Star: "The Conventional Security Workspace"**

Sentinel uses a familiar, restrained operator interface: a navy navigation rail,
pale application ground, white bordered panels, and clear blue selection. The
workhorse sans, compact metadata, and aligned controls give footage and event
records room to be read. This records the user's approved conventional dashboard
direction as implemented, rather than introducing a new identity.

The current implementation is a labeled demonstration workspace. Its camera
imagery is synthetic and its recordings are illustrative still-frame previews.
Keep those disclosures visible; production authentication, camera transport, and
backend authorization are still required. Detailed access requirements remain in
[PRODUCT.md](PRODUCT.md), and page composition remains in the
[operator surface brief](.impeccable/surfaces/frontend-src-app-tsx.md).

**Key Characteristics:**

- Navy navigation, pale ground, and quiet white panels.
- Blue navigation and event selection, with written status labels.
- Compact sans typography, tabular timestamps, and conventional media controls.
- Contained imagery, modest corners, and shadows reserved for overlays.

Extracted from `frontend/src/index.css`, `App.css`, `App.tsx`, and the CameraCard
and MediaPlayer components and stylesheets on 15 October 2026. The approved comp
is `.impeccable/mocks/decision/conventional-dashboard.png`; final visual evidence
is in `.impeccable/review/{desktop,laptop,mobile,comp-size}.png`. Review and tooling
limitations are recorded separately in
[verification notes](.impeccable/review/verification-notes.md). The unresolved
asset-checker gate is not a complete automatic pass and does not define a visual
rule. Frontmatter is the normative token layer; the
[sidecar](.impeccable/design.json) adds previews, motion, elevation, and breakpoints.
Its synthesized tonal ramps are panel preview aids, not additional shipping tokens.

## Colors

One blue interaction accent sits within cool neutral surfaces; state colors
communicate operational facts rather than threat severity.

### Primary

- **Selection Blue** (`primary`, `primary-hover`): current navigation, recovery
  actions, focus, and media progress. `selection` is the pale selected-row fill.
- **Quiet Blue Action** (`secondary-text`, `secondary-surface`,
  `secondary-hover`): the secondary access-check action.

### Neutral

- **Navy Rail** (`nav`, `nav-text`, `nav-hover`): navigation and camera preview
  backing, with light labels and a lighter hover surface.
- **Pale Ground and White Panels** (`background`, `surface`, `border`): separate
  application ground from working areas without persistent shadows.
- **Ink and Slate** (`text`, `text-muted`): primary content and supporting metadata.
- **Field Outline and Ink** (`field-border`, `field-text`): native select controls.
- **Media Slate** (`media-surface`, `media-text`, `media-hover`, `media-focus`,
  `media-disabled`): dark playback controls with their own visible focus treatment.

### Operational states

- `current` marks current stream/detection data; `stale` marks outdated data.
- `failed` marks interrupted capture or failed recording preparation;
  `preparing` marks unfinished clip preparation; `unavailable` marks absent media.
- The source declares additional root success/warning/error variables that are
  not used by these components. They are intentionally not promoted to tokens.

**The Written State Rule.** Every operational color accompanies a written state;
color alone never communicates stream health, capture state, or recording readiness.

## Typography

The single family stack in the frontmatter is used throughout. Arial is the
intentional workhorse face for the approved interface; Helvetica Neue and the
generic sans provide fallbacks. There is no separate display face or monospaced
font. The scale is task-based, not a fixed modular ratio.

The `headline` and `headline-small` roles identify the current page. `title`
identifies the event section; it reduces to the camera-title size below the
laptop toolbar breakpoint, while retaining its own weight and line height.
`camera-title` identifies camera cards. `body` is the global base, `navigation`
labels desktop navigation, `field` supports selects and explanatory messages,
`label` supports filters/table content, and `caption` supports secondary dates
and event counts. The table adapts to available width: compact (11px), normal
(12px), and wide (13px). These are density adjustments, not new font families.

**The Stable Time Rule.** Use tabular numerals for frame times, event time buttons,
the workspace clock, and playback time so changing digits retain alignment.

## Layout

The layout is fluid across the available viewport, without a centered maximum
content width. Desktop navigation is fixed and uses a clamped width
(`clamp(172px, 12.74vw, 208px)`); content offsets by that same width. The default
content inset is (16px), with an (80px) header. Reused spacing steps live in the
frontmatter; the CSS also uses deliberate optical adjustments, so this is not a
strict eight-pixel grid.

The implemented Overview has two equal camera columns with a (16px) gap. A single
assigned camera fills the available column, with its preview capped at (400px)
height. Event review uses a (1.35fr / 1fr) table-and-recording grid, aligned at the
top. Events uses compact camera previews (140px) and a taller scrollable history
table (320px minimum, 430px maximum). These describe the current surface, not a
required composition for every future screen.

| Viewport condition | Implemented response |
| --- | --- |
| At least 1550px | Table type grows to 13px, rows to 59px, and camera/time selects have a 132px minimum width. |
| At most 1450px | Filter labels move above fields, section title becomes 17px, and review gap reduces to 16px. |
| At most 1350px | Repeated event-type column and visible timezone suffix are hidden; recording and table padding tighten. |
| At most 1080px | Review ratio becomes 1.1fr / 1fr; filters fill their row below the heading; table type becomes 11px. |
| At most 900px | Navigation becomes a sticky horizontal bar (62px); account text hides; content loses its sidebar offset; table type returns to 12px. |
| At most 700px | Review becomes one column; table retains a 530px minimum width inside its own scroll region; event-type column returns. |
| At most 640px | Camera card padding becomes 12px; expand/close controls gain 44px targets; preview dialog margins reduce. |
| At most 540px | Camera cards stack; page title uses headline-small; content insets become 12px; filters have 40px minimum height; visible clock and timezone suffix hide. |
| At most 420px | Media control columns narrow to 36px and gaps to 4px, retaining 44px control height. |

The body minimum width is (320px). At narrow sizes, the table scroll region keeps
its keyboard focus outline and its caption retains the timezone even when the
visible suffix is hidden. The documented verification targets are desktop
(1440px), laptop (1280px), and narrow-screen fallback (390px).

## Elevation & Depth

Working panels remain flat: white against pale ground, thin borders, and a tonal
selected row provide hierarchy. Shadows distinguish the account popover and
modal dialogs from persistent content.

- Account popover: `0 8px 28px #11243c26`.
- Demo information dialog: `0 20px 70px #101f3b36`; backdrop `#10213966`.
- Expanded camera dialog: `0 24px 72px #0d19284d`; backdrop `#102033b8`.

**The Overlay Depth Rule.** Keep camera and review panels flat; reserve the
observed shadow treatments for content that overlays the workspace.

## Shapes

The frontmatter's corner scale progresses from tightly clipped previews to
controls, panels, and dialogs. Recording panels use their own intermediate
corner. Borders are thin (1px); status dots and account avatars are circular.
The camera preview clips imagery while using `object-fit: contain`, preserving
the whole scene. The default camera aspect ratio is (1.83), and playback uses
(1.876). The dark letterbox backing is part of the media surface.

**The Whole Frame Rule.** Contain camera and recording imagery within its viewport;
do not crop away the scene to fill a decorative card shape.

## Components

### Buttons and focus

Primary and secondary recovery actions use the frontmatter variants and a
(40px) minimum height. The text action clears filters; the compact icon action
reloads the workspace. Disabled reload uses reduced opacity (0.45). The demo
label is a real button that opens disclosure, not a passive status pill.

Keyboard focus uses a blue (3px) outline with (3px) offset. Navigation changes
that outline to light blue (`#9cbfff`). Media controls instead use their lighter
media-focus color at (2px) with (2px) offset. Preserve accessible names on icon
controls and the skip-to-content link. Icons are inline SVG with rounded strokes,
generally (1.8px), not text glyphs.

### Fields

Camera, time-period, and recording-part controls are native selects with visible
labels. Their default minimum height is (36px), white fill, thin outline, and
the frontmatter's control corner. The camera/time outline darkens on hover
(`#9daec4`); all use the global focus outline. There is no implemented text-input
or validation-error pattern to extend from yet.

### Navigation

Overview and Events are real hash links with a current-page state. The current
item uses solid blue and white type; hover uses the lighter navy surface. Default
links have a (47px) minimum height. Background changes use (160ms ease-out).
The account control opens an anchored popover; Escape closes it and returns focus.
Use the responsive navigation treatment in Layout.

### Camera cards

The card header combines a camera name, a text-and-dot stream state, a separate
detection state, and the last-frame time. The preview supports loading, failed
image, current, stale, offline, and paused presentations. Retained or uncertain
images are dimmed with `brightness(0.38) saturate(0.45)` and carry a centered
warning with “Current presence unknown.” Missing data never becomes evidence
that no person is present.

Expand opens a native dialog with the same full-frame treatment, explicit demo
labeling, a Close action, and focus return to the trigger. Expanded images retain
their warning state. Pausing monitoring does not remove authorized archives.

### Event table and adjacent recording

Thin row dividers and tabular timestamps support scanning. A pale blue row fill
and adjusted dividers (`#bfd1f8`) identify the selected event. Hover uses
`#f2f6fd`; row background changes take (150ms ease-out). Each event time is a
keyboard button with a pressed state; the row also responds to pointer selection.
Selection opens the recording beside the table on wide screens. Filters reset
selection and recording-part choice; an empty result explains how to recover.

**The Separate States Rule.** Capture (capturing, completed, interrupted) and
recording availability (ready, preparing, failed, unavailable) remain separate
labels; completed capture does not promise a playable clip.

### Playback

Playback uses a dark media surface and real play/pause, seek, mute, and fullscreen
controls. Control buttons are (40px × 44px) before the narrow breakpoint; the
seek track is (4px) high inside a (44px) input. Time uses tabular numerals.
Loading and media errors are written over the viewport; playback errors provide
a retry action. Pending, failed, expired, deleting, or deleted media presents an
explanation and disabled controls. Available event metadata remains visible.

The caption “Illustrative still-frame preview” stays with the sample player.
The exported design-panel media specimen shows the control's appearance only;
actual playback behavior belongs to MediaPlayer.

### Workspace states and motion

Loading uses static placeholder blocks and an accessible status message. Empty
events, no filter matches, no assignments, unavailable workspace, and ended
session each have distinct explanatory text and an appropriate recovery action.
An ended session removes camera and recording content from the demo workspace.
These fixture behaviors do not enforce server-side access.

The only authored transitions are brief navigation and table background changes.
There is no entrance animation or animated skeleton. Reduced-motion preference
sets transition/animation duration to (0.01ms), one animation iteration, and
automatic scrolling. Preserve this behavior for new interactive states.

## Do's and Don'ts

### Do:

- **Do** preserve the approved conventional navigation, restrained panels, and readable workhorse typography.
- **Do** pair operational colors with written labels and keep capture separate from recording availability.
- **Do** retain whole-frame imagery, tabular timestamps, native select labels, and visible keyboard focus.
- **Do** keep demo disclosures and illustrative-media captions visible until real integrations replace the fixtures.
- **Do** preserve event metadata when media is unavailable and explain the available recovery action.

### Don't:

- **Don't** portray stale, offline, paused, or failed monitoring as proof of no presence.
- **Don't** imply threat severity, identity, or intent from the modeled person-presence event.
- **Don't** describe frontend visibility or demo session filtering as backend authorization.
- **Don't** add permanent panel shadows or entrance choreography to the implemented operator workspace.
