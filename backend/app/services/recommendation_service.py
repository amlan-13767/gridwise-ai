import datetime as dt
import pandas as pd
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..models.tables import Anomaly, Recommendation, Building, Zone, OptimizationRun, Forecast
from . import common, cooling_service

SEV_PRI = {"critical": "high", "high": "high", "medium": "medium", "low": "low"}


def _add(db, key, **kw):
    if db.scalar(select(Recommendation.id).where(Recommendation.source_key == key)):
        return 0
    db.add(Recommendation(source_key=key, **kw)); return 1


def generate(db: Session):
    now = pd.Timestamp(common.data_now(db)); tariff = common.get_setting(db, "electricity_tariff", 6.0)
    bmap = common.building_map(db); n = 0
    since = (now - pd.Timedelta(days=14)).to_pydatetime()
    # 1) anomalies -> deterministic rule-based alerts (investigation leads, not confirmed waste)
    rows = db.scalars(select(Anomaly).where(Anomaly.timestamp >= since, Anomaly.severity.in_(["medium", "high", "critical"]))).all()
    by = {}
    for a in rows:
        by.setdefault((a.building_id, a.category), []).append(a)
    for (bid, cat), L in by.items():
        b, zt = bmap[bid]
        excess = sum(max(0, a.observed_value - a.expected_value) for a in L)  # kW-hours (hourly buckets)
        worst = max(L, key=lambda a: a.deviation)
        title = ({"overnight_consumption": f"Review overnight electricity usage in {b.building_name}",
                  "sudden_load_increase": f"Investigate sudden load increase in {b.building_name}"}
                 .get(cat, f"Investigate unusually high consumption in {b.building_name}"))
        n += _add(db, f"anom:{bid}:{cat}", building_id=bid, title=title,
                  description=f"{len(L)} flagged hour(s) in the last 14 days; peak deviation {worst.deviation:.0f}% above the comparable-hours baseline. "
                              "This is an anomaly, not confirmed wastage; cause must be verified on site.",
                  recommendation_type="rule_based_alert", category=cat, priority=SEV_PRI[worst.severity],
                  estimated_energy_saving_kwh=round(excess, 1), estimated_cost_saving=round(excess * tariff, 0),
                  confidence="medium", recommended_action="Inspect the building's loads/schedules during the flagged window and confirm whether the usage was needed.",
                  supporting_evidence=dict(zone=zt, flagged_hours=len(L), worst_timestamp=worst.timestamp.isoformat() + "Z",
                                           observed_kw=round(worst.observed_value, 1), expected_kw=round(worst.expected_value, 1),
                                           method=worst.detection_method, data_source="simulated"))
    # 2) cooling schedule review (optimizer-backed -> ai_generated)
    for c in cooling_service.analysis(db, days=14):
        if c["schedule_flag"]:
            opt = cooling_service.optimize(db, c["building_id"])
            n += _add(db, f"cool:{c['building_id']}", building_id=c["building_id"],
                      title=f"Review cooling schedule in {c['building']}",
                      description=f"Cooling ran for {c['after_hours_cooling_hours']} hours outside operating hours with no reported occupancy "
                                  f"({c['after_hours_cooling_kwh']:.0f} kWh in 14 days). Occupancy is schedule-based, so confirm actual use first.",
                      recommendation_type="ai_generated", category="cooling", priority="high" if c["after_hours_cooling_kwh"] > 400 else "medium",
                      estimated_energy_saving_kwh=round(opt.get("energy_saving_kwh", 0) * 14, 1),
                      estimated_cost_saving=round(opt.get("cost_saving", 0) * 14, 0), confidence="medium",
                      recommended_action="Align HVAC schedule with confirmed occupancy; keep comfort and equipment limits for occupied hours.",
                      supporting_evidence=dict(zone=c["zone"], after_hours_kwh=round(c["after_hours_cooling_kwh"], 1),
                                               hvac_share_pct=round(c["hvac_share_pct"], 1), basis=c["assumptions"], data_source="simulated"))
    # 3) load shifting from latest optimization run
    run = db.scalars(select(OptimizationRun).where(OptimizationRun.status.in_(["pending_review", "approved"])).order_by(OptimizationRun.id.desc())).first()
    if run and run.result.get("status") == "optimal":
        r = run.result
        n += _add(db, f"opt:{run.id}", building_id=None, title="Consider shifting eligible pump and non-critical loads off the evening tariff peak",
                  description=f"Optimizer (run #{run.id}) estimates a daily cost difference of INR {r['cost_difference']:.0f} and a peak change of "
                              f"{r['peak_reduction_kw']:.1f} kW versus baseline, by moving only flexible loads within permitted windows.",
                  recommendation_type="ai_generated", category="load_shifting", priority="medium",
                  estimated_energy_saving_kwh=0.0, estimated_cost_saving=round(r["cost_difference"], 0), confidence="medium",
                  recommended_action="Review and, if operationally acceptable, adjust pump / equipment schedules. No controls are changed automatically.",
                  supporting_evidence=dict(optimization_run=run.id, shifts=[dict(load=s["load"], moved_kwh=s["moved_kwh"]) for s in r["shifts"]], data_source="simulated"))
    # 4) forecast peak warning
    fc = db.scalars(select(Forecast).where(Forecast.scope == "campus", Forecast.horizon == "24_hours")).all()
    if fc:
        pk = max(fc, key=lambda f: f.predicted_demand_kw)
        hist = common.hourly_frame(db, (now - pd.Timedelta(days=30)).to_pydatetime())
        camp = hist.groupby("ts").y.sum(); p95 = float(camp.quantile(.95))
        if pk.predicted_demand_kw > p95:
            n += _add(db, f"peak:{pk.forecast_timestamp:%Y%m%d}", building_id=None, title="Expected campus peak demand above the 30-day 95th percentile",
                      description=f"Forecast peak {pk.predicted_demand_kw:.0f} kW at {pk.forecast_timestamp:%H:%M} UTC vs 95th percentile {p95:.0f} kW.",
                      recommendation_type="rule_based_alert", category="peak_demand", priority="medium", estimated_energy_saving_kwh=None,
                      estimated_cost_saving=None, confidence="medium", recommended_action="Review deferrable loads during the forecast peak window.",
                      supporting_evidence=dict(forecast_kw=pk.predicted_demand_kw, p95_kw=p95, data_source="simulated"))
    # 5) rising energy intensity
    hist = common.hourly_frame(db, (now - pd.Timedelta(days=28)).to_pydatetime())
    mid = now - pd.Timedelta(days=14)
    for bid, g in hist.groupby("building_id"):
        b, zt = bmap[bid]
        if not b.floor_area:
            continue
        a, p = g[g.ts >= mid].y.sum(), g[g.ts < mid].y.sum()
        if p > 0 and a / p > 1.10 and zt != "Residential":
            n += _add(db, f"int:{bid}", building_id=bid, title=f"Review rising energy intensity in {b.building_name}",
                      description=f"Energy over the last 14 days is {(a/p-1)*100:.0f}% above the previous 14 days ({a/b.floor_area:.1f} kWh/m2). Weather and occupancy may explain part of this.",
                      recommendation_type="rule_based_alert", category="intensity", priority="low", estimated_energy_saving_kwh=None,
                      estimated_cost_saving=None, confidence="low", recommended_action="Compare against weather-normalised baseline and check new equipment.",
                      supporting_evidence=dict(change_pct=round((a / p - 1) * 100, 1), data_source="simulated"))
    db.commit()
    return n
