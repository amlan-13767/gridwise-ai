"""Offline analysis report from the CSV (no database): totals, zone comparison, intensity, cost, renewable share, saving candidates."""
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from ml.common import load_readings, load_buildings, REPORTS
from ml.anomaly_detection.detect import detect
d = load_readings(); b = load_buildings().set_index("building_id")
d["cost"] = d.energy_consumption_kwh * d.electricity_tariff
days = (d.timestamp.max() - d.timestamp.min()).days + 1
z = d.groupby("zone_type").agg(kwh=("energy_consumption_kwh", "sum"), cost=("cost", "sum"))
camp = d.groupby("timestamp").power_demand_kw.sum()
h, a = detect(d)
rep = dict(data_source="SIMULATED", days=days, total_kwh=d.energy_consumption_kwh.sum(), avg_daily_kwh=d.energy_consumption_kwh.sum() / days,
           peak_kw=camp.max(), estimated_cost_inr=d.cost.sum(), zone=z.round(0).to_dict("index"),
           renewable_share_pct=d.solar_generation_kw.sum() * .25 / d.energy_consumption_kwh.sum() * 100,
           kwh_per_m2=(d.groupby("building_id").energy_consumption_kwh.sum() / b.floor_area).describe().round(2).to_dict(),
           anomaly_flags=len(a), cooling_kwh=d.cooling_load_kw.sum() * .25)
REPORTS.mkdir(exist_ok=True); (REPORTS / "analysis_report.json").write_text(json.dumps(rep, indent=1, default=float)); print(json.dumps(rep, indent=1, default=float))
