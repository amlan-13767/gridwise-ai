"""Dataset validation: schema, ranges, source labels, duplicates, interval regularity."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pandas as pd
from ml.common import load_readings

REQ = "timestamp building_id zone_type meter_id energy_consumption_kwh power_demand_kw voltage current temperature humidity occupancy cooling_load_kw solar_generation_kw wind_generation_kw electricity_tariff is_holiday is_weekend data_source".split()
d = load_readings(); errs = []
errs += [f"missing column {c}" for c in REQ if c not in d]
if set(d.data_source) != {"simulated"}: errs.append("data_source must be 'simulated' only")
if d.duplicated(["building_id", "timestamp"]).any(): errs.append("duplicate building/timestamp rows")
if d.power_demand_kw.le(0).any(): errs.append("non-positive power")
if not d.voltage.between(200, 260).all(): errs.append("voltage out of range")
if d.solar_generation_kw.lt(0).any(): errs.append("negative solar")
if not ((d.energy_consumption_kwh - d.power_demand_kw * 0.25).abs() < 1e-2).all(): errs.append("kWh != kW*0.25h")
steps = d.sort_values("timestamp").groupby("building_id").timestamp.diff().dropna().unique()
if len(steps) != 1 or steps[0] != pd.Timedelta("15min"): errs.append(f"irregular intervals {steps}")
print(f"rows={len(d):,} buildings={d.building_id.nunique()} range={d.timestamp.min()}..{d.timestamp.max()}")
print("VALID" if not errs else "INVALID: " + "; ".join(errs)); sys.exit(1 if errs else 0)
