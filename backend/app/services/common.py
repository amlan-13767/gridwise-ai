import datetime as dt
import pandas as pd
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
from ..models.tables import EnergyReading, Meter, Building, Zone, Setting, OccupancyRecord, WeatherReading


def data_now(db: Session) -> dt.datetime:
    """The 'current time' of the data set (latest stored reading, UTC naive)."""
    return db.scalar(select(func.max(EnergyReading.timestamp))) or dt.datetime.utcnow()


def get_setting(db: Session, key: str, default=None, cast=float):
    s = db.get(Setting, key)
    if not s:
        return default
    try:
        return cast(s.value)
    except Exception:
        return s.value


def building_map(db: Session):
    rows = db.execute(select(Building, Zone.zone_type).join(Zone, Zone.id == Building.zone_id)).all()
    return {b.id: (b, zt) for b, zt in rows}


def hourly_frame(db: Session, start: dt.datetime, end: dt.datetime | None = None) -> pd.DataFrame:
    """Hourly mean power per building from stored readings (UTC)."""
    q = (select(EnergyReading.timestamp, EnergyReading.power_demand_kw, EnergyReading.cooling_load_kw,
                EnergyReading.indoor_temperature, Meter.building_id)
         .join(Meter, Meter.id == EnergyReading.meter_id).where(EnergyReading.timestamp >= start))
    if end:
        q = q.where(EnergyReading.timestamp <= end)
    df = pd.read_sql(q, db.get_bind())
    df["ts"] = pd.to_datetime(df.timestamp).dt.floor("h")
    return (df.groupby(["building_id", "ts"]).agg(y=("power_demand_kw", "mean"), cooling=("cooling_load_kw", "mean"),
                                                   indoor=("indoor_temperature", "mean")).reset_index())


def weather_frame(db, start):
    return pd.read_sql(select(WeatherReading).where(WeatherReading.timestamp >= start), db.get_bind())


def occupancy_frame(db, start):
    return pd.read_sql(select(OccupancyRecord.building_id, OccupancyRecord.timestamp, OccupancyRecord.occupancy,
                              OccupancyRecord.occupancy_basis).where(OccupancyRecord.timestamp >= start), db.get_bind())
