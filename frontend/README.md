# Sentinel frontend

React, TypeScript, Tailwind CSS, and Vite, using the v0 dashboard design.

```bash
pnpm install
pnpm dev
```

Open `http://localhost:5173`. `pnpm build` checks types and builds to `dist/`.

## Sign-in page

The root URL opens the sign-in page. `/login` is also available directly. Successful sign-in opens `/dashboard`; unauthorized requests, ended sessions, and successful logout return to `/login`.

The dashboard's user icon opens **Settings** and **Log out**. `/settings` shows the account information returned by the API and a browser-local **Reduce animations** preference. Account editing stays with the API's administration workflows; this page does not simulate saving profile changes.

The form follows `backend/app/db/schema.sql` and the user/session models:

- Email is the login identity: a trimmed, lowercase address of at most 254 characters.
- Password is submitted as entered. The backend hashes/verifies it; the database specifies Argon2id for stored password hashes. The sign-in form does not impose a new password-length policy.
- `display_name` is profile data. Roles (`admin` and `user`) and `is_active` are controlled by the backend, not selected during sign-in.
- Sessions use an opaque token in a protected cookie. The frontend does not store passwords or session tokens in browser storage.

The existing frontend auth contract is `POST /api/v1/session` with JSON `{ "email": "...", "password": "..." }`. A successful response must establish the session cookie. The frontend then loads the protected dashboard; `DELETE /api/v1/session` signs out. These endpoints still need implementation on the API branch. The UI provides validation, password visibility, pending states, and friendly errors without accepting demo credentials.

The frontend contains no sample cameras, synthetic events, demo accounts, generated alerts, or monitoring summary counters. It displays real loading, error, and empty states when camera/event data is absent. Account and camera administration controls require an actual authenticated response.

Vite proxies `/api/v1` to `SENTINEL_API_TARGET` from `.env.local`, defaulting to `http://127.0.0.1:8000`. The current frontend adapter expects `/api/v1/dashboard`; this endpoint is not implemented by the current main backend, so it shows a data loading error instead of fabricated content. Backend functionality was not changed as part of this frontend cleanup.
