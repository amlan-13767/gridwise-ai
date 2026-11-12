# IoT integration
* Topic: `gridwise/campus/<zone>/<building>/<meter>`; payload per `backend/app/iot/ingest.py::ReadingIn` plus `device_key`.
* **Auth**: each meter has a key = HMAC-SHA256(SECRET_KEY, meter_id); returned once when registering via `POST /api/iot/devices`. The broker should also require username/password (compose configures Mosquitto with `allow_anonymous false`).
* **Validation**: schema, known/active meter, source label must match the meter's registered `data_source`, future timestamps rejected, > 1 h late → `quality_status=delayed`, implausible kW/voltage → `suspect`, missing `energy_kwh` → estimated from power (`estimated`), duplicates on `(meter, timestamp)` ignored.
* **Status**: online ≤ 30 min, stale ≤ 6 h, otherwise offline (relative to the newest reading for simulated devices).
* **Run**: `python iot/mqtt/worker.py` (subscriber) and `python iot/simulators/simulator.py --mode mqtt|http` (clearly `source=simulated`). Verified locally against Mosquitto 2 with authentication and PostgreSQL.
* **ESP32**: see `iot/esp32/README.md`. Never connect development boards to mains; use certified meters installed by qualified electricians. Control of equipment is out of scope and disabled.
