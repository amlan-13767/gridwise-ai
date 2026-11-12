# Database
Tables: users, zones, buildings, building_areas, meters, energy_readings, weather_readings, occupancy_records, renewable_assets, renewable_readings, forecasts, anomalies, recommendations, optimization_runs, energy_tariffs, model_versions, notifications, audit_logs (+ `settings`).
* Unique constraints: `(meter_id, timestamp)` on readings (duplicate protection), `(building_id, timestamp, detection_method)` on anomalies, building/meter codes.
* Indexes on `energy_readings.timestamp`, forecast timestamps, anomaly timestamps, FK columns.
* No hard deletes: buildings/meters are deactivated; `building_areas.building_id` is `RESTRICT`.
* Additions beyond the brief: `energy_readings.cooling_load_kw/indoor_temperature`, `buildings.location_is_approximate`, `anomalies.category/baseline_info`, `recommendations.measured_saving_kwh/source_key`.
* Migrations: `alembic upgrade head` (initial revision included). Verified on SQLite and PostgreSQL 16. TimescaleDB hypertables are **not** configured (plain PostgreSQL); the schema is compatible if you add them.
