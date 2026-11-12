"""Seed the database with the SIMULATED campus (never real NIT Rourkela measurements)."""
import datetime as dt, json, os, hmac, hashlib
import pandas as pd
from sqlalchemy import insert, select, func, delete, update
from sqlalchemy.orm import Session
from ..core.config import settings
from ..core.security import hash_password
from ..models.tables import *
from ml.common import load_buildings, DATA, REPORTS

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


SEED_MARK = "seed_complete"
SIM_TABLES_IN_DELETE_ORDER = [Recommendation, Anomaly, Forecast, OptimizationRun, RenewableReading, RenewableAsset, OccupancyRecord,
                              WeatherReading, EnergyReading, BuildingArea, Meter, Building, Zone, EnergyTariff, ModelVersion, Notification]


def _reset_simulated(db: Session) -> bool:
    """Remove a half-finished SIMULATED seed. Refuses if any real data exists. Users/audit logs are kept."""
    if db.scalar(select(func.count()).select_from(Meter).where(Meter.data_source != "simulated")) or \
       db.scalar(select(func.count()).select_from(Building).where(Building.data_source != "simulated")):
        return False
    db.execute(update(User).values(assigned_zone_id=None))
    for m in SIM_TABLES_IN_DELETE_ORDER:
        db.execute(delete(m))
    db.execute(delete(Setting))
    db.commit()
    return True


def seed(db: Session, with_demo_users=True, run_ml=True):
    from . import forecast_service, anomaly_service, recommendation_service, optimization_service, model_service
    if db.get(Setting, SEED_MARK):
        return "already seeded"
    if db.scalar(select(func.count()).select_from(Zone)):
        if not _reset_simulated(db):
            return "database already has non-simulated campus data: refusing to seed"
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
    cols = ["timestamp", "building_id", "zone_type", "energy_consumption_kwh", "power_demand_kw", "voltage", "current", "cooling_load_kw",
            "indoor_temperature", "temperature", "humidity", "cloud_cover", "irradiance", "occupancy", "solar_generation_kw"]
    df = pd.read_csv(DATA / "readings.csv.gz", usecols=cols, parse_dates=["timestamp"])
    for c in cols[3:-2] + ["solar_generation_kw"]:
        df[c] = df[c].astype("float32")
    if df.timestamp.dt.tz is not None:
        df["timestamp"] = df.timestamp.dt.tz_localize(None)
    occ_basis = {"Academic": "scheduled", "Hostel": "estimated", "Residential": "estimated"}
    sol_codes = sorted(set(df.loc[df.solar_generation_kw > 0, "building_id"]))
    assets = {}
    for code in sol_codes:
        a = RenewableAsset(building_id=bmap[code].id, asset_type="solar", installed_capacity_kw=100.0, status="active", data_source="simulated")
        db.add(a); assets[code] = a
    db.flush()
    first = True
    for code, g in df.groupby("building_id", sort=False):  # one building at a time keeps peak memory low (Render free = 512 MB)
        mid = meters[code].id
        _bulk(db, EnergyReading, [dict(meter_id=mid, timestamp=t.to_pydatetime(), energy_consumption_kwh=float(c), power_demand_kw=float(d), voltage=float(e),
                                       current=float(f), cooling_load_kw=float(k), indoor_temperature=float(h), data_source="simulated", quality_status="good")
                                  for t, c, d, e, f, k, h in zip(g.timestamp, g.energy_consumption_kwh, g.power_demand_kw, g.voltage, g.current, g.cooling_load_kw, g.indoor_temperature)])
        hh = g[g.timestamp.dt.minute == 0]
        _bulk(db, OccupancyRecord, [dict(building_id=bmap[code].id, timestamp=t.to_pydatetime(), occupancy=int(o), occupancy_basis=occ_basis[z], data_source="simulated")
                                    for t, o, z in zip(hh.timestamp, hh.occupancy, hh.zone_type)])
        if first:
            _bulk(db, WeatherReading, [dict(timestamp=t.to_pydatetime(), temperature=float(a), humidity=float(b), cloud_cover=float(c), irradiance=float(d), data_source="simulated")
                                       for t, a, b, c, d in zip(g.timestamp, g.temperature, g.humidity, g.cloud_cover, g.irradiance)])
            first = False
        if code in assets:
            gg = g.assign(hr=g.timestamp.dt.floor("h")).groupby("hr").solar_generation_kw.mean().reset_index()
            _bulk(db, RenewableReading, [dict(renewable_asset_id=assets[code].id, timestamp=t.to_pydatetime(), generation_kw=float(k), generation_kwh=float(k), data_source="simulated")
                                         for t, k in zip(gg.hr, gg.solar_generation_kw)])
        db.flush()
    del df
    for n, s_, e, r in (("Off-peak", 0, 18, 6.0), ("Evening peak", 18, 22, 8.5), ("Late", 22, 24, 6.0)):
        db.add(EnergyTariff(name=n, start_hour=s_, end_hour=e, rate_per_kwh=r, is_assumption=True))
    for k, v in (("grid_emissions_factor", settings.GRID_EMISSIONS_FACTOR), ("electricity_tariff", settings.ELECTRICITY_TARIFF),
                 ("reporting_period_days", 30), ("renewable_accounting", "avoided_grid_emissions"),
                 ("operating_start_hour", 8), ("operating_end_hour", 18), ("setback_min_fraction", 0.25),
                 ("data_mode", "SIMULATED DEMONSTRATION DATA")):
        db.add(Setting(key=k, value=str(v)))
    if with_demo_users:
        for n, e, r, z in DEMO_USERS:
            if not db.scalar(select(User).where(User.email == e)):
                db.add(User(name=n, email=e, password_hash=hash_password(DEMO_PASSWORD), role=r, assigned_zone_id=zones[z].id if z else None))
    db.commit()
    if run_ml:
        model_service.register_models(db)
        forecast_service.run_forecast(db)
        forecast_service.run_solar_forecast(db)
        anomaly_service.run_detection(db)
        optimization_service.run_load_shifting(db, user_id=None)
        recommendation_service.generate(db)
    db.add(Setting(key=SEED_MARK, value=dt.datetime.utcnow().isoformat()))
    db.commit()
    return "seeded"
