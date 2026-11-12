import pandas as pd, numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..core.db import get_db
from ..core.deps import current_user, check_building, zone_scope
from ..models.tables import *
from ..services import analytics as A, common

router = APIRouter(prefix="/api/energy", tags=["energy"])
IST = pd.Timedelta(hours=5, minutes=30)


def _f(db, u, days, zone, building_id, meter_id, source, start, end, building_level=False):
    df = A.frame(db)
    s, e = A.window(db, days, start, end)
    return A.scoped(db, df, u, zone, building_id, meter_id, source, s, e, building_level), s, e


def _anoms(db, u, since, building_ids=None, status="open"):
    q = select(Anomaly, Building, Zone.zone_type).join(Building, Building.id == Anomaly.building_id).join(Zone, Zone.id == Building.zone_id).where(Anomaly.timestamp >= since)
    sc = zone_scope(db, u)
    if sc is not None:
        q = q.where(Building.zone_id.in_(sc))
    if u.role == "viewer":
        q = q.where(Zone.zone_type != "Residential")
    if status:
        q = q.where(Anomaly.status == status)
    return db.execute(q).all()


def _rec_savings(db, zone_ids=None):
    q = select(Recommendation.estimated_energy_saving_kwh, Recommendation.estimated_cost_saving, Building.zone_id, Zone.zone_type) \
        .outerjoin(Building, Building.id == Recommendation.building_id).outerjoin(Zone, Zone.id == Building.zone_id) \
        .where(Recommendation.status.in_(["pending", "approved", "investigating"]))
    return db.execute(q).all()


@router.get("/overview")
def overview(days: int = Query(30, ge=1, le=120), zone: str | None = None, building_id: int | None = None, meter_id: int | None = None,
             source: str | None = None, start: str | None = None, end: str | None = None,
             u: User = Depends(current_user), db: Session = Depends(get_db)):
    df, s, e = _f(db, u, days, zone, building_id, meter_id, source, start, end)
    if df.empty:
        return dict(empty=True, data_mode="SIMULATED DEMONSTRATION DATA")
    total = float(df.kwh.sum()); cost = float(df.cost.sum())
    last = df[df.ts == df.ts.max()]
    cur = float(last.kw.sum())
    ren_q = select(func.coalesce(func.sum(RenewableReading.generation_kwh), 0), func.min(RenewableReading.data_source)).where(
        RenewableReading.timestamp >= s.to_pydatetime(), RenewableReading.timestamp <= e.to_pydatetime())
    ren, rsrc = db.execute(ren_q).one()
    sav = _rec_savings(db)
    sc = zone_scope(db, u)
    sav = [x for x in sav if sc is None or x[2] in sc]
    anoms = _anoms(db, u, (e - pd.Timedelta(days=7)).to_pydatetime())
    mode = "SIMULATED DEMONSTRATION DATA" if set(df.data_source) <= {"simulated"} else "MIXED / REAL DATA - check source filter"
    return dict(data_mode=mode, period=dict(start=s.isoformat() + "Z", end=e.isoformat() + "Z", days=days),
                total_kwh=total, current_kw=cur, estimated_cost=cost, peak=A.peak_info(df),
                renewable_kwh=float(ren), renewable_source=rsrc or "none", renewable_pct=float(ren) / total * 100 if total else 0,
                saving_opportunity_kwh=float(sum(x[0] or 0 for x in sav)), saving_opportunity_cost=float(sum(x[1] or 0 for x in sav)),
                saving_note="ESTIMATED opportunity from open recommendations; not achieved savings.",
                active_anomalies=len(anoms), currency="INR", cost_note="Cost uses the configured tariff slabs (assumption).")


@router.get("/consumption")
def consumption(granularity: str = Query("day", pattern="^(hour|day|week|month)$"), group: str | None = Query(None, pattern="^(zone|building)$"),
                days: int = Query(30, ge=1, le=120), zone: str | None = None, building_id: int | None = None, meter_id: int | None = None,
                source: str | None = None, start: str | None = None, end: str | None = None,
                u: User = Depends(current_user), db: Session = Depends(get_db)):
    df, s, e = _f(db, u, days, zone, building_id, meter_id, source, start, end, building_level=group == "building")
    return dict(granularity=granularity, group=group, items=A.consumption(df, granularity, group) if not df.empty else [])


