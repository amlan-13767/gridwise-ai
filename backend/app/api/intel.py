import json, datetime as dt
import pandas as pd, numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ml.common import REPORTS
from ..core.db import get_db
from ..core.deps import current_user, require, audit, check_building, zone_scope, MANAGE, ADMIN
from ..models.tables import *
from ..services import analytics as A, common, forecast_service, anomaly_service, cooling_service, optimization_service, recommendation_service
from optimization.renewable_dispatch import dispatch

router = APIRouter(prefix="/api", tags=["intelligence"])
IST = pd.Timedelta(hours=5, minutes=30)
iso = lambda d: d.isoformat() + "Z"


def _scope_filter(q, db, u, bcol=Building):
    sc = zone_scope(db, u)
    if sc is not None:
        q = q.where(bcol.zone_id.in_(sc))
    return q


# ---------------- Forecasting ----------------
@router.post("/forecast/run")
def run_forecast(u: User = Depends(require(*MANAGE)), db: Session = Depends(get_db)):
    forecast_service.run_forecast(db); audit(db, u.id, "forecast_run", "forecast"); db.commit()
    return dict(ok=True, count=db.scalar(select(func.count()).select_from(Forecast)))


@router.get("/forecast/evaluation")
def forecast_eval(u: User = Depends(current_user)):
    f = REPORTS / "forecast_evaluation.json"
    if not f.exists():
        raise HTTPException(404, "No evaluation report. Run scripts/train_models.py")
    return json.loads(f.read_text())


@router.get("/forecast")
def forecast(scope: str = Query("campus", pattern="^(campus|zone|building)$"), zone: str | None = None, building_id: int | None = None,
             horizon: str = Query("24_hours", pattern="^(1_hour|24_hours|7_days)$"), u: User = Depends(current_user), db: Session = Depends(get_db)):
    sc = zone_scope(db, u)
    q = select(Forecast).where(Forecast.horizon == horizon, Forecast.scope == scope)
    if scope == "zone":
        if not zone:
            raise HTTPException(422, "zone required")
        q = q.where(Forecast.zone_type == zone.capitalize())
        z = db.scalar(select(Zone).where(Zone.zone_type == zone.capitalize()))
        if sc is not None and (not z or z.id not in sc):
            raise HTTPException(403, "Zone outside your authorisation")
        if u.role == "viewer" and zone.capitalize() == "Residential":
            pass  # zone-level aggregate is allowed
    if scope == "campus" and sc is not None:
        raise HTTPException(403, "Campus-wide forecast requires campus-level role")
    if scope == "building":
        b = db.get(Building, building_id) if building_id else None
        if not b:
            raise HTTPException(404, "building_id required / not found")
        check_building(db, u, b)
        q = q.where(Forecast.building_id == building_id)
    rows = db.scalars(q.order_by(Forecast.forecast_timestamp)).all()
    now = pd.Timestamp(common.data_now(db)).floor("h")
    df = A.frame(db)
    sub = A.scoped(db, df, u, zone if scope == "zone" else None, building_id if scope == "building" else None, None, None,
                   now - pd.Timedelta(hours=72), now) if (scope != "campus" or sc is None) else df.iloc[0:0]
    act = sub.groupby("ts").kw.sum().reset_index()
    return dict(scope=scope, horizon=horizon, data_mode="SIMULATED DEMONSTRATION DATA",
                model_version=rows[0].model_version if rows else None, generated_at=iso(rows[0].generated_at) if rows else None,
                forecast=[dict(ts=iso(r.forecast_timestamp), kw=r.predicted_demand_kw, lower=r.lower_bound_kw, upper=r.upper_bound_kw) for r in rows],
                actual=[dict(ts=iso(r.ts.to_pydatetime()), kw=float(r.kw)) for r in act.itertuples()],
                predicted_kwh=sum(r.predicted_demand_kw for r in rows), lower_kwh=sum(r.lower_bound_kw for r in rows), upper_kwh=sum(r.upper_bound_kw for r in rows),
                interval="80% prediction interval from validation residuals (bounds summed; conservative)")


