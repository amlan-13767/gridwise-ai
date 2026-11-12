import datetime as dt
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session
from ml.anomaly_detection.detect import detect
from ..models.tables import Anomaly, Meter, Notification
from . import common

IST = pd.Timedelta(hours=5, minutes=30)


def run_detection(db: Session, days: int | None = None):
    now = common.data_now(db)
    start = pd.Timestamp(now) - pd.Timedelta(days=days or 400)
    hf = common.hourly_frame(db, start.to_pydatetime())
    bmap = common.building_map(db)
    hf["timestamp"] = hf.ts; hf["zone_type"] = hf.building_id.map(lambda i: bmap[i][1])
    hf["power_demand_kw"] = hf.y
    h, a = detect(hf[["timestamp", "building_id", "zone_type", "power_demand_kw"]])
    meters = {m.building_id: m.id for m in db.scalars(select(Meter))}
    existing = {(x.building_id, x.timestamp, x.detection_method) for x in db.scalars(select(Anomaly))}
    n = 0
    for r in a.itertuples():
        key = (r.building_id, r.ts.to_pydatetime(), r.method)
        if key in existing:
            continue
        cat = "overnight_consumption" if r.overnight else ("sudden_load_increase" if r.method == "rolling_mean_jump" else "high_consumption")
        db.add(Anomaly(building_id=r.building_id, meter_id=meters.get(r.building_id), timestamp=r.ts.to_pydatetime(),
                       observed_value=float(r.y), expected_value=float(r.expected), deviation=float(r.deviation_pct),
                       severity=r.severity, detection_method=r.method, category=cat,
                       baseline_info=dict(basis="median of comparable hours (same hour-of-day and weekday/weekend type)",
                                          hour_local=int(r.hour), day_type="weekend" if r.daytype else "weekday",
                                          robust_sigma_kw=float(r.mad), z_score=float(r.z)),
                       status="open"))
        n += 1
    db.commit()
    return n