@router.get("/buildings")
def buildings(days: int = Query(30, ge=1, le=120), zone: str | None = None, u: User = Depends(current_user), db: Session = Depends(get_db)):
    df, s, e = _f(db, u, days, zone, None, None, None, None, None, building_level=True)
    anoms = {b.id for _, b, _ in _anoms(db, u, (e - pd.Timedelta(days=2)).to_pydatetime())}
    out = []
    # expected = median of same local hour and day type over the window
    for bid, g in df.groupby("building_id"):
        r = g.iloc[0]; days_n = max(1, (e - s).days)
        latest = g.sort_values("ts").iloc[-1]
        hist = g[(g.lhour == latest.lhour)]
        exp = float(hist.kw.median()) if len(hist) else None
        ratio = latest.kw / exp if exp else None
        stale = (e - latest.ts) > pd.Timedelta(hours=6)
        status = "no_data" if stale else "anomaly" if bid in anoms else "elevated" if ratio and ratio > 1.15 else "normal"
        night = g[g.lhour.between(0, 4)].kwh.sum() / max(1, days_n) / 5
        out.append(dict(building_id=int(bid), code=r.code, building=r.building_name, zone=r.zone_type, building_type=r.building_type,
                        kwh=float(g.kwh.sum()), avg_daily_kwh=float(g.kwh.sum()) / days_n, peak_kw=float(g.groupby("ts").kw_max.sum().max()),
                        cost=float(g.cost.sum()), current_kw=float(latest.kw), expected_kw=exp, status=status,
                        kwh_per_m2=float(g.kwh.sum() / r.floor_area) if r.floor_area else None,
                        lat=r.location_latitude, lon=r.location_longitude, floor_area=r.floor_area, capacity=int(r.capacity) if r.capacity == r.capacity else None))
    return dict(items=sorted(out, key=lambda x: -x["kwh"]))


@router.get("/zones")
def zones(days: int = Query(30, ge=1, le=120), u: User = Depends(current_user), db: Session = Depends(get_db)):
    df, s, e = _f(db, u, days, None, None, None, None, None, None)
    occ = pd.read_sql(select(OccupancyRecord.building_id, OccupancyRecord.timestamp, OccupancyRecord.occupancy), db.get_bind())
    occ["h"] = (pd.to_datetime(occ.timestamp) + IST).dt.hour
    beds = occ[occ.h.between(0, 4)].groupby("building_id").occupancy.mean()  # night-time presence ~ occupied beds (ESTIMATE)
    sav = _rec_savings(db); out = []
    for zt, g in df.groupby("zone_type"):
        area = g.drop_duplicates("building_id").floor_area.sum()
        d = dict(zone=zt, kwh=float(g.kwh.sum()), peak_kw=float(g.groupby("ts").kw_max.sum().max()), cost=float(g.cost.sum()),
                 kwh_per_m2=float(g.kwh.sum() / area) if area else None, buildings=int(g.building_id.nunique()),
                 potential_saving_kwh=float(sum(x[0] or 0 for x in sav if x[3] == zt)), potential_saving_note="ESTIMATE")
        if zt == "Hostel":
            ids = g.building_id.unique(); ob = float(beds.reindex(ids).sum())
            d["occupied_beds_estimate"] = ob; d["kwh_per_occupied_bed"] = float(g.kwh.sum() / ob) if ob else None
            d["kwh_per_occupied_bed_per_day"] = d["kwh_per_occupied_bed"] / max(1, (e - s).days) if ob else None
        out.append(d)
    return dict(items=out, normalisation="Per m2 / per estimated occupied bed so buildings of different size can be compared")


