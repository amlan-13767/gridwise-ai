"""Background jobs (Celery + Redis). Heavy model TRAINING stays offline (scripts/train_models.py);
these tasks only run inference / detection with saved, reviewed artifacts."""
from celery import Celery
from ..core.config import settings

celery = Celery("gridwise", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery.conf.beat_schedule = {
    "forecast-hourly": {"task": "gridwise.forecast", "schedule": 3600.0},
    "anomalies-hourly": {"task": "gridwise.anomalies", "schedule": 3600.0},
}


@celery.task(name="gridwise.forecast")
def forecast():
    from ..core.db import SessionLocal
    from ..services import forecast_service
    with SessionLocal() as db:
        forecast_service.run_forecast(db); forecast_service.run_solar_forecast(db)
    return "ok"


@celery.task(name="gridwise.anomalies")
def anomalies():
    from ..core.db import SessionLocal
    from ..services import anomaly_service, recommendation_service
    with SessionLocal() as db:
        n = anomaly_service.run_detection(db, days=30); recommendation_service.generate(db)
    return n
