import json, datetime as dt
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models.tables import ModelVersion
from ml.common import REPORTS


def register_models(db: Session):
    """Register trained artifacts. New models start as pending_review; first-ever set is
    auto-registered as 'production' only in demo seeding (documented), later retrains need review."""
    f = REPORTS / "forecast_evaluation.json"
    if f.exists():
        r = json.loads(f.read_text())
        for hz, res in r["horizons"].items():
            best = res["selected_by_validation_rmse"]
            _upsert(db, f"demand_{hz}", f"{best}-{r['version']}", "demand_forecast", r["trained_at"], r["dataset"],
                    dict(test=res[best], baseline=res["baseline_hourly_average"],
                         improvement_vs_baseline_rmse_pct=res["improvement_vs_baseline_rmse_pct"],
                         all_models={k: v for k, v in res.items() if isinstance(v, dict) and "rmse" in v}))
    f = REPORTS / "solar_evaluation.json"
    if f.exists():
        r = json.loads(f.read_text()); best = r["metrics"]["selected_by_validation_rmse"]
        _upsert(db, "solar_generation", f"{best}-{r['version']}", "solar_forecast", r["trained_at"], r["dataset"],
                dict(test=r["metrics"][best], baseline=r["metrics"]["baseline_hourly_average"],
                     all_models={k: v for k, v in r["metrics"].items() if isinstance(v, dict) and "rmse" in v}))
    f = REPORTS / "anomaly_evaluation.json"
    if f.exists():
        r = json.loads(f.read_text())
        _upsert(db, "anomaly_detector", "robust-zscore+isoforest-v1", "anomaly_detection", dt.datetime.utcnow().isoformat(),
                "SIMULATED with injected anomalies", r)
    db.commit()


def _upsert(db, name, version, task, trained_at, dataset, metrics):
    mv = db.scalar(select(ModelVersion).where(ModelVersion.name == name, ModelVersion.version == version, ModelVersion.task == task))
    ta = dt.datetime.fromisoformat(trained_at.replace("Z", "+00:00")).replace(tzinfo=None)
    if mv:
        mv.metrics = metrics; mv.trained_at = ta
    else:
        db.add(ModelVersion(name=name, version=version, task=task, trained_at=ta, training_dataset=dataset,
                            metrics=metrics, status="pending_review"))


def touch_prediction(db, task):
    for mv in db.scalars(select(ModelVersion).where(ModelVersion.task == task)):
        mv.last_prediction_at = dt.datetime.utcnow()
