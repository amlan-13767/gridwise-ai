# GRIDWISE AI: Smart Campus Energy Intelligence & Optimization Platform
**Monitor. Predict. Optimize. Save.** A decision-support platform for the Academic, Hostel and Residential zones of a campus (NIT Rourkela use case).

> **Everything in the demo is SIMULATED.** Buildings, meters, solar assets, occupancy, weather and map positions are generated sample data, not the real NIT Rourkela inventory or measurements. Model accuracy is measured on that simulated data only. The platform **monitors and recommends; it never controls equipment.** Savings are *estimates* unless a recommendation is explicitly recorded as MEASURED.

* Repository: https://github.com/amlan-13767/gridwise-ai (public)
* Live frontend: https://gridwise-ai-xi.vercel.app (Vercel) · API: https://gridwise-api-9ypw.onrender.com (Render free tier, PostgreSQL). The free API sleeps when idle: the first request after inactivity can take ~1 minute.
* **First login**: there are no built-in production accounts. The owner creates the first Super Administrator by setting `GRIDWISE_ADMIN_EMAIL` and `GRIDWISE_ADMIN_PASSWORD` in the Render environment (see `docs/deployment.md`).
* Silent demo video: [`demo/gridwise-ai-demo.mp4`](demo/gridwise-ai-demo.mp4) (local app, simulated data, no audio)

## Problem and solution
Campuses face unoccupied-space consumption, evening hostel peaks, inefficient cooling, no unified view, undetected anomalies, solar/demand mismatch and rising peak cost. GRIDWISE AI unifies metering data and provides demand forecasting, anomaly detection, cooling analysis/optimisation, solar forecasting, load-shifting optimisation, explainable recommendations, carbon estimates, reports and IoT ingestion.

## Zones
Academic (departments, labs, library, admin; schedule-based occupancy), Hostel (per-occupied-bed normalisation; no per-student data), Residential (aggregate clusters only; viewers cannot see building-level residential data). Buildings/zones/meters are database records managed in the UI (Settings → Campus infrastructure, IoT Devices).

## Features (all pages are wired to the API)
Landing · Login · Campus dashboard (8 KPIs, filters, granularity, zone cards, alerts) · Energy map (Leaflet/OSM, status colours, details panel) · Academic / Hostel / Residential dashboards · Building details · Demand forecasting (+ evaluation tables) · Anomalies (review workflow) · Cooling intelligence (analysis + optimiser) · Renewable (simulated solar, forecast, surplus/deficit) · Optimization engine (OR-Tools, approve) · Recommendations (approve/reject/investigate/implement/measured) · Sustainability · Reports + CSV export · IoT devices · Model management (promotion requires admin) · Users · System configuration + audit log.
Not implemented: PDF reports, Local Outlier Factor, a reinforcement-learning cooling environment, wind (schema only), battery, live weather, OpenAI explanations, real hardware, TimescaleDB hypertables.

## Stack
Next.js 16 · React · TypeScript · Tailwind 4 · Recharts · TanStack Query · React Hook Form · Zod · Leaflet · FastAPI · SQLAlchemy · Alembic · Pydantic · pandas · scikit-learn · XGBoost · LightGBM · OR-Tools · SciPy · paho-mqtt · Celery/Redis · Mosquitto · PostgreSQL · Docker · Playwright · Pytest · Ruff.

## Quick start
```bash
git clone https://github.com/amlan-13767/gridwise-ai && cd gridwise-ai
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python scripts/generate_data.py          # simulated dataset (seed 42)
python scripts/validate_data.py
python scripts/train_models.py           # trains + evaluates; writes ml/models and ml/reports
export DEMO_PASSWORD='Gridwise#Demo1'    # optional: demo accounts' password (default shown)
python scripts/seed_database.py          # SQLite gridwise.db with demo accounts (admin@/manager@/zone@/viewer@gridwise.demo)
uvicorn backend.app.main:app --port 8000
# second terminal
cd frontend && cp ../.env.example .env.local   # then keep NEXT_PUBLIC_* lines; quote values containing '#'
npm install && npm run dev                      # http://localhost:3000
```
Production start-up (`python -m backend.app.bootstrap`) runs migrations, creates the first admin from env vars and optionally loads the simulated dataset; see `docs/deployment.md`. Production never creates demo accounts. `docker compose up --build` starts API + Postgres + Redis + authenticated Mosquitto + workers.

## Tests
```bash
pytest -q                      # 40 tests: API/RBAC/ingestion/reports, ML (reproducibility, split, leakage, serialisation), optimisation
cd frontend && npm run build && npx playwright test    # 7 E2E specs (+ screenshots) against :3000/:8000
cd frontend && npx tsc --noEmit && npx eslint .
```
Backend tests use a separate SQLite database seeded from the simulated dataset. Item 25 "production API communication" is covered only locally (the frontend↔API round trip is exercised by Playwright); no production API exists yet.

## Model evaluation (simulated data)
See `docs/ml_pipeline.md` and `ml/reports/*.json`. Summary: 1 h and 24 h forecasts beat the hourly-average baseline (RMSE −40 % / −21 %); the 7-day model has better MAE (−33 %) but **worse RMSE (+4 %)** than the baseline. Solar RF RMSE 1.60 kW vs baseline 11.98 kW; anomaly detector precision 96 % / recall 94 % against injected anomalies.

## Cooling, renewables, optimisation
* **Cooling**: after-hours = outside configured operating hours (or weekend) with occupancy < 5 % of capacity; savings from a SciPy LP (occupied hours fully served, setback floor 25 % otherwise, server rooms never reduced). Estimates against the observed baseline, never guaranteed.
* **Solar**: simulated 400 kWp across four academic buildings; wind and batteries are not assumed.
* **Optimiser**: OR-Tools GLOP shifts only flexible loads (hostel pumps, approved non-critical equipment) inside permitted windows; reports baseline vs optimised cost and peak; infeasible scenarios are reported.

## IoT
MQTT/HTTP ingestion with per-device keys, validation, duplicate handling and quality flags (`docs/iot_integration.md`). A simulator publishes `source=simulated` messages. No real hardware was connected.

## Screenshots
`demo/screenshots/` (landing, dashboard, map, hostel, forecast, anomalies, cooling, renewable, optimisation, recommendations, sustainability).

## Future real-campus integration
Obtain authorisation and real meter/occupancy/timetable/weather data; verify building coordinates; register real meters (`data_source=real`); retrain and re-evaluate models on real history; set official tariff and emissions factor; add privacy review before any household-level data; engineering/safety review before any control capability.
