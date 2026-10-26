# Dark operator workspace redesign

The user rejected the prior conventional dashboard as generic and asked for a modern, attractive, complete frontend based on the app specification and actual backend APIs. Dark mode and Tailwind CSS are explicit requirements; shadcn may supply accessible component primitives. Operators work in a dim room, typically with one or two storage-room cameras on desktop/laptop. Monitoring and event review remain equally important.

The previous visual system is an anti-reference. Its excessive framing, oversized two-item sidebar, tiny labels, and one-camera letterboxing are not requirements. Preserve product truth, access rules, event semantics and functioning controls.

## Grounded systems

1. Photographic contact sheet: footage is the content; compact labels and a selected-frame inspector support quick comparison.
2. Dispatch shift log: dated activity rows, explicit state and stable selection support repeated operator handovers.
3. Digital asset review studio: a neutral workspace separates inspection from the collection without adding administration chrome.
4. Industrial operator console: restrained panel boundaries and written state make current and unknown conditions clear.
5. Warehouse pick-list register: aligned location references and reliable scanning suit the storage-room context.
6. Architectural drawing review: a large visual field and a precise side inspector keep context while investigating details.
7. Broadcast source/record desk: live sources and recorded playback remain distinct and visible together, with an event queue below.

Seed 2c7fa1a5 assigned index 7. This becomes the dark Review Studio direction. The contact-sheet system is the alternate pick. Both use the user's dark-mode constraint. A dark conventional dashboard remains available as the category-standard exit.

## Catalog challenger evaluation

Each was fused with actual camera/events content before comparison. All six lose both audience identification and product clarity relative to the source/record desk, so they are declined as whole systems.

- Midnight transit diagram: event navigation as routes/transfers would imply relationships the backend does not record. Keep persistent orientation while inspecting an item.
- Monochrome product marketing: claim/proof sections interrupt a repeated monitoring task. Keep a disciplined neutral ramp and scarce accent.
- Lexicon shoulder and plate: alphabetic entries and printed-mark interaction do not fit timed event review. Keep a consistent, well-proportioned inspector margin.
- Star atlas: chart coordinates, magnitude and panning imply unsupported camera geometry. Keep visual prominence tied to the selected subject.
- Crouwel grid specimen: construction-grid and letterform controls have no operational function here. Keep a strict alignment grid without decorative grid lines.
- Darkroom exposure sheets: filtration, cross-hatched conflict and overlapping sheets invent states and obscure footage. Keep image-neutral surroundings and clear source/record distinction.

## Implementation discovery

Canonical FastAPI exposes GET /health. A separate prototype exposes event collection/detail/create/delete and filename-based video retrieval, without authentication, camera configuration, or live transport APIs. Frontend capabilities must describe those differences honestly. Detailed reports: /tmp/sentinel-api-inventory.md and /tmp/sentinel-frontend-scope.md.
