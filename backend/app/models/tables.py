import datetime as dt
from sqlalchemy import (String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON,
                        UniqueConstraint, Index)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.db import Base


def now():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(30))  # super_admin|energy_manager|zone_manager|viewer
    assigned_zone_id: Mapped[int | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Zone(Base):
    __tablename__ = "zones"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    zone_type: Mapped[str] = mapped_column(String(30))  # Academic|Hostel|Residential
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Building(Base):
    __tablename__ = "buildings"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"), index=True)
    building_name: Mapped[str] = mapped_column(String(150))
    building_type: Mapped[str] = mapped_column(String(40))
    floor_area: Mapped[float | None] = mapped_column(Float)
    capacity: Mapped[int | None] = mapped_column(Integer)
    location_latitude: Mapped[float | None] = mapped_column(Float)
    location_longitude: Mapped[float | None] = mapped_column(Float)
    location_is_approximate: Mapped[bool] = mapped_column(Boolean, default=True)
    data_source: Mapped[str] = mapped_column(String(20), default="simulated")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    zone = relationship("Zone")


class BuildingArea(Base):
    __tablename__ = "building_areas"
    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    area_type: Mapped[str] = mapped_column(String(40), default="general")
    floor_area: Mapped[float | None] = mapped_column(Float)
    __table_args__ = (UniqueConstraint("building_id", "name"),)


class Meter(Base):
    __tablename__ = "meters"
    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"), index=True)
    meter_identifier: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    meter_type: Mapped[str] = mapped_column(String(40), default="main")
    communication_protocol: Mapped[str] = mapped_column(String(30), default="mqtt")
    installation_location: Mapped[str] = mapped_column(String(150), default="")
    data_source: Mapped[str] = mapped_column(String(20), default="simulated")
    status: Mapped[str] = mapped_column(String(20), default="active")
    api_key_hash: Mapped[str | None] = mapped_column(String(200))
    last_seen: Mapped[dt.datetime | None] = mapped_column(DateTime)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    building = relationship("Building")


class EnergyReading(Base):
    __tablename__ = "energy_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    meter_id: Mapped[int] = mapped_column(ForeignKey("meters.id"))
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime)
    energy_consumption_kwh: Mapped[float] = mapped_column(Float)
    power_demand_kw: Mapped[float] = mapped_column(Float)
    voltage: Mapped[float | None] = mapped_column(Float)
    current: Mapped[float | None] = mapped_column(Float)
    cooling_load_kw: Mapped[float | None] = mapped_column(Float)
    indoor_temperature: Mapped[float | None] = mapped_column(Float)
    data_source: Mapped[str] = mapped_column(String(20), default="simulated")
    quality_status: Mapped[str] = mapped_column(String(20), default="good")
    __table_args__ = (UniqueConstraint("meter_id", "timestamp", name="uq_reading_meter_ts"),
                      Index("ix_reading_ts", "timestamp"))


class WeatherReading(Base):
    __tablename__ = "weather_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, unique=True)
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)
    cloud_cover: Mapped[float | None] = mapped_column(Float)
    irradiance: Mapped[float | None] = mapped_column(Float)
    data_source: Mapped[str] = mapped_column(String(20), default="simulated")


class OccupancyRecord(Base):
    __tablename__ = "occupancy_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"))
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime)
    occupancy: Mapped[int] = mapped_column(Integer)
    occupancy_basis: Mapped[str] = mapped_column(String(20), default="estimated")  # observed|estimated|scheduled
    data_source: Mapped[str] = mapped_column(String(20), default="simulated")
    __table_args__ = (UniqueConstraint("building_id", "timestamp"),)


class RenewableAsset(Base):
    __tablename__ = "renewable_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"))
    asset_type: Mapped[str] = mapped_column(String(20), default="solar")
    installed_capacity_kw: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="active")
    data_source: Mapped[str] = mapped_column(String(20), default="simulated")


class RenewableReading(Base):
    __tablename__ = "renewable_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    renewable_asset_id: Mapped[int] = mapped_column(ForeignKey("renewable_assets.id"))
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime)
    generation_kw: Mapped[float] = mapped_column(Float)
    generation_kwh: Mapped[float] = mapped_column(Float)
    data_source: Mapped[str] = mapped_column(String(20), default="simulated")
    __table_args__ = (UniqueConstraint("renewable_asset_id", "timestamp"),)


class Forecast(Base):
    __tablename__ = "forecasts"
    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int | None] = mapped_column(ForeignKey("buildings.id"), index=True)  # null = campus
    scope: Mapped[str] = mapped_column(String(20), default="building")  # building|zone|campus|solar
    zone_type: Mapped[str | None] = mapped_column(String(30))
    forecast_timestamp: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    generated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    horizon: Mapped[str] = mapped_column(String(20))
    predicted_demand_kw: Mapped[float] = mapped_column(Float)
    lower_bound_kw: Mapped[float] = mapped_column(Float)
    upper_bound_kw: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(60))
    confidence_metadata: Mapped[dict | None] = mapped_column(JSON)


class Anomaly(Base):
    __tablename__ = "anomalies"
    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"), index=True)
    meter_id: Mapped[int | None] = mapped_column(ForeignKey("meters.id"))
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    observed_value: Mapped[float] = mapped_column(Float)
    expected_value: Mapped[float] = mapped_column(Float)
    deviation: Mapped[float] = mapped_column(Float)  # percent
    severity: Mapped[str] = mapped_column(String(20))
    detection_method: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|investigating|dismissed|resolved
    category: Mapped[str] = mapped_column(String(40), default="high_consumption")
    baseline_info: Mapped[dict | None] = mapped_column(JSON)
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (UniqueConstraint("building_id", "timestamp", "detection_method", name="uq_anom"),)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int | None] = mapped_column(ForeignKey("buildings.id"), index=True)
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text)
    recommendation_type: Mapped[str] = mapped_column(String(30))  # ai_generated|rule_based_alert|verified_action|measured_saving
    category: Mapped[str] = mapped_column(String(40), default="general")
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    estimated_energy_saving_kwh: Mapped[float | None] = mapped_column(Float)
    estimated_cost_saving: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[str] = mapped_column(String(20), default="medium")
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    supporting_evidence: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected|investigating|implemented
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    implemented_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    measured_saving_kwh: Mapped[float | None] = mapped_column(Float)
    review_note: Mapped[str | None] = mapped_column(Text)
    source_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(30), default="load_shifting")
    parameters: Mapped[dict | None] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="pending_review")  # pending_review|approved|infeasible
    mode: Mapped[str] = mapped_column(String(20), default="recommendation")  # never 'control'
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class EnergyTariff(Base):
    __tablename__ = "energy_tariffs"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    start_hour: Mapped[int] = mapped_column(Integer)
    end_hour: Mapped[int] = mapped_column(Integer)
    rate_per_kwh: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    is_assumption: Mapped[bool] = mapped_column(Boolean, default=True)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(60))
    task: Mapped[str] = mapped_column(String(40))
    trained_at: Mapped[dt.datetime] = mapped_column(DateTime)
    training_dataset: Mapped[str] = mapped_column(String(200))
    metrics: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="pending_review")  # pending_review|production|rejected|archived
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    last_prediction_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    __table_args__ = (UniqueConstraint("name", "version", "task"),)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[str] = mapped_column(String(20), default="info")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(40))
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, index=True)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(String(300))
