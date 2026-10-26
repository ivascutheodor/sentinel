# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Sentinel serves security operators at a single storage-room installation. The user confirmed this
audience and setting during initialization. The domain distinguishes administrators
from ordinary users with access to assigned cameras.

## Product Purpose

Help operators monitor camera zones for person presence and review the associated
recorded events. The core mechanism is person detection within a configured region,
with event clips that include footage before and after the detected presence.

## Operating Context

- The web application lives in `frontend/`, with a Python API in `backend/` and
  camera processing in `workers/`.
- The intended workflow is to configure cameras and detection regions, monitor
  activity, and review events and available recordings. Administrators manage
  camera assignments and installation settings.
- The database models RTSP cameras. The worker prototype can also read a local
  video file or camera device for development.
- Operators primarily use a desktop monitor or laptop and usually monitor one
  camera, with two the current expected maximum. Live monitoring and recent-event
  review have equal priority.
- The React/Vite frontend implements Overview and Events with labeled demo data,
  camera previews, filters, event selection, and illustrative recording playback.
  It is not yet connected to authenticated camera or media APIs.

## Capabilities and Constraints

### Access rules to preserve

The user explicitly identified access rules as a durable requirement. Preserve
the following contract recorded in the database models:

- Active administrators can access all cameras. Active ordinary users can access
  only assigned cameras and those cameras' events and clips.
- The backend must authorize and audit camera access grants and revocations.
  Revoking access must terminate affected active streams.
- Account deactivation or role changes must invalidate affected sessions and live
  authorizations. Historical records retain their account references.
- Disabling camera monitoring does not by itself revoke access to its archive.
- Playback must be authorized by the backend; a server filesystem path is not a
  browser playback URL. UI visibility alone does not enforce access.

These are requirements to retain and implement, not claims that the current
prototype already enforces them.

### Recording and event semantics

- The worker detects people inside a polygonal region and requires sustained
  presence before starting a recording. Saved footage excludes the detection
  overlays shown in the worker's preview.
- Person presence is the modeled event type. Detection does not establish a
  person's identity, intent, or threat level.
- An event's capture state and a clip's availability are separate. A completed
  event does not imply that every clip is ready to play.
- The database contract retains event metadata after video retention and
  distinguishes pending, ready, failed, deleting, and deleted clips.

### Implementation maturity

- The documented FastAPI entry point, `backend/app/main.py`, currently exposes
  only a health endpoint. A separate prototype in `backend/server/server.py`
  provides in-memory event operations and local video serving.
- SQLAlchemy models and an initial PostgreSQL migration exist. Authentication,
  authorized operator workflows, and integration with the web UI remain work to do.
- `backend/README.md` identifies unfinished database protections, including audit
  immutability, lifecycle transitions, immutable event configuration snapshots,
  automatic update timestamps, and settings initialization.
- Worker and database recording defaults differ. Neither establishes a confirmed
  deployment policy for timing or retention.

## Brand Commitments

The existing product name is Sentinel. Product-specific voice and identity assets
are not established; React/Vite starter assets are not Sentinel brand commitments.

For the operator interface, the user selected a conventional security dashboard:
a familiar sidebar, camera cards, and an event table with adjacent playback.
Preserve that preference rather than introducing an unfamiliar visual metaphor.

## Evidence on Hand

- `backend/app/db/schema.sql` and `backend/app/db/models/`: domain structure,
  intended access rules, and lifecycle contracts. Comments can describe behavior
  that is not yet implemented.
- `backend/README.md`: supported development workflow and database scope limits.
- `workers/src/monitor.py`, `workers/src/recorder.py`, and `workers/src/zone.py`:
  detection and recording prototype.
- `workers/tests/test_recorder.py`: existing cases for brief presence, pre/post
  recording, and saving an unfinished clip when closing the recorder.
- No customer testimonials, deployment results, or measured detection accuracy
  were established during initialization. Do not invent them.

## Product Principles

1. Preserve camera-scoped access throughout monitoring, history, and playback.
2. Help operators move from observed presence to the corresponding recording.
3. Describe detection results and recording availability accurately, including
   incomplete or failed states.
4. Keep implemented capabilities distinct from intended behavior when presenting
   the product.

## Open Decisions

- Deployment location, remote access, and storage requirements, including whether
  the installation must operate entirely locally.
- Final retention policy and recording timings.
- Notification requirements beyond the approved monitoring and review workspace.
- Deployment interface language and product-specific accessibility needs; the
  current interface is English with keyboard access and a narrow-screen fallback.
- Success measures and any positioning claims beyond the documented mechanism.
