import datetime as dt
import numpy as np, pandas as pd
from sqlalchemy.orm import Session
from optimization.cooling_optimizer import optimize_cooling
from ..models.tables import Building, Zone
from . import common
from .optimization_service import tariff_by_hour

IST = pd.Timedelta(hours=5, minutes=30)
LOW_OCC = 0.05  # fraction of capacity treated as 'no reported occupancy'


def _frame(db, days):
    now = pd.Timestamp(common.data_now(db)); start = (now - pd.Timedelta(days=days)).to_pydatetime()
    hf = common.hourly_frame(db, start)
    oc = common.occupancy_frame(db, start); oc["ts"] = pd.to_datetime(oc.timestamp)
    f = hf.merge(oc[["building_id", "ts", "occupancy", "occupancy_basis"]], on=["building_id", "ts"], how="left")
    loc = f.ts + IST
    f["hour"] = loc.dt.hour; f["dow"] = loc.dt.dayofweek
    return f


def analysis(db: Session, days=14, zone_ids=None, building_id=None):
    start_h = int(common.get_setting(db, "operating_start_hour", 8)); end_h = int(common.get_setting(db, "operating_end_hour", 18))
    f = _frame(db, days); bmap = common.building_map(db)
    tariff = common.get_setting(db, "electricity_tariff", 6.0)
    out = []
    for bid, g in f.groupby("building_id"):
        b, zt = bmap[bid]
        if zone_ids is not None and b.zone_id not in zone_ids or (building_id and bid != building_id):
            continue
        cap = b.capacity or 1
        low = g.occupancy.fillna(0) < LOW_OCC * cap
        outside = (g.hour < start_h) | (g.hour >= end_h) | (g.dow >= 5)
        crit = b.building_type == "server_room"
        ah = g[low & outside & (g.cooling > 0.5)] if zt == "Academic" and not crit else g.iloc[0:0]
        total_cool = float(g.cooling.sum()); total = float(g.y.sum())
        occ_hrs = g[~low]
        comfort = float((occ_hrs.indoor.between(22, 26.5)).mean() * 100) if len(occ_hrs) else None
        out.append(dict(
            building_id=bid, code=b.code, building=b.building_name, zone=zt, building_type=b.building_type,
            cooling_kwh=total_cool, total_kwh=total, hvac_share_pct=total_cool / total * 100 if total else 0,
            after_hours_cooling_kwh=float(ah.cooling.sum()), after_hours_cooling_hours=int(len(ah)),
            est_saving_kwh=float(ah.cooling.sum() * (1 - 0.25)), est_saving_cost=float(ah.cooling.sum() * 0.75 * tariff),
            comfort_in_range_pct=comfort, avg_indoor_temp_occupied=float(occ_hrs.indoor.mean()) if len(occ_hrs) else None,
            schedule_flag=bool(float(ah.cooling.sum()) > 0.08 * max(total_cool, 1) and len(ah) >= 20),
            occupancy_basis=str(g.occupancy_basis.dropna().iloc[0]) if g.occupancy_basis.notna().any() else "none",
            assumptions="After-hours = outside configured operating hours (or weekend) with occupancy < 5% of capacity "
                        "(occupancy is " + ("schedule-based, not observed" if zt == "Academic" else "estimated") + "). "
                        "Saving assumes cooling can be set back to 25% outside hours: an ESTIMATE, not a measured result."))
    return sorted(out, key=lambda r: -r["after_hours_cooling_kwh"])


def optimize(db: Session, building_id: int, days=7):
    bmap = common.building_map(db); b, zt = bmap[building_id]
    f = _frame(db, days); g = f[f.building_id == building_id]
    cap = b.capacity or 1
    prof = g.groupby("hour").agg(c=("cooling", "mean"), o=("occupancy", "mean")).reindex(range(24)).fillna(0)
    occupied = [bool(o >= LOW_OCC * cap) for o in prof.o]
    tar = tariff_by_hour(db)
    sb = common.get_setting(db, "setback_min_fraction", 0.25)
    crit = b.building_type == "server_room"
    r = optimize_cooling(prof.c.tolist(), occupied, tar, setback_min=sb, critical=crit)
    r.update(building=b.building_name, building_id=building_id, baseline_kw=prof.c.tolist(), occupied=occupied,
             tariff=tar, basis=f"typical day from last {days} days; occupancy is {'schedule-based' if zt=='Academic' else 'estimated'}",
             kind="ESTIMATED saving vs observed baseline - not measured", approval_required=True,
             note="Recommendation only. GRIDWISE AI does not change HVAC settings. Respect equipment limits and thermal-comfort standards.",
             explanation=("Critical load: cooling kept at 100%." if crit else
                          f"Occupied hours stay at 100% of required cooling (comfort). Unoccupied hours may be set back to {int(sb*100)}% "
                          f"(equipment floor), valued at hourly tariff."))
    return r
