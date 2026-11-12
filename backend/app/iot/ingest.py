"""Shared ingestion pipeline for MQTT and HTTP. Validation, auth, dedupe, data-quality flags."""
import datetime as dt, hmac
from pydantic import BaseModel, Field, field_validator, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ..models.tables import Meter, EnergyReading

MAX_KW, MAX_DELAY = 5000.0, dt.timedelta(hours=1)


class ReadingIn(BaseModel):
    meter_id: str = Field(min_length=3, max_length=50)
    building_id: str | None = None
    timestamp: dt.datetime
    power_kw: float
    energy_kwh: float | None = None
    voltage: float | None = None
    current: float | None = None
    source: str = Field("real", pattern="^(real|simulated)$")

    @field_validator("timestamp")
    @classmethod
    def utc(cls, v):
        return v.astimezone(dt.timezone.utc).replace(tzinfo=None) if v.tzinfo else v


def device_key(secret: str, meter_identifier: str) -> str:
    import hashlib
    return hmac.new(secret.encode(), meter_identifier.encode(), hashlib.sha256).hexdigest()[:32]


def ingest(db: Session, payload: dict, key: str | None, secret: str, now: dt.datetime | None = None) -> dict:
    """Returns dict(status=stored|duplicate|rejected, reason). Never raises on bad data."""
    try:
        r = ReadingIn(**payload)
    except (ValidationError, TypeError) as e:
        return dict(status="rejected", reason="invalid payload: " + str(e).splitlines()[0][:120])
    m = db.scalar(select(Meter).where(Meter.meter_identifier == r.meter_id))
    if not m:
        return dict(status="rejected", reason="unknown meter")
    if not key or not hmac.compare_digest(key, device_key(secret, m.meter_identifier)):
        return dict(status="rejected", reason="device authentication failed")
    if m.status != "active":
        return dict(status="rejected", reason=f"meter is {m.status}")
    if (m.data_source == "simulated") != (r.source == "simulated"):
        return dict(status="rejected", reason="source label does not match the registered meter data_source")
    now = now or dt.datetime.utcnow()
    quality = "good"
    if r.power_kw < 0 or r.power_kw > MAX_KW:
        quality = "suspect"
    if r.timestamp > now + dt.timedelta(minutes=5):
        return dict(status="rejected", reason="timestamp in the future")
    if now - r.timestamp > MAX_DELAY:
        quality = "delayed" if quality == "good" else quality
    kwh = r.energy_kwh if r.energy_kwh is not None else max(r.power_kw, 0) * 0.25
    if r.energy_kwh is None:
        quality = quality if quality != "good" else "estimated"  # energy derived from power over 15 min
    if r.voltage is not None and not (150 <= r.voltage <= 280):
        quality = "suspect"
    if db.scalar(select(EnergyReading.id).where(EnergyReading.meter_id == m.id, EnergyReading.timestamp == r.timestamp)):
        return dict(status="duplicate", reason="reading already stored for this meter/timestamp")
    db.add(EnergyReading(meter_id=m.id, timestamp=r.timestamp, energy_consumption_kwh=kwh, power_demand_kw=r.power_kw,
                         voltage=r.voltage, current=r.current, data_source=r.source, quality_status=quality))
    if not m.last_seen or r.timestamp > m.last_seen:
        m.last_seen = r.timestamp
    try:
        db.commit()
    except IntegrityError:
        db.rollback(); return dict(status="duplicate", reason="reading already stored (race)")
    return dict(status="stored", quality=quality)


def device_status(m: Meter, ref: dt.datetime) -> str:
    if m.status != "active":
        return m.status
    if not m.last_seen:
        return "never_seen"
    age = ref - m.last_seen
    return "online" if age <= dt.timedelta(minutes=30) else "stale" if age <= dt.timedelta(hours=6) else "offline"
