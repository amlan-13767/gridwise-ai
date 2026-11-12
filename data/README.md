# Data

`data/synthetic/` is **generated** (gitignored): `python scripts/generate_data.py` (seed 42, reproducible).
Every row has `data_source = simulated`. **None of it is a real NIT Rourkela measurement.**

## Dictionary (`readings.csv.gz`, 15-minute rows)
| column | meaning |
|---|---|
| timestamp | UTC interval start |
| building_id, zone_type, meter_id | simulated building code (ACD-xx / HST-xx / RES-xx), zone, virtual meter |
| energy_consumption_kwh, power_demand_kw | interval energy / average power |
| voltage, current | simulated electrical values |
| temperature, humidity, cloud_cover, irradiance | simulated outdoor weather |
| indoor_temperature | simulated indoor temperature (cooled ≈ 24 °C) |
| occupancy | simulated headcount (academic = schedule-based, hostel/residential = estimated) |
| cooling_load_kw | HVAC share of power |
| solar_generation_kw, wind_generation_kw | simulated solar (4 academic buildings, 400 kWp total); wind always 0 |
| electricity_tariff | assumed ₹/kWh slab (peak 18-22h) |
| is_holiday, is_weekend | calendar flags (demo holiday list) |
| injected_anomaly | ground-truth label for evaluating detectors (not available in real data) |
| data_source | always `simulated` |

## Assumptions
10 academic, 20 hostel, 5 residential buildings (parameters, **not** a real inventory); 90 days from 2026-08-15;
academic load follows 08:30-17:30 working hours (weekends/holidays ≈ 35%); library evenings; hostels peak ≈19:30 plus mess/pump loads;
residential morning + evening peaks; solar follows a daylight curve damped by an AR(1) cloud process; 2-4 random anomalies per
building plus three deterministic demo anomalies; two academic buildings (ACD-03, ACD-05) deliberately run cooling outside
operating hours so the cooling module has something to find. Validate with `python scripts/validate_data.py`.
