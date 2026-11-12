"""Pandas analytics on a cached hourly frame (stored in UTC; presented in IST)."""
import time, datetime as dt
import numpy as np, pandas as pd
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..core.db import engine
from ..models.tables import EnergyReading, Meter, Building, Zone, Anomaly, Recommendation, RenewableReading, OccupancyRecord
from . import common
from .optimization_service import tariff_by_hour

IST = pd.Timedelta(hours=5, minutes=30)
_cache = {"key": None, "t": 0, "df": None}
SQLITE = engine.dialect.name == "sqlite"


def utc_hour(col):
    return func.strftime("%Y-%m-%d %H:00:00", col) if SQLITE else func.to_char(func.date_trunc("hour", col), "YYYY-MM-DD HH24:MI:SS")


def frame(db: Session) -> pd.DataFrame:
    key = db.scalar(select(func.max(EnergyReading.id)))
    if _cache["key"] == key and time.time() - _cache["t"] < 120 and _cache["df"] is not None:
        return _cache["df"]
    hb = utc_hour(EnergyReading.timestamp).label("hb")
    q = (select(hb, Meter.building_id, Meter.id.label("meter_id"), EnergyReading.data_source,
                func.sum(EnergyReading.energy_consumption_kwh).label("kwh"), func.max(EnergyReading.power_demand_kw).label("kw_max"),
                func.avg(EnergyReading.power_demand_kw).label("kw"), func.sum(EnergyReading.cooling_load_kw).label("cool_raw"),
                func.count().label("n"))
         .join(Meter, Meter.id == EnergyReading.meter_id).group_by(hb, Meter.building_id, Meter.id, EnergyReading.data_source))
    df = pd.read_sql(q, db.get_bind())
    df["ts"] = pd.to_datetime(df.hb); df["cooling_kwh"] = df.cool_raw.fillna(0) * 0.25
    b = pd.read_sql(select(Building.id.label("building_id"), Building.code, Building.building_name, Building.building_type,
                           Building.floor_area, Building.capacity, Building.zone_id, Building.is_active, Zone.zone_type, Building.location_latitude,
                           Building.location_longitude).join(Zone, Zone.id == Building.zone_id), db.get_bind())
    df = df.merge(b, on="building_id")
    loc = df.ts + IST
    df["lhour"] = loc.dt.hour; df["ldate"] = loc.dt.strftime("%Y-%m-%d")
    tar = tariff_by_hour(db)
    df["cost"] = df.kwh * df.lhour.map(lambda h: tar[h])
    _cache.update(key=key, t=time.time(), df=df)
    return df


def invalidate():
    _cache["df"] = None


def scoped(db, df, user, zone=None, building_id=None, meter_id=None, source=None, start=None, end=None, building_level=False):
    from ..core.deps import zone_scope
    sc = zone_scope(db, user)
    if sc is not None:
        df = df[df.zone_id.isin(sc)]
    if building_level and user.role == "viewer":
        df = df[df.zone_type != "Residential"]
    if zone:
        df = df[df.zone_type.str.lower() == zone.lower()]
    if building_id:
        df = df[df.building_id == building_id]
    if meter_id:
        df = df[df.meter_id == meter_id]
    if source:
        df = df[df.data_source == source]
    if start:
        df = df[df.ts >= pd.Timestamp(start)]
    if end:
        df = df[df.ts <= pd.Timestamp(end)]
    return df[df.is_active] if "is_active" in df else df


def window(db, days, start=None, end=None):
    now = pd.Timestamp(common.data_now(db)).floor("h")
    e = pd.Timestamp(end) if end else now
    s = pd.Timestamp(start) if start else e - pd.Timedelta(days=days)
    return s, e


def hourly_campus(df):
    return df.groupby("ts").agg(kwh=("kwh", "sum"), kw=("kw", "sum"), cooling=("cooling_kwh", "sum"), cost=("cost", "sum")).reset_index()


def peak_info(df):
    h = df.groupby("ts").kw_max.sum()
    if h.empty:
        return None
    t = h.idxmax(); return dict(kw=float(h.max()), timestamp=t.isoformat() + "Z")


def consumption(df, gran="day", group=None):
    loc = df.ts + IST
    key = {"hour": loc.dt.strftime("%Y-%m-%dT%H:00"), "day": loc.dt.strftime("%Y-%m-%d"),
           "week": loc.dt.strftime("%G-W%V"), "month": loc.dt.strftime("%Y-%m")}[gran]
    d = df.assign(bucket=key)
    cols = ["bucket"] + ([{"zone": "zone_type", "building": "building_name"}[group]] if group else [])
    g = d.groupby(cols).agg(kwh=("kwh", "sum"), cost=("cost", "sum")).reset_index()
    peaks = d.groupby(cols + ["ts"]).kw_max.sum().reset_index().groupby(cols).kw_max.max().rename("peak_kw").reset_index()
    g = g.merge(peaks, on=cols).rename(columns={"zone_type": "zone", "building_name": "building"})
    return g.round(2).to_dict("records")
