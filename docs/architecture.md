# Architecture

```
ESP32 / certified meters ──MQTT──► Mosquitto ──► iot/mqtt/worker.py ─┐
simulator (source=simulated) ──HTTP /api/iot/ingest─────────────────┤  validate · authenticate · de-duplicate
                                                                     ▼
Next.js (Vercel) ──REST+JWT──► FastAPI ──► SQLAlchemy ──► PostgreSQL (SQLite for local dev)
                                  │                             ▲
                                  ├── services/ (analytics, forecast, anomaly, cooling, optimisation, recommendations)
                                  ├── ml/ saved models (joblib)  ◄── offline training: scripts/train_models.py
                                  └── optimization/ (OR-Tools GLOP, SciPy HiGHS)       Celery+Redis: hourly inference jobs
```
* **Frontend** (`frontend/`): Next.js App Router, TypeScript, Tailwind, Recharts, TanStack Query, React Hook Form + Zod, Leaflet. shadcn-style primitives are hand-written in `components/ui` (the shadcn CLI was not used).
* **Backend** (`backend/app`): `api/` routers, `models/tables.py` (19 tables = the 18 specified + `settings`), `services/`, `iot/ingest.py`.
* **Safety**: monitoring and recommendation only. No endpoint writes to equipment. Optimisation runs have `mode="recommendation"` and need human approval.
* **Roles**: `super_admin`, `energy_manager`, `zone_manager` (single assigned zone), `viewer` (no building-level residential data). JWT bearer tokens (8 h), bcrypt hashes, admin-only registration, CLI for the first admin, audit log for writes/logins.
* **Time**: stored UTC, shown in IST (Asia/Kolkata).
