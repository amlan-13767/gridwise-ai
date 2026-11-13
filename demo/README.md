# Demonstration
`gridwise-ai-demo.mp4` (3:00, 1440x900, H.264, **no audio stream**, checked with `ffprobe`) is a Playwright recording of the **deployed production application**
(https://gridwise-ai-xi.vercel.app talking to the Render API and PostgreSQL) running on **simulated demonstration data**. Played at 1.17x speed.
It shows: landing -> administrator login (email and password fields masked) -> campus dashboard (KPIs, zone switching: Academic / Hostel / Residential, chart granularity) -> energy map ->
building analytics -> demand forecasting (24 h) -> anomaly detection -> cooling intelligence -> renewable (simulated) -> optimisation (baseline vs optimised) -> AI recommendations -> sustainability -> reports and CSV export.
The production run is read-only: no approvals, status changes or new optimisation runs are made on the live database.

Script: `frontend/e2e/record-demo.mjs`. Reproduce (credentials come from the gitignored `frontend/.env.e2e`, never from the repo):
```bash
cd frontend && BASE_URL=https://gridwise-ai-xi.vercel.app OUT_DIR=../demo/raw_prod node e2e/record-demo.mjs
ffmpeg -i ../demo/raw_prod/*.webm -an -c:v libx264 -pix_fmt yuv420p ../demo/gridwise-ai-demo.mp4
```
Without `E2E_EMAIL`/`E2E_PASSWORD` the script drives a local stack (API :8000, web :3000) using the local demo accounts. Screenshots: `demo/screenshots/`.
