# Sentinel frontend

React, TypeScript, Tailwind CSS, and Vite. All changes for this integration are frontend-only.

```bash
cd frontend
pnpm install
pnpm dev
```

Open `http://localhost:5173`. The root page is sign-in; authenticated views are `/dashboard`, `/events`, and `/settings`.

## Docker

Start the frontend from this directory:

```bash
docker compose up --build
```

Open http://localhost:5173. Compose builds the existing Dockerfile, which bundles the frontend with Vite and serves `dist/` on container port 3000. Rebuild after source changes.

Docker publishes port 5173 on `0.0.0.0`. From another machine on your network, open `http://<your-machine-ip>:5173`.

This Dockerfile serves static files and does not run Vite's development API proxy. Connecting the backend requires a reverse proxy that forwards `/api/v1` to the API on the same origin; `SENTINEL_API_TARGET` does not configure the static server.

Stop with `Ctrl+C`, then `docker compose down` to remove the container.


## Verification

- `pnpm test`: API contract, field mapping, lifecycle, URL/path containment, HTTP/cancellation, and malformed-response tests. Requires Node.js with TypeScript stripping (22.18+; Node.js 26 supported).
- `pnpm build`: TypeScript check and production bundle.
- `pnpm lint`: Oxlint.
- `pnpm preview`: serve the production build with the same API proxy.

For deployed static files, reverse-proxy `/api/v1` to the authenticated backend on the same origin and follow the backend's HTTPS cookie configuration.