@router.get("/peak-demand")
def peak(days: int = Query(30, ge=1, le=120), zone: str | None = None, u: User = Depends(current_user), db: Session = Depends(get_db)):
    df, s, e = _f(db, u, days, zone, None, None, None, None, None)
    if df.empty:
        return dict(daily=[], hourly_pattern=[], top=[])
    c = df.groupby("ts").agg(kw=("kw_max", "sum")).reset_index()
    c["ldate"] = (c.ts + IST).dt.strftime("%Y-%m-%d"); c["lh"] = (c.ts + IST).dt.hour
    daily = c.loc[c.groupby("ldate").kw.idxmax()][["ldate", "kw", "lh"]].rename(columns={"ldate": "date", "lh": "local_hour"})
    pat = c.groupby("lh").kw.agg(["mean", "max"]).reset_index().rename(columns={"lh": "hour", "mean": "avg_kw", "max": "max_kw"})
    top = c.nlargest(5, "kw")
    return dict(daily=daily.round(1).to_dict("records"), hourly_pattern=pat.round(1).to_dict("records"),
                top=[dict(timestamp=r.ts.isoformat() + "Z", kw=round(r.kw, 1)) for r in top.itertuples()])


@router.get("/zone-dashboard/{zone_type}")
def zone_dashboard(zone_type: str, days: int = Query(30, ge=1, le=120), u: User = Depends(current_user), db: Session = Depends(get_db)):
    zt = zone_type.capitalize()
    if zt not in ("Academic", "Hostel", "Residential"):
        raise HTTPException(404, "Unknown zone")
    sc = zone_scope(db, u)
    if sc is not None:
        z = db.scalar(select(Zone).where(Zone.zone_type == zt))
        if z.id not in sc:
            raise HTTPException(403, "Zone outside your authorisation")
    df, s, e = _f(db, u, days, zt, None, None, None, None, None, building_level=True)
    restricted = u.role == "viewer" and zt == "Residential"
    n = max(1, (e - s).days)
    res = dict(zone=zt, days=n, data_mode="SIMULATED DEMONSTRATION DATA", restricted=restricted)
    if restricted:
        df2 = A.scoped(db, A.frame(db), u, zt, None, None, None, s, e)
        res["aggregate_only"] = True
        res["daily"] = A.consumption(df2, "day"); res["note"] = "Viewer role: building-level residential data is withheld for privacy."
        return res
    if df.empty:
        return res
    res["daily"] = A.consumption(df, "day"); res["by_building"] = A.consumption(df, "day", "building")
    prof = df.groupby(["lhour"]).agg(kw=("kw", "sum")).reset_index(); prof["kw"] = prof.kw / (df.ts.nunique() / 24)
    res["hourly_profile"] = prof.round(1).to_dict("records")
    rows = []
    occ = pd.read_sql(select(OccupancyRecord.building_id, OccupancyRecord.timestamp, OccupancyRecord.occupancy), db.get_bind())
    occ["h"] = (pd.to_datetime(occ.timestamp) + IST).dt.hour
    nightocc = occ[occ.h.between(0, 4)].groupby("building_id").occupancy.mean()
    for bid, g in df.groupby("building_id"):
        r = g.iloc[0]
        row = dict(building_id=int(bid), building=r.building_name, building_type=r.building_type, kwh=float(g.kwh.sum()),
                   cost=float(g.cost.sum()), peak_kw=float(g.groupby("ts").kw_max.sum().max()), kwh_per_m2=float(g.kwh.sum() / r.floor_area) if r.floor_area else None,
                   overnight_kwh_per_night=float(g[g.lhour.between(0, 4)].kwh.sum() / n), evening_peak_kw=float(g[g.lhour.between(18, 21)].kw.mean()),
                   hvac_pct=float(g.cooling_kwh.sum() / g.kwh.sum() * 100), cooling_kwh=float(g.cooling_kwh.sum()))
        if zt == "Hostel":
            ob = float(nightocc.get(bid, 0))
            row.update(capacity=int(r.capacity), occupied_beds_estimate=ob, occupancy_pct=ob / r.capacity * 100 if r.capacity else None,
                       kwh_per_occupied_bed_per_day=float(g.kwh.sum() / n / ob) if ob else None)
        rows.append(row)
    res["buildings"] = sorted(rows, key=lambda x: -x["kwh"])
    afterhours = df[(df.lhour < 8) | (df.lhour >= 18)]
    res["outside_hours_kwh"] = float(afterhours.kwh.sum()); res["total_kwh"] = float(df.kwh.sum())
    res["hvac_kwh"] = float(df.cooling_kwh.sum())
    if zt == "Academic":
        res["by_type"] = df.groupby("building_type").kwh.sum().round(1).reset_index().to_dict("records")
        res["note"] = ("Occupancy is schedule-based, not observed; an empty timetable slot does not prove a room is unoccupied. "
                       "Sub-metering for lab/classroom areas is not available in the simulated dataset - building-level meters only.")
    if zt == "Hostel":
        res["submetering"] = "Mess, water-pump and corridor sub-meters are not present in the simulated dataset. Individual student consumption is never shown."
        res["patterns_note"] = "Detected patterns are investigation opportunities, not conclusions about occupant behaviour."
    if zt == "Residential":
        res["privacy"] = "Aggregate cluster-level data only. Household-level monitoring requires consent and is not enabled."
        sol = db.scalar(select(func.coalesce(func.sum(RenewableReading.generation_kwh), 0)).where(RenewableReading.timestamp >= s.to_pydatetime()))
        res["solar_note"] = "Simulated solar assets are attached to academic buildings; no residential solar in this dataset."
    return res


