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

The browser calls the API directly on the same hostname and protocol at port 8000. For example, opening `http://homie:5173` uses `http://homie:8000/api/v1`. This applies to login, event requests, and authenticated recordings. No proxy is used.

In `backend/.env`, allow the exact frontend origin you open in your browser, then restart the backend:

```dotenv
CORS_ORIGINS=["http://localhost:5173", "http://homie:5173"]
```

Replace `homie` with your actual Tailscale/private hostname or IP. Use the same hostname and protocol for both frontend and backend so session cookies work across their different ports. The backend must listen on `0.0.0.0:8000` to accept network connections.

If the API uses another address or port, set `VITE_API_ORIGIN` in `frontend/.env` (Docker Compose) or `frontend/.env.local` (native Vite):

```dotenv
VITE_API_ORIGIN=http://your-server:8000
```

Use an origin without `/api/v1`. Vite embeds this public address at build time, so rebuild Docker after changing it; restart Vite during native development. The variable contains no password or worker key. See [Vite's environment-variable documentation](https://vite.dev/guide/env-and-mode).

Stop with `Ctrl+C`, then `docker compose down` to remove the container.


## Verification

- `pnpm test`: API contract, field mapping, lifecycle, URL/path containment, HTTP/cancellation, and malformed-response tests. Requires Node.js with TypeScript stripping (22.18+; Node.js 26 supported).
- `pnpm build`: TypeScript check and production bundle.
- `pnpm lint`: Oxlint.
- `pnpm preview`: serve the production build with direct API access.

For private production, set the allowed frontend origin in the backend environment and rebuild with `VITE_API_ORIGIN` if the API address differs. Use HTTPS consistently and enable `SESSION_COOKIE_SECURE=True` when serving the API over HTTPS.
