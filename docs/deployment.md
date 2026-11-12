# Deployment
| piece | where | status |
|---|---|---|
| Frontend | Vercel team `amlan-prateek-pandas-projects`, project `gridwise-ai` (deploy from `frontend/`, root directory `frontend` if Git-connected) | **deployed**: https://gridwise-ai-xi.vercel.app |
| API | Docker host (Render blueprint in `render.yaml`, Railway, Fly…) with `backend/Dockerfile` | **not deployed** (no host credentials available) |
| Database | managed PostgreSQL (`DATABASE_URL`), run `alembic upgrade head` then `python scripts/seed_database.py` for demo data | not provisioned |
| MQTT / workers | `docker compose` (Mosquitto + `iot/mqtt/worker.py` + Celery) on a persistent host, never on Vercel serverless | verified locally only |

Steps once an API host exists: set on the API `DATABASE_URL`, `SECRET_KEY`, `FRONTEND_URL=https://gridwise-ai-xi.vercel.app`; on Vercel set `NEXT_PUBLIC_API_URL=<api url>` (and optionally `NEXT_PUBLIC_DEMO_MODE=true`, `NEXT_PUBLIC_DEMO_PASSWORD="…"` to show demo-login buttons; these are public values) and redeploy with `vercel --prod`. CORS already allows `https://gridwise-ai*.vercel.app`.
Local full stack: `docker compose up --build` (API + Postgres + Redis + Mosquitto + workers).