@router.get("/building/{bid}/summary")
def building_summary(bid: int, days: int = Query(14, ge=1, le=90), u: User = Depends(current_user), db: Session = Depends(get_db)):
    b = db.get(Building, bid)
    if not b:
        raise HTTPException(404, "Building not found")
    check_building(db, u, b)
    zt = db.get(Zone, b.zone_id).zone_type
    df, s, e = _f(db, u, days, None, bid, None, None, None, None)
    daily = A.consumption(df, "day"); hourly = A.consumption(df.tail(24 * 7), "hour")
    fc = db.scalars(select(Forecast).where(Forecast.building_id == bid, Forecast.horizon == "24_hours").order_by(Forecast.forecast_timestamp)).all()
    an = db.scalars(select(Anomaly).where(Anomaly.building_id == bid).order_by(Anomaly.timestamp.desc()).limit(10)).all()
    rc = db.scalars(select(Recommendation).where(Recommendation.building_id == bid).order_by(Recommendation.id.desc()).limit(10)).all()
    areas = db.scalars(select(BuildingArea).where(BuildingArea.building_id == bid)).all()
    total = float(df.kwh.sum()); n = max(1, (e - s).days)
    return dict(building=dict(id=b.id, code=b.code, name=b.building_name, zone=zt, type=b.building_type, floor_area=b.floor_area, capacity=b.capacity,
                              lat=b.location_latitude, lon=b.location_longitude, approximate=b.location_is_approximate),
                data_mode="SIMULATED DEMONSTRATION DATA",
                kpis=dict(total_kwh=total, avg_daily_kwh=total / n, peak_kw=float(df.groupby("ts").kw_max.sum().max()) if not df.empty else 0,
                          kwh_per_m2=total / b.floor_area if b.floor_area else None, hvac_pct=float(df.cooling_kwh.sum() / total * 100) if total else None,
                          cost=float(df.cost.sum()), current_kw=float(df.sort_values("ts").iloc[-1].kw) if not df.empty else None),
                daily=daily, hourly=hourly, areas=[dict(name=a.name, type=a.area_type) for a in areas],
                forecast=[dict(ts=f.forecast_timestamp.isoformat() + "Z", kw=f.predicted_demand_kw, lower=f.lower_bound_kw, upper=f.upper_bound_kw, model=f.model_version) for f in fc],
                anomalies=[dict(id=a.id, timestamp=a.timestamp.isoformat() + "Z", severity=a.severity, deviation=a.deviation, status=a.status, category=a.category) for a in an],
                recommendations=[dict(id=r.id, title=r.title, priority=r.priority, status=r.status, type=r.recommendation_type) for r in rc])