@router.get("/forecast/{building_id}")
def forecast_building(building_id: int, horizon: str = "24_hours", u: User = Depends(current_user), db: Session = Depends(get_db)):
    return forecast("building", None, building_id, horizon, u, db)


# ---------------- Anomalies ----------------
class ReviewIn(BaseModel):
    status: str = Field(pattern="^(investigating|dismissed|resolved|open)$")
    note: str | None = Field(None, max_length=1000)


def a_out(a: Anomaly, b: Building, zt: str):
    return dict(id=a.id, building_id=a.building_id, building=b.building_name, zone=zt, timestamp=iso(a.timestamp), observed_kw=a.observed_value,
                expected_kw=a.expected_value, deviation_pct=a.deviation, severity=a.severity, detection_method=a.detection_method,
                category=a.category, status=a.status, baseline=a.baseline_info, review_note=a.review_note,
                recommended_investigation={"overnight_consumption": "Check lighting, HVAC, lab equipment and servers left running overnight.",
                                           "sudden_load_increase": "Check for new/faulty equipment or schedule changes at this time.",
                                           "high_consumption": "Compare against comparable days and check equipment and meter integrity."}.get(a.category),
                disclaimer="Statistical anomaly - an investigation lead, not confirmed wastage.")


@router.get("/anomalies")
def anomalies(status: str | None = None, severity: str | None = None, building_id: int | None = None, zone: str | None = None, days: int = Query(30, le=400),
              limit: int = Query(50, le=500), offset: int = 0, u: User = Depends(current_user), db: Session = Depends(get_db)):
    now = common.data_now(db)
    q = select(Anomaly, Building, Zone.zone_type).join(Building, Building.id == Anomaly.building_id).join(Zone, Zone.id == Building.zone_id) \
        .where(Anomaly.timestamp >= now - dt.timedelta(days=days))
    q = _scope_filter(q, db, u)
    if u.role == "viewer":
        q = q.where(Zone.zone_type != "Residential")
    for col, v in ((Anomaly.status, status), (Anomaly.severity, severity), (Anomaly.building_id, building_id)):
        if v:
            q = q.where(col == v)
    if zone:
        q = q.where(Zone.zone_type == zone.capitalize())
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.execute(q.order_by(Anomaly.timestamp.desc()).limit(limit).offset(offset)).all()
    return dict(total=total, items=[a_out(a, b, zt) for a, b, zt in rows])


