# Deployment

| piece | where | notes |
|---|---|---|
| Frontend | Vercel (Git-connected; **Root Directory must be `frontend`**: with the repo root a build fails with `ENOENT package.json`) team `amlan-prateek-pandas-projects`, project `gridwise-ai` → https://gridwise-ai-xi.vercel.app | needs `NEXT_PUBLIC_API_URL` (public Config variable) at **build** time: redeploy after changing it |
| API | Render Web Service `gridwise-api` (Docker, **Free** plan) → https://gridwise-api-9ypw.onrender.com (`/docs`, `/api/health`) | free instances spin down after ~15 min idle; the first request can take up to a minute |
| Database | Render PostgreSQL `gridwise-db` (free) | free Render Postgres databases expire after a limited period; back up or upgrade before relying on it |
| MQTT broker / workers | not deployed (needs a persistent host); `docker compose` locally | never run these in Vercel serverless functions |

## What happens when the API container starts
`python -m backend.app.bootstrap && uvicorn …` (see `backend/Dockerfile`):
1. Waits for PostgreSQL (10 retries) and fails fast with a clear message if `DATABASE_URL` is wrong (password masked).
2. Runs Alembic migrations. If the tables were created earlier by `create_all` (the first Render deploy did this), the schema is **adopted with `alembic stamp head`**, never recreated; no data is touched.
3. Creates the first Super Administrator from environment variables (idempotent, see below).
4. If `SEED_DEMO_DATA=true` **and** the database has no completed seed, loads the SIMULATED campus dataset (35 buildings, 302k readings), model inference (forecasts, anomalies, optimisation run, recommendations) and writes a `seed_complete` marker. A half-finished seed (e.g. an out-of-memory kill) is detected by the missing marker and redone; seeding refuses if any non-simulated data exists. Seeding is skipped on every later start.
`ENVIRONMENT=production` forbids a SQLite fallback and disables `create_all`.

## Creating the first Super Administrator (owner action, no code changes)
Render dashboard → `gridwise-api` → **Environment** → add (as secrets):
* `GRIDWISE_ADMIN_EMAIL` = your email
* `GRIDWISE_ADMIN_PASSWORD` = a strong password, at least 12 characters, chosen by you

Save (Render redeploys). On start the log shows `created super administrator <email>`. Rules: if that email already exists nothing changes and **the password is never reset**; the password is bcrypt-hashed and never logged. After your first login you may delete `GRIDWISE_ADMIN_PASSWORD` from the dashboard. Create further users in the app (User Management). To reset a lost password: delete the user's row or use a different `GRIDWISE_ADMIN_EMAIL`. Demo accounts (`*@gridwise.demo`) are **not** created in production (`SEED_DEMO_USERS` defaults to false).
Local equivalent: `GRIDWISE_ADMIN_PASSWORD=… python -m backend.app.cli create-admin --email you@org`.

## Environment variables
API (Render): `DATABASE_URL` (internal URL of `gridwise-db`), `SECRET_KEY` (generated), `FRONTEND_URL=https://gridwise-ai-xi.vercel.app`, `ENVIRONMENT=production`, `DEMO_MODE=true`, `SEED_DEMO_DATA=true`, `GRIDWISE_ADMIN_EMAIL`, `GRIDWISE_ADMIN_PASSWORD`.
Frontend (Vercel): `NEXT_PUBLIC_API_URL=https://gridwise-api-9ypw.onrender.com` only. Never put secrets in `NEXT_PUBLIC_*`.
CORS accepts `FRONTEND_URL`, `http://localhost:3000` and `https://gridwise-ai*.vercel.app`.

Local full stack: `docker compose up --build`.
