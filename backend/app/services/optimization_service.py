import datetime as dt
import numpy as np, pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session
from optimization.load_scheduling import optimize_load_shifting
from ..models.tables import Forecast, EnergyTariff, OptimizationRun, Building, Zone
from . import common

IST = pd.Timedelta(hours=5, minutes=30)
PUMP_KW = 6.0  # SIMULATED per-hostel pump rating (registry assumption)


def tariff_by_hour(db):
    ts = db.scalars(select(EnergyTariff)).all()
    out = [common.get_setting(db, "electricity_tariff", 6.0)] * 24
    for t in ts:
        for h in range(t.start_hour, t.end_hour):
            out[h] = t.rate_per_kwh
    return out


def _series(rows, col="predicted_demand_kw"):
    s = [0.0] * 24
    for r in rows:
        s[(pd.Timestamp(r.forecast_timestamp) + IST).hour] = getattr(r, col)
    return s


def build_inputs(db):
    camp = db.scalars(select(Forecast).where(Forecast.scope == "campus", Forecast.horizon == "24_hours")).all()
    sol = db.scalars(select(Forecast).where(Forecast.scope == "solar")).all()
    demand, solar = _series(camp), _series(sol)
    n_h = db.scalar(select(__import__("sqlalchemy").func.count()).select_from(Building).join(Zone, Zone.id == Building.zone_id)
                    .where(Zone.zone_type == "Hostel", Building.is_active == True)) or 0  # noqa
    pump = [0.0] * 24
    for h in (5, 6, 17):
        pump[h] = PUMP_KW * n_h
    pump[18] = PUMP_KW * n_h * 0.5
    acad = db.scalars(select(Forecast).where(Forecast.scope == "zone", Forecast.zone_type == "Academic", Forecast.horizon == "24_hours")).all()
    acad_s = _series(acad)
    neq = [0.04 * acad_s[h] if 9 <= h < 17 else 0.0 for h in range(24)]
    flex = [
        dict(name="Hostel water pumps (flexible, tank-buffered)", baseline_kw=pump, energy_kwh=sum(pump), window=(5, 19),
             max_kw=PUMP_KW * n_h, essential=False),
        dict(name="Approved non-critical academic equipment", baseline_kw=neq, energy_kwh=sum(neq), window=(6, 22),
             max_kw=max(max(neq), 1) * 1.5, essential=False),
    ]
    base = [max(0.0, demand[h] - sum(f["baseline_kw"][h] for f in flex)) for h in range(24)]
    return demand, solar, base, flex


def run_load_shifting(db: Session, user_id, peak_penalty=2.0, waste_lambda=0.5, peak_cap_kw=None):
    demand, solar, base, flex = build_inputs(db)
    tar = tariff_by_hour(db)
    res = optimize_load_shifting(base, solar, tar, flex, waste_lambda=waste_lambda, peak_penalty=peak_penalty, peak_cap_kw=peak_cap_kw)
    res["hours_local"] = list(range(24)); res["forecast_demand_kw"] = demand; res["solar_kw"] = solar; res["tariff"] = tar
    res["essential_load_note"] = "Essential and safety loads (kept inside base demand) are never shifted."
    res["data_note"] = "Inputs are SIMULATED forecasts; savings are ESTIMATES in recommendation mode, not achieved savings."
    if res["status"] == "optimal":
        pk = int(np.argmax(res["baseline"]["grid_kw"])); res["forecast_peak"] = dict(kw=res["baseline"]["peak_kw"], local_hour=pk)
    run = OptimizationRun(created_by=user_id, kind="load_shifting", parameters=dict(
        peak_penalty=peak_penalty, waste_lambda=waste_lambda, peak_cap_kw=peak_cap_kw), result=res,
        status="pending_review" if res["status"] == "optimal" else "infeasible", mode="recommendation")
    db.add(run); db.commit()
    return run