@router.get("/anomalies/{aid}")
def anomaly(aid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(Anomaly, aid)
    if not a:
        raise HTTPException(404, "Anomaly not found")
    b = db.get(Building, a.building_id); check_building(db, u, b)
    d = a_out(a, b, db.get(Zone, b.zone_id).zone_type)
    now = pd.Timestamp(a.timestamp)
    df = A.scoped(db, A.frame(db), u, None, a.building_id, None, None, now - pd.Timedelta(hours=36), now + pd.Timedelta(hours=12))
    d["context"] = [dict(ts=iso(r.ts.to_pydatetime()), kw=float(r.kw)) for r in df.sort_values("ts").itertuples()]
    return d


@router.patch("/anomalies/{aid}/review")
def review_anomaly(aid: int, body: ReviewIn, u: User = Depends(require("super_admin", "energy_manager", "zone_manager")), db: Session = Depends(get_db)):
    a = db.get(Anomaly, aid)
    if not a:
        raise HTTPException(404, "Anomaly not found")
    check_building(db, u, db.get(Building, a.building_id))
    a.status = body.status; a.review_note = body.note; a.reviewed_by = u.id
    audit(db, u.id, "anomaly_review", "anomaly", aid, dict(status=body.status)); db.commit()
    return dict(id=a.id, status=a.status)


@router.post("/anomalies/detect")
def detect(u: User = Depends(require(*MANAGE)), db: Session = Depends(get_db)):
    n = anomaly_service.run_detection(db); audit(db, u.id, "anomaly_detection_run", "anomaly", detail=dict(new=n)); db.commit()
    return dict(new_anomalies=n)


@router.get("/anomalies-evaluation")
def anomaly_eval(u: User = Depends(current_user)):
    f = REPORTS / "anomaly_evaluation.json"
    return json.loads(f.read_text()) if f.exists() else {}


# ---------------- Cooling ----------------
@router.get("/cooling/overview")
def cooling_overview(days: int = 14, u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = cooling_service.analysis(db, days, zone_scope(db, u))
    if u.role == "viewer":
        rows = [r for r in rows if r["zone"] != "Residential"]
    tot = sum(r["cooling_kwh"] for r in rows)
    return dict(days=days, data_mode="SIMULATED DEMONSTRATION DATA", cooling_kwh=tot, total_kwh=sum(r["total_kwh"] for r in rows),
                hvac_share_pct=tot / max(1, sum(r["total_kwh"] for r in rows)) * 100, flagged=sum(1 for r in rows if r["schedule_flag"]),
                est_saving_kwh=sum(r["est_saving_kwh"] for r in rows if r["schedule_flag"]), est_saving_cost=sum(r["est_saving_cost"] for r in rows if r["schedule_flag"]),
                saving_note="ESTIMATED against the observed baseline; not a measured or guaranteed reduction.")


@router.get("/cooling/analysis")
def cooling_analysis(days: int = 14, zone: str | None = None, u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = cooling_service.analysis(db, days, zone_scope(db, u))
    if u.role == "viewer":
        rows = [r for r in rows if r["zone"] != "Residential"]
    if zone:
        rows = [r for r in rows if r["zone"].lower() == zone.lower()]
    return dict(items=rows)


class CoolIn(BaseModel):
    building_id: int
    days: int = Field(7, ge=2, le=30)


@router.post("/cooling/optimize")
def cooling_optimize(body: CoolIn, u: User = Depends(require(*MANAGE, "zone_manager")), db: Session = Depends(get_db)):
    b = db.get(Building, body.building_id)
    if not b:
        raise HTTPException(404, "Building not found")
    check_building(db, u, b)
    r = cooling_service.optimize(db, body.building_id, body.days)
    audit(db, u.id, "cooling_optimize", "building", b.id); db.commit()
    return r


# ---------------- Renewable ----------------
def _solar_actual_vs_fc(db, hours=48):
    now = pd.Timestamp(common.data_now(db)).floor("h")
    df = A.frame(db)
    w = common.weather_frame(db, (now - pd.Timedelta(hours=hours + 2)).to_pydatetime())
    w["ts"] = pd.to_datetime(w.timestamp).dt.floor("h")
    wh = w.groupby("ts").agg(irradiance=("irradiance", "mean"), cloud_cover=("cloud_cover", "mean"), temperature=("temperature", "mean")).reset_index()
    import joblib
    from ml.common import MODELS
    from ml.renewable.solar import FEATURES
    bundle = joblib.load(MODELS / "solar.joblib")
    loc = wh.ts + IST; wh["hour"] = loc.dt.hour; wh["doy"] = loc.dt.dayofyear; wh["capacity_kw"] = 400.0
    wh["pred"] = np.clip(bundle["model"].predict(wh[FEATURES]), 0, None)
    q = select(func.sum(RenewableReading.generation_kw).label("kw"), RenewableReading.timestamp).group_by(RenewableReading.timestamp).where(RenewableReading.timestamp >= (now - pd.Timedelta(hours=hours)).to_pydatetime())
    act = pd.read_sql(q, db.get_bind()); act["ts"] = pd.to_datetime(act.timestamp)
    m = wh.merge(act[["ts", "kw"]], on="ts", how="inner").tail(hours)
    return m, bundle["version"]


@router.get("/renewable/overview")
def renewable_overview(days: int = 7, u: User = Depends(current_user), db: Session = Depends(get_db)):
    assets = db.execute(select(RenewableAsset, Building.building_name).join(Building, Building.id == RenewableAsset.building_id)).all()
    now = common.data_now(db)
    rows = pd.read_sql(select(RenewableReading.timestamp, func.sum(RenewableReading.generation_kwh).label("kwh")).group_by(RenewableReading.timestamp)
                       .where(RenewableReading.timestamp >= now - dt.timedelta(days=days)), db.get_bind())
    rows["ts"] = pd.to_datetime(rows.timestamp)
    camp = A.hourly_campus(A.scoped(db, A.frame(db), u, None, None, None, None, pd.Timestamp(now) - pd.Timedelta(days=days), pd.Timestamp(now)))
    m = camp.merge(rows[["ts", "kwh"]].rename(columns={"kwh": "solar_kwh"}), on="ts", how="left").fillna(0)
    m["ldate"] = (m.ts + IST).dt.strftime("%Y-%m-%d")
    daily = m.groupby("ldate").agg(demand_kwh=("kwh", "sum"), solar_kwh=("solar_kwh", "sum")).reset_index()
    daily["renewable_pct"] = daily.solar_kwh / daily.demand_kwh * 100
    cmp_, ver = _solar_actual_vs_fc(db)
    mae = float((cmp_.pred - cmp_.kw).abs().mean()) if len(cmp_) else None
    return dict(data_mode="SIMULATED - not real campus generation", assets=[dict(id=a.id, building=n, type=a.asset_type, capacity_kw=a.installed_capacity_kw,
                status=a.status, data_source=a.data_source) for a, n in assets],
                total_capacity_kw=sum(a.installed_capacity_kw for a, _ in assets), solar_kwh=float(m.solar_kwh.sum()), demand_kwh=float(m.kwh.sum()),
                renewable_pct=float(m.solar_kwh.sum() / m.kwh.sum() * 100) if m.kwh.sum() else 0, wind=dict(supported=True, installed=False,
                note="Wind is supported by the schema but no wind asset exists; none is assumed."),
                battery=dict(available=False, note="No battery storage is assumed."),
                daily=daily.round(1).to_dict("records"),
                hourly=[dict(ts=iso(r.ts.to_pydatetime()), demand_kw=float(r.kw), solar_kw=float(r.solar_kwh)) for r in m.tail(72).itertuples()],
                actual_vs_forecast=[dict(ts=iso(r.ts.to_pydatetime()), actual_kw=float(r.kw), forecast_kw=float(r.pred)) for r in cmp_.itertuples()],
                forecast_mae_kw_48h=mae, forecast_model=ver, avf_note="Forecast uses observed weather inputs on held-out recent hours (backtest).")


@router.get("/renewable/forecast")
def renewable_forecast(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Forecast).where(Forecast.scope == "solar").order_by(Forecast.forecast_timestamp)).all()
    camp = db.scalars(select(Forecast).where(Forecast.scope == "campus", Forecast.horizon == "24_hours").order_by(Forecast.forecast_timestamp)).all()
    cd = {c.forecast_timestamp: c.predicted_demand_kw for c in camp}
    disp = dispatch([cd.get(r.forecast_timestamp, 0) for r in rows], [r.predicted_demand_kw for r in rows])
    items = [dict(ts=iso(r.forecast_timestamp), solar_kw=r.predicted_demand_kw, lower=r.lower_bound_kw, upper=r.upper_bound_kw,
                  demand_kw=cd.get(r.forecast_timestamp, 0), **d) for r, d in zip(rows, disp)]
    run = db.scalars(select(OptimizationRun).where(OptimizationRun.status != "infeasible").order_by(OptimizationRun.id.desc())).first()
    return dict(data_mode="SIMULATED", model_version=rows[0].model_version if rows else None, items=items,
                expected_solar_kwh=sum(i["solar_kw"] for i in items), expected_surplus_kwh=sum(i["surplus_kw"] for i in items),
                expected_deficit_kwh=sum(i["deficit_kw"] for i in items),
                renewable_share_pct=sum(i["solar_used_kw"] for i in items) / max(1, sum(i["demand_kw"] for i in items)) * 100,
                uncertainty="80% interval from validation residuals",
                load_shifting=[dict(load=s["load"], reason=s["reason"], moved_kwh=s["moved_kwh"]) for s in (run.result.get("shifts", []) if run else [])])


@router.post("/renewable/forecast/run")
def renewable_run(u: User = Depends(require(*MANAGE)), db: Session = Depends(get_db)):
    forecast_service.run_solar_forecast(db); audit(db, u.id, "solar_forecast_run", "forecast"); db.commit()
    return dict(ok=True)


# ---------------- Optimization ----------------
class OptIn(BaseModel):
    peak_penalty: float = Field(2.0, ge=0, le=100)
    waste_lambda: float = Field(0.5, ge=0, le=100)
    peak_cap_kw: float | None = Field(None, gt=0)


def run_out(r: OptimizationRun, full=True):
    d = dict(id=r.id, created_at=iso(r.created_at), kind=r.kind, status=r.status, mode=r.mode, parameters=r.parameters, approved_by=r.approved_by)
    res = r.result or {}
    d["summary"] = dict(status=res.get("status"), cost_difference=res.get("cost_difference"), peak_reduction_kw=res.get("peak_reduction_kw"),
                        baseline_cost=(res.get("baseline") or {}).get("cost"), optimized_cost=(res.get("optimized") or {}).get("cost"),
                        baseline_peak_kw=(res.get("baseline") or {}).get("peak_kw"), optimized_peak_kw=(res.get("optimized") or {}).get("peak_kw"),
                        message=res.get("message"))
    if full:
        d["result"] = res
    return d


@router.post("/optimization/run")
def opt_run(body: OptIn, u: User = Depends(require(*MANAGE)), db: Session = Depends(get_db)):
    r = optimization_service.run_load_shifting(db, u.id, body.peak_penalty, body.waste_lambda, body.peak_cap_kw)
    audit(db, u.id, "optimization_run", "optimization_run", r.id); db.commit()
    return run_out(r)


@router.get("/optimization/runs")
def opt_runs(limit: int = Query(20, le=100), u: User = Depends(current_user), db: Session = Depends(get_db)):
    return dict(items=[run_out(r, False) for r in db.scalars(select(OptimizationRun).order_by(OptimizationRun.id.desc()).limit(limit))])


@router.get("/optimization/{rid}")
def opt_get(rid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(OptimizationRun, rid)
    if not r:
        raise HTTPException(404, "Run not found")
    return run_out(r)


@router.post("/optimization/{rid}/approve")
def opt_approve(rid: int, u: User = Depends(require(*MANAGE)), db: Session = Depends(get_db)):
    r = db.get(OptimizationRun, rid)
    if not r:
        raise HTTPException(404, "Run not found")
    if r.status != "pending_review":
        raise HTTPException(409, f"Run is '{r.status}', only pending_review runs can be approved")
    r.status = "approved"; r.approved_by = u.id
    audit(db, u.id, "optimization_approved", "optimization_run", rid, dict(note="recommendation only; no equipment controlled")); db.commit()
    return run_out(r, False) | dict(note="Approved as a recommendation. GRIDWISE AI does not control equipment.")


# ---------------- Recommendations ----------------
class RecPatch(BaseModel):
    status: str | None = Field(None, pattern="^(pending|approved|rejected|investigating|implemented)$")
    implemented_at: dt.datetime | None = None
    measured_saving_kwh: float | None = Field(None, ge=0)
    review_note: str | None = Field(None, max_length=1000)


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject|investigate)$")
    note: str | None = None


def r_out(r: Recommendation, b: Building | None, zt: str | None):
    return dict(id=r.id, building_id=r.building_id, building=b.building_name if b else "Campus-wide", zone=zt or "Campus", title=r.title,
                description=r.description, type=r.recommendation_type, category=r.category, priority=r.priority,
                estimated_energy_saving_kwh=r.estimated_energy_saving_kwh, estimated_cost_saving=r.estimated_cost_saving,
                confidence=r.confidence, recommended_action=r.recommended_action, evidence=r.supporting_evidence, status=r.status,
                implemented_at=iso(r.implemented_at) if r.implemented_at else None, measured_saving_kwh=r.measured_saving_kwh,
                review_note=r.review_note, created_at=iso(r.created_at),
                saving_label="MEASURED" if r.measured_saving_kwh is not None else "ESTIMATED (not achieved)")


@router.get("/recommendations")
def recs(status: str | None = None, type: str | None = None, priority: str | None = None, zone: str | None = None,
         limit: int = Query(100, le=500), offset: int = 0, u: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Recommendation, Building, Zone.zone_type).outerjoin(Building, Building.id == Recommendation.building_id).outerjoin(Zone, Zone.id == Building.zone_id)
    sc = zone_scope(db, u)
    if sc is not None:
        q = q.where(Building.zone_id.in_(sc))
    if u.role == "viewer":
        q = q.where((Zone.zone_type.is_(None)) | (Zone.zone_type != "Residential"))
    for col, v in ((Recommendation.status, status), (Recommendation.recommendation_type, type), (Recommendation.priority, priority)):
        if v:
            q = q.where(col == v)
    if zone:
        q = q.where(Zone.zone_type == zone.capitalize())
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    order = Recommendation.id.desc()
    rows = db.execute(q.order_by(order).limit(limit).offset(offset)).all()
    items = [r_out(r, b, zt) for r, b, zt in rows]
    items.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["priority"]])
    return dict(total=total, items=items)


