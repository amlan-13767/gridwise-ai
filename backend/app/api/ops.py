import csv, io, json, datetime as dt
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ml.common import REPORTS
from ..core.config import settings
from ..core.db import get_db
from ..core.deps import current_user, require, audit, zone_scope, MANAGE, ADMIN
from ..core.security import hash_password
from ..iot.ingest import ingest, device_status, device_key
from ..models.tables import *
from ..services import analytics as A, common

router = APIRouter(prefix="/api", tags=["ops"])
IST = pd.Timedelta(hours=5, minutes=30)


def _respond(rows: list[dict], fmt: str, name: str, meta: dict):
    if fmt == "csv":
        buf = io.StringIO()
        buf.write(f"# GRIDWISE AI report: {name}. {meta.get('data_mode','')}. Estimates are not measured savings.\n")
        if rows:
            w = csv.DictWriter(buf, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="gridwise_{name}.csv"'})
    return dict(**meta, rows=rows)


# ---------------- Reports ----------------
@router.get("/reports/energy")
def rep_energy(days: int = Query(30, ge=1, le=120), granularity: str = "day", zone: str | None = None, format: str = Query("json", pattern="^(json|csv)$"),
               u: User = Depends(current_user), db: Session = Depends(get_db)):
    s, e = A.window(db, days)
    df = A.scoped(db, A.frame(db), u, zone, None, None, None, s, e)
    rows = A.consumption(df, granularity, "zone")
    c = A.hourly_campus(df)
    n = max(1, days)
    meta = dict(data_mode="SIMULATED DEMONSTRATION DATA", period_days=days, total_kwh=float(df.kwh.sum()), avg_daily_kwh=float(df.kwh.sum()) / n,
                peak=A.peak_info(df), estimated_cost=float(df.cost.sum()), currency="INR")
    return _respond(rows, format, "energy", meta)


@router.get("/reports/buildings")
def rep_buildings(days: int = Query(30, ge=1, le=120), format: str = Query("json", pattern="^(json|csv)$"), u: User = Depends(current_user), db: Session = Depends(get_db)):
    from .energy import buildings
    items = buildings(days, None, u, db)["items"]
    rows = [dict(code=i["code"], building=i["building"], zone=i["zone"], kwh=round(i["kwh"], 1), avg_daily_kwh=round(i["avg_daily_kwh"], 1),
                 peak_kw=round(i["peak_kw"], 1), cost_inr=round(i["cost"], 0), kwh_per_m2=round(i["kwh_per_m2"], 2) if i["kwh_per_m2"] else None,
                 status=i["status"], data_source="simulated") for i in items]
    return _respond(rows, format, "buildings", dict(data_mode="SIMULATED DEMONSTRATION DATA", period_days=days))


@router.get("/reports/sustainability")
def rep_sust(days: int = Query(30, ge=1, le=120), format: str = Query("json", pattern="^(json|csv)$"), u: User = Depends(current_user), db: Session = Depends(get_db)):
    ef = common.get_setting(db, "grid_emissions_factor", settings.GRID_EMISSIONS_FACTOR)
    s, e = A.window(db, days)
    df = A.scoped(db, A.frame(db), u, None, None, None, None, s, e)
    ren = pd.read_sql(select(RenewableReading.timestamp, func.sum(RenewableReading.generation_kwh).label("kwh")).group_by(RenewableReading.timestamp)
                      .where(RenewableReading.timestamp >= s.to_pydatetime()), db.get_bind())
    ren_kwh = float(ren.kwh.sum()) if u.role != "zone_manager" else 0.0
    total = float(df.kwh.sum()); grid = max(0.0, total - ren_kwh)
    zones = df.groupby("zone_type").kwh.sum()
    zrows = [dict(zone=z, kwh=round(float(k), 1), emissions_kg=round(float(k) * ef * (grid / total if total else 1), 1)) for z, k in zones.items()]
    loc = df.ts + IST
    wk = df.assign(week=loc.dt.strftime("%G-W%V")).groupby("week").kwh.sum().reset_index()
    rec_meas = db.scalar(select(func.coalesce(func.sum(Recommendation.measured_saving_kwh), 0)))
    rec_est = db.scalar(select(func.coalesce(func.sum(Recommendation.estimated_energy_saving_kwh), 0)).where(Recommendation.status.in_(["pending", "approved", "investigating"])))
    meta = dict(data_mode="SIMULATED DEMONSTRATION DATA", period_days=days, emissions_factor_kg_per_kwh=ef,
                formula="Estimated carbon = grid electricity (total - renewable) x emissions factor",
                total_kwh=total, renewable_kwh=ren_kwh, grid_kwh=grid, estimated_emissions_kg=grid * ef, estimated_avoided_kg=ren_kwh * ef,
                renewable_note="Renewable generation is SIMULATED. All carbon figures are ESTIMATES using the configured factor, which is an assumption and must be replaced with an official value.",
                weekly_kwh=wk.round(1).to_dict("records"), measured_savings_kwh=float(rec_meas), estimated_saving_pipeline_kwh=float(rec_est),
                zone_emissions=zrows)
    return _respond(zrows, format, "sustainability", meta)


@router.get("/reports/models")
def rep_models(format: str = Query("json", pattern="^(json|csv)$"), u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = [dict(model=m.name, version=m.version, task=m.task, status=m.status, trained_at=m.trained_at.isoformat(),
                 rmse=(m.metrics or {}).get("test", {}).get("rmse"), mae=(m.metrics or {}).get("test", {}).get("mae"),
                 baseline_rmse=(m.metrics or {}).get("baseline", {}).get("rmse")) for m in db.scalars(select(ModelVersion))]
    return _respond(rows, format, "models", dict(data_mode="Metrics are on SIMULATED data"))


# ---------------- IoT ----------------
class DeviceIn(BaseModel):
    building_id: int
    meter_identifier: str = Field(min_length=3, max_length=50)
    meter_type: str = "main"
    communication_protocol: str = Field("mqtt", pattern="^(mqtt|modbus_tcp|modbus_rtu|http|manual)$")
    installation_location: str = ""
    data_source: str = Field("real", pattern="^(real|simulated)$")


class DevicePatch(BaseModel):
    status: str | None = Field(None, pattern="^(active|inactive|maintenance)$")
    installation_location: str | None = None


@router.get("/iot/devices")
def devices(u: User = Depends(current_user), db: Session = Depends(get_db)):
    ref_sim = common.data_now(db); ref_real = dt.datetime.utcnow()
    q = select(Meter, Building, Zone.zone_type).join(Building, Building.id == Meter.building_id).join(Zone, Zone.id == Building.zone_id)
    sc = zone_scope(db, u)
    if sc is not None:
        q = q.where(Building.zone_id.in_(sc))
    if u.role == "viewer":
        q = q.where(Zone.zone_type != "Residential")
    last = dict(db.execute(select(EnergyReading.meter_id, func.max(EnergyReading.timestamp)).group_by(EnergyReading.meter_id)).all())
    out = []
    for m, b, zt in db.execute(q.order_by(Meter.id)):
        m.last_seen = max([x for x in (m.last_seen, last.get(m.id)) if x] or [None]) if (m.last_seen or last.get(m.id)) else None
        out.append(dict(id=m.id, meter_identifier=m.meter_identifier, building=b.building_name, zone=zt, protocol=m.communication_protocol,
                        data_source=m.data_source, config_status=m.status, connection=device_status(m, ref_sim if m.data_source == "simulated" else ref_real),
                        last_seen=m.last_seen.isoformat() + "Z" if m.last_seen else None, location=m.installation_location))
    return dict(items=out, note="'simulated' devices are virtual; no real hardware is implied.")


@router.post("/iot/devices", status_code=201)
def add_device(body: DeviceIn, u: User = Depends(require(*ADMIN)), db: Session = Depends(get_db)):
    if not db.get(Building, body.building_id):
        raise HTTPException(404, "Building not found")
    if db.scalar(select(Meter).where(Meter.meter_identifier == body.meter_identifier)):
        raise HTTPException(409, "Device already registered")
    m = Meter(**body.model_dump()); db.add(m); db.flush(); audit(db, u.id, "device_registered", "meter", m.id); db.commit()
    return dict(id=m.id, meter_identifier=m.meter_identifier, device_key=device_key(settings.SECRET_KEY, m.meter_identifier),
                note="Store this key on the device now; it authenticates MQTT/HTTP publishing.")


@router.patch("/iot/devices/{did}")
def patch_device(did: int, body: DevicePatch, u: User = Depends(require(*ADMIN)), db: Session = Depends(get_db)):
    m = db.get(Meter, did)
    if not m:
        raise HTTPException(404, "Device not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    audit(db, u.id, "device_updated", "meter", did); db.commit()
    return dict(id=m.id, status=m.status)


@router.get("/iot/status")
def iot_status(u: User = Depends(current_user), db: Session = Depends(get_db)):
    d = devices(u, db)["items"]
    cnt = {}
    for x in d:
        cnt[x["connection"]] = cnt.get(x["connection"], 0) + 1
    q = dict(db.execute(select(EnergyReading.quality_status, func.count()).group_by(EnergyReading.quality_status)).all())
    src = dict(db.execute(select(EnergyReading.data_source, func.count()).group_by(EnergyReading.data_source)).all())
    return dict(devices=len(d), by_connection=cnt, quality=q, readings_by_source=src,
                mqtt=dict(broker=settings.MQTT_BROKER_URL.split("@")[-1], topic_pattern="gridwise/campus/<zone>/<building>/<meter>"))


@router.post("/iot/ingest")
async def http_ingest(request: Request, x_device_key: str | None = Header(None), db: Session = Depends(get_db)):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(dict(status="rejected", reason="body is not JSON"), 400)
    r = ingest(db, body, x_device_key, settings.SECRET_KEY)
    A.invalidate()
    return JSONResponse(r, {"stored": 201, "duplicate": 200, "rejected": 401 if "authentication" in r.get("reason", "") else 422}[r["status"]])


# ---------------- Admin ----------------
class UserPatch(BaseModel):
    name: str | None = None
    role: str | None = Field(None, pattern="^(super_admin|energy_manager|zone_manager|viewer)$")
    assigned_zone_id: int | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=10, max_length=128)


@router.get("/users")
def users(u: User = Depends(require(*ADMIN)), db: Session = Depends(get_db)):
    return dict(items=[dict(id=x.id, name=x.name, email=x.email, role=x.role, assigned_zone_id=x.assigned_zone_id, is_active=x.is_active) for x in db.scalars(select(User).order_by(User.id))])


@router.patch("/users/{uid}")
def patch_user(uid: int, body: UserPatch, u: User = Depends(require(*ADMIN)), db: Session = Depends(get_db)):
    t = db.get(User, uid)
    if not t:
        raise HTTPException(404, "User not found")
    ch = body.model_dump(exclude_unset=True)
    if uid == u.id and (ch.get("is_active") is False or ("role" in ch and ch["role"] != "super_admin")):
        raise HTTPException(409, "You cannot demote or deactivate your own account")
    if "password" in ch:
        t.password_hash = hash_password(ch.pop("password"))
    for k, v in ch.items():
        setattr(t, k, v)
    audit(db, u.id, "user_updated", "user", uid, {k: v for k, v in ch.items()}); db.commit()
    return dict(id=t.id, role=t.role, is_active=t.is_active)


@router.get("/audit-logs")
def audit_logs(limit: int = Query(100, le=500), offset: int = 0, u: User = Depends(require(*ADMIN)), db: Session = Depends(get_db)):
    rows = db.execute(select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.user_id).order_by(AuditLog.id.desc()).limit(limit).offset(offset)).all()
    return dict(items=[dict(id=a.id, user=e, action=a.action, entity=a.entity, entity_id=a.entity_id, detail=a.detail, at=a.created_at.isoformat() + "Z") for a, e in rows])


@router.get("/notifications")
def notifications(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where((Notification.user_id == u.id) | (Notification.user_id.is_(None))).order_by(Notification.id.desc()).limit(30)).all()
    return dict(items=[dict(id=n.id, title=n.title, body=n.body, level=n.level, is_read=n.is_read, at=n.created_at.isoformat() + "Z") for n in rows])


@router.get("/models")
def models(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return dict(items=[dict(id=m.id, name=m.name, version=m.version, task=m.task, trained_at=m.trained_at.isoformat() + "Z", training_dataset=m.training_dataset,
                            status=m.status, metrics=m.metrics, last_prediction_at=m.last_prediction_at.isoformat() + "Z" if m.last_prediction_at else None)
                       for m in db.scalars(select(ModelVersion).order_by(ModelVersion.task, ModelVersion.name))])


class ModelReview(BaseModel):
    decision: str = Field(pattern="^(promote|reject|archive)$")


@router.post("/models/{mid}/review")
def review_model(mid: int, body: ModelReview, u: User = Depends(require(*ADMIN)), db: Session = Depends(get_db)):
    m = db.get(ModelVersion, mid)
    if not m:
        raise HTTPException(404, "Model not found")
    if body.decision == "promote":
        for o in db.scalars(select(ModelVersion).where(ModelVersion.name == m.name, ModelVersion.status == "production", ModelVersion.id != m.id)):
            o.status = "archived"
    m.status = {"promote": "production", "reject": "rejected", "archive": "archived"}[body.decision]; m.reviewed_by = u.id
    audit(db, u.id, "model_review", "model_version", mid, dict(decision=body.decision)); db.commit()
    return dict(id=m.id, status=m.status)


SETTING_KEYS = {"grid_emissions_factor": float, "electricity_tariff": float, "reporting_period_days": int, "renewable_accounting": str,
                "operating_start_hour": int, "operating_end_hour": int, "setback_min_fraction": float}


@router.get("/settings")
def get_settings(u: User = Depends(current_user), db: Session = Depends(get_db)):
    d = {s.key: s.value for s in db.scalars(select(Setting))}
    return dict(settings=d, tariffs=[dict(id=t.id, name=t.name, start_hour=t.start_hour, end_hour=t.end_hour, rate=t.rate_per_kwh, assumption=t.is_assumption)
                                    for t in db.scalars(select(EnergyTariff))],
                notes="Emission factor and tariffs are configurable ASSUMPTIONS and must be set from official sources.")


@router.patch("/settings")
def patch_settings(body: dict, u: User = Depends(require(*ADMIN)), db: Session = Depends(get_db)):
    changed = {}
    for k, v in body.items():
        if k not in SETTING_KEYS:
            raise HTTPException(422, f"Unknown setting '{k}'")
        try:
            val = SETTING_KEYS[k](v)
        except (TypeError, ValueError):
            raise HTTPException(422, f"Invalid value for {k}")
        if SETTING_KEYS[k] in (float, int) and val < 0:
            raise HTTPException(422, f"{k} must be >= 0")
        if k == "setback_min_fraction" and val > 1:
            raise HTTPException(422, "setback_min_fraction must be <= 1")
        s = db.get(Setting, k)
        if s:
            s.value = str(val)
        else:
            db.add(Setting(key=k, value=str(val)))
        changed[k] = val
    audit(db, u.id, "settings_changed", "settings", detail=changed); db.commit(); A.invalidate()
    return dict(changed=changed)
