# Sentinel frontend

React, TypeScript, Tailwind CSS, and Vite, using the v0 dashboard design.

```bash
pnpm install
pnpm dev
```

Open `http://localhost:5173`. `pnpm build` checks types and builds to `dist/`.

The frontend contains no sample cameras, synthetic events, demo accounts, generated alerts, or monitoring summary counters. It displays real loading, error, and empty states when camera/event data is absent. Account and camera administration controls require an actual authenticated response.

Vite proxies `/api/v1` to `SENTINEL_API_TARGET` from `.env.local`, defaulting to `http://127.0.0.1:8000`. The current frontend adapter expects `/api/v1/dashboard`; this endpoint is not implemented by the current main backend, so it shows a data loading error instead of fabricated content. Backend functionality was not changed as part of this frontend cleanup.