def _apply(r, body: RecPatch, u, db):
    ch = body.model_dump(exclude_unset=True)
    if ch.get("status") == "implemented":
        if r.status not in ("approved", "implemented"):
            raise HTTPException(409, "Only approved recommendations can be marked implemented")
        r.implemented_at = ch.get("implemented_at") or dt.datetime.utcnow()
    if ch.get("measured_saving_kwh") is not None:
        if r.status != "implemented" and ch.get("status") != "implemented":
            raise HTTPException(409, "Measured results can only be recorded for implemented actions")
        r.recommendation_type = "measured_saving"
    elif ch.get("status") == "implemented":
        r.recommendation_type = "verified_action"
    for k, v in ch.items():
        if k != "implemented_at":
            setattr(r, k, v)
    if ch.get("status") in ("approved", "rejected", "investigating", "implemented"):
        r.approved_by = u.id
    audit(db, u.id, "recommendation_update", "recommendation", r.id, {k: str(v) for k, v in ch.items()}); db.commit()


@router.patch("/recommendations/{rid}")
def rec_patch(rid: int, body: RecPatch, u: User = Depends(require(*MANAGE)), db: Session = Depends(get_db)):
    r = db.get(Recommendation, rid)
    if not r:
        raise HTTPException(404, "Recommendation not found")
    _apply(r, body, u, db)
    return r_out(r, db.get(Building, r.building_id) if r.building_id else None, None)


@router.post("/recommendations/{rid}/review")
def rec_review(rid: int, body: DecisionIn, u: User = Depends(require(*MANAGE, "zone_manager")), db: Session = Depends(get_db)):
    r = db.get(Recommendation, rid)
    if not r:
        raise HTTPException(404, "Recommendation not found")
    if r.building_id:
        check_building(db, u, db.get(Building, r.building_id))
    elif u.role == "zone_manager":
        raise HTTPException(403, "Campus-wide recommendations need a campus-level role")
    st = {"approve": "approved", "reject": "rejected", "investigate": "investigating"}[body.decision]
    if u.role == "zone_manager" and st != "investigating":
        raise HTTPException(403, "Zone managers may mark items for investigation / submit notes; approval requires facilities manager")
    _apply(r, RecPatch(status=st, review_note=body.note), u, db)
    return r_out(r, db.get(Building, r.building_id) if r.building_id else None, None)


@router.post("/recommendations/generate")
def rec_generate(u: User = Depends(require(*MANAGE)), db: Session = Depends(get_db)):
    n = recommendation_service.generate(db); audit(db, u.id, "recommendations_generated", "recommendation", detail=dict(new=n)); db.commit()
    return dict(new=n)
