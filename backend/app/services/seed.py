"""Seed the database with the SIMULATED campus (never real NIT Rourkela measurements)."""
import json, os, hmac, hashlib
import pandas as pd
from sqlalchemy import insert, select, func, delete
from sqlalchemy.orm import Session
from ..core.config import settings
from ..core.security import hash_password
from ..models.tables import *
from ml.common import load_readings, load_buildings, REPORTS

ZONE_DESC = {
    "Academic": "Simulated academic area: departments, labs, library, admin and common facilities.",
    "Hostel": "Simulated hostel area: hostel buildings, mess, water pumps, common areas.",
    "Residential": "Simulated residential area: quarters clusters and shared infrastructure (aggregate only).",
}
AREAS = {"ACD-03": [("Laboratory 1", "computer_lab"), ("Laboratory 2", "computer_lab"), ("Classrooms", "classroom")],
         "ACD-04": [("Reading Hall", "library"), ("Archives", "library")],
         "ACD-01": [("Classrooms", "classroom")], "HST-01": [("Mess", "mess"), ("Water Pumps", "pump"), ("Corridors", "common")]}
DEMO_USERS = [("Demo Administrator", "admin@gridwise.demo", "super_admin", None),
              ("Demo Facilities Manager", "manager@gridwise.demo", "energy_manager", None),
              ("Demo Zone Manager (Hostel)", "zone@gridwise.demo", "zone_manager", "Hostel"),
              ("Demo Auditor", "viewer@gridwise.demo", "viewer", None)]
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "Gridwise#Demo1")


def device_key(meter_identifier: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), meter_identifier.encode(), hashlib.sha256).hexdigest()[:32]


def _bulk(db, model, rows, chunk=8000):
    for i in range(0, len(rows), chunk):
        db.execute(insert(model), rows[i:i + chunk])


def seed(db: Session, with_demo_users=True, run_ml=True):
    from . import forecast_service, anomaly_service, recommendation_service, optimization_service, model_service
    if db.scalar(select(func.count()).select_from(Zone)):
        return "already seeded"
    zones = {}
    for zt in ("Academic", "Hostel", "Residential"):
        z = Zone(name=f"{zt} Area", zone_type=zt, description=ZONE_DESC[zt]); db.add(z); zones[zt] = z
    db.flush()
    bdf = load_buildings(); bmap = {}
    for r in bdf.itertuples():
        b = Building(code=r.building_id, zone_id=zones[r.zone_type].id, building_name=r.building_name,
                     building_type=r.building_type, floor_area=r.floor_area, capacity=r.capacity,
                     location_latitude=r.lat, location_longitude=r.lon, location_is_approximate=True)
        db.add(b); bmap[r.building_id] = b
    db.flush()
    for code, areas in AREAS.items():
        for n, t in areas:
            db.add(BuildingArea(building_id=bmap[code].id, name=n, area_type=t))
    meters = {}
    for code, b in bmap.items():
        m = Meter(building_id=b.id, meter_identifier=f"MTR-{code}", installation_location="SIMULATED main incomer",
                  communication_protocol="mqtt", data_source="simulated")
        db.add(m); meters[code] = m
    db.flush()
    df = load_readings()
    mid = {c: m.id for c, m in meters.items()}
    df["meter_pk"] = df.building_id.map(mid)
    df["ts"] = df.timestamp.dt.tz_localize(None) if df.timestamp.dt.tz is not None else df.timestamp
    rows = [dict(meter_id=int(a), timestamp=b.to_pydatetime(), energy_consumption_kwh=float(c), power_demand_kw=float(d),
                 voltage=float(e), current=float(f), cooling_load_kw=float(g), indoor_temperature=float(h),
                 data_source="simulated", quality_status="good")
            for a, b, c, d, e, f, g, h in zip(df.meter_pk, df.ts, df.energy_consumption_kwh, df.power_demand_kw,
                                              df.voltage, df.current, df.cooling_load_kw, df.indoor_temperature)]
    _bulk(db, EnergyReading, rows)
    w = df[df.building_id == df.building_id.iloc[0]]
    _bulk(db, WeatherReading, [dict(timestamp=t.to_pydatetime(), temperature=float(a), humidity=float(b), cloud_cover=float(c),
                                    irradiance=float(d), data_source="simulated")
                               for t, a, b, c, d in zip(w.ts, w.temperature, w.humidity, w.cloud_cover, w.irradiance)])
    hh = df[df.ts.dt.minute == 0]
    occ_basis = {"Academic": "scheduled", "Hostel": "estimated", "Residential": "estimated"}
    _bulk(db, OccupancyRecord, [dict(building_id=bmap[c].id, timestamp=t.to_pydatetime(), occupancy=int(o),
                                     occupancy_basis=occ_basis[z], data_source="simulated")
                                for c, t, o, z in zip(hh.building_id, hh.ts, hh.occupancy, hh.zone_type)])
    # renewable (simulated) on buildings that have solar in the dataset
    sol = hh[hh.solar_generation_kw > 0].building_id.unique().tolist() or []
    sol = sorted(set(df[df.solar_generation_kw > 0].building_id))
    for code in sol:
        a = RenewableAsset(building_id=bmap[code].id, asset_type="solar", installed_capacity_kw=100.0,
                           status="active", data_source="simulated")
        db.add(a); db.flush()
        g = df[df.building_id == code].copy(); g["hr"] = g.ts.dt.floor("h")
        gg = g.groupby("hr").solar_generation_kw.mean().reset_index()
        _bulk(db, RenewableReading, [dict(renewable_asset_id=a.id, timestamp=t.to_pydatetime(), generation_kw=float(k),
                                          generation_kwh=float(k), data_source="simulated") for t, k in zip(gg.hr, gg.solar_generation_kw)])
    for n, s, e, r in (("Off-peak", 0, 18, 6.0), ("Evening peak", 18, 22, 8.5), ("Late", 22, 24, 6.0)):
        db.add(EnergyTariff(name=n, start_hour=s, end_hour=e, rate_per_kwh=r, is_assumption=True))
    for k, v in (("grid_emissions_factor", settings.GRID_EMISSIONS_FACTOR), ("electricity_tariff", settings.ELECTRICITY_TARIFF),
                 ("reporting_period_days", 30), ("renewable_accounting", "avoided_grid_emissions"),
                 ("operating_start_hour", 8), ("operating_end_hour", 18), ("setback_min_fraction", 0.25),
                 ("data_mode", "SIMULATED DEMONSTRATION DATA")):
        db.add(Setting(key=k, value=str(v)))
    if with_demo_users:
        for n, e, r, z in DEMO_USERS:
            db.add(User(name=n, email=e, password_hash=hash_password(DEMO_PASSWORD), role=r,
                        assigned_zone_id=zones[z].id if z else None))
    db.commit()
    if run_ml:
        model_service.register_models(db)
        forecast_service.run_forecast(db)
        forecast_service.run_solar_forecast(db)
        anomaly_service.run_detection(db)
        optimization_service.run_load_shifting(db, user_id=None)
        recommendation_service.generate(db)
        db.commit()
    return "seeded"
