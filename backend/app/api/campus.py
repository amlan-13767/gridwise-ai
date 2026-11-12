from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..core.db import get_db
from ..core.deps import current_user, require, audit, check_building, zone_scope, ADMIN, MANAGE
from ..models.tables import Zone, Building, BuildingArea, Meter, EnergyReading, User
from ..services import analytics

router = APIRouter(prefix="/api", tags=["campus"])


class ZoneIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    zone_type: str = Field(pattern="^(Academic|Hostel|Residential)$")
    description: str = ""


class BuildingIn(BaseModel):
    zone_id: int
    code: str = Field(min_length=2, max_length=20)
    building_name: str = Field(min_length=2, max_length=150)
    building_type: str
    floor_area: float | None = Field(None, gt=0)
    capacity: int | None = Field(None, ge=0)
    location_latitude: float | None = Field(None, ge=-90, le=90)
    location_longitude: float | None = Field(None, ge=-180, le=180)


class BuildingPatch(BaseModel):
    building_name: str | None = None
    building_type: str | None = None
    floor_area: float | None = Field(None, gt=0)
    capacity: int | None = Field(None, ge=0)
    zone_id: int | None = None
    location_latitude: float | None = None
    location_longitude: float | None = None
    is_active: bool | None = None


class MeterIn(BaseModel):
    building_id: int
    meter_identifier: str = Field(min_length=3, max_length=50)
    meter_type: str = "main"
    communication_protocol: str = Field("mqtt", pattern="^(mqtt|modbus_tcp|modbus_rtu|http|manual)$")
    installation_location: str = ""
    data_source: str = Field("real", pattern="^(real|simulated)$")


class MeterPatch(BaseModel):
    status: str | None = Field(None, pattern="^(active|inactive|maintenance)$")
    installation_location: str | None = None
    meter_type: str | None = None


def b_out(b: Building, zt=None):
    return dict(id=b.id, code=b.code, zone_id=b.zone_id, zone_type=zt or (b.zone.zone_type if b.zone else None),
                building_name=b.building_name, building_type=b.building_type, floor_area=b.floor_area, capacity=b.capacity,
                location_latitude=b.location_latitude, location_longitude=b.location_longitude,
                location_is_approximate=b.location_is_approximate, data_source=b.data_source, is_active=b.is_active)


@router.get("/zones")
def zones(u: User = Depends(current_user), db: Session = Depends(get_db)):
    sc = zone_scope(db, u)
    q = select(Zone) if sc is None else select(Zone).where(Zone.id.in_(sc))
    return [dict(id=z.id, name=z.name, zone_type=z.zone_type, description=z.description, is_active=z.is_active) for z in db.scalars(q)]


@router.post("/zones", status_code=201)
def create_zone(body: ZoneIn, u: User = Depends(require(*ADMIN)), db: Session = Depends(get_db)):
    if db.scalar(select(Zone).where(Zone.name == body.name)):
        raise HTTPException(409, "Zone name exists")
    z = Zone(**body.model_dump()); db.add(z); db.flush(); audit(db, u.id, "zone_created", "zone", z.id); db.commit()
    return dict(id=z.id, name=z.name, zone_type=z.zone_type, description=z.description, is_active=True)


@router.get("/buildings")
def buildings(zone_id: int | None = None, zone_type: str | None = None, include_inactive: bool = False,
              limit: int = Query(100, le=500), offset: int = 0, u: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Building, Zone.zone_type).join(Zone, Zone.id == Building.zone_id)
    sc = zone_scope(db, u)
    if sc is not None:
        q = q.where(Building.zone_id.in_(sc))
    if u.role == "viewer":
        q = q.where(Zone.zone_type != "Residential")  # privacy: no building-level residential data for viewers
    if zone_id:
        q = q.where(Building.zone_id == zone_id)
    if zone_type:
        q = q.where(Zone.zone_type == zone_type)
    if not include_inactive:
        q = q.where(Building.is_active == True)  # noqa
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.execute(q.order_by(Building.code).limit(limit).offset(offset)).all()
    return dict(total=total, items=[b_out(b, zt) for b, zt in rows])


@router.post("/buildings", status_code=201)
def create_building(body: BuildingIn, u: User = Depends(require(*ADMIN)), db: Session = Depends(get_db)):
    if not db.get(Zone, body.zone_id):
        raise HTTPException(404, "Zone not found")
    if db.scalar(select(Building).where(Building.code == body.code)):
        raise HTTPException(409, "Building code exists")
    b = Building(**body.model_dump(), data_source="real", location_is_approximate=body.location_latitude is None)
    db.add(b); db.flush(); audit(db, u.id, "building_created", "building", b.id); db.commit(); analytics.invalidate()
    return b_out(b)


@router.get("/buildings/{bid}")
def building(bid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    b = db.get(Building, bid)
    if not b:
        raise HTTPException(404, "Building not found")
    check_building(db, u, b)
    d = b_out(b)
    d["areas"] = [dict(id=a.id, name=a.name, area_type=a.area_type) for a in db.scalars(select(BuildingArea).where(BuildingArea.building_id == bid))]
    d["meters"] = [dict(id=m.id, meter_identifier=m.meter_identifier, status=m.status, data_source=m.data_source)
                   for m in db.scalars(select(Meter).where(Meter.building_id == bid))]
    return d


@router.patch("/buildings/{bid}")
def patch_building(bid: int, body: BuildingPatch, u: User = Depends(require(*ADMIN)), db: Session = Depends(get_db)):
    b = db.get(Building, bid)
    if not b:
        raise HTTPException(404, "Building not found")
    ch = body.model_dump(exclude_unset=True)
    if "zone_id" in ch and not db.get(Zone, ch["zone_id"]):
        raise HTTPException(404, "Zone not found")
    for k, v in ch.items():
        setattr(b, k, v)
    audit(db, u.id, "building_updated", "building", bid, ch); db.commit(); analytics.invalidate()
    return b_out(b)


@router.get("/meters")
def meters(building_id: int | None = None, u: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Meter, Building).join(Building, Building.id == Meter.building_id).join(Zone, Zone.id == Building.zone_id)
    sc = zone_scope(db, u)
    if sc is not None:
        q = q.where(Building.zone_id.in_(sc))
    if u.role == "viewer":
        q = q.where(Zone.zone_type != "Residential")
    if building_id:
        q = q.where(Meter.building_id == building_id)
    return [dict(id=m.id, building_id=m.building_id, building=b.building_name, meter_identifier=m.meter_identifier, meter_type=m.meter_type,
                 communication_protocol=m.communication_protocol, installation_location=m.installation_location,
                 data_source=m.data_source, status=m.status) for m, b in db.execute(q.order_by(Meter.id))]


@router.post("/meters", status_code=201)
def create_meter(body: MeterIn, u: User = Depends(require(*ADMIN)), db: Session = Depends(get_db)):
    if not db.get(Building, body.building_id):
        raise HTTPException(404, "Building not found")
    if db.scalar(select(Meter).where(Meter.meter_identifier == body.meter_identifier)):
        raise HTTPException(409, "Meter identifier exists")
    m = Meter(**body.model_dump()); db.add(m); db.flush(); audit(db, u.id, "meter_created", "meter", m.id); db.commit()
    return dict(id=m.id, meter_identifier=m.meter_identifier, status=m.status, data_source=m.data_source)


@router.patch("/meters/{mid}")
def patch_meter(mid: int, body: MeterPatch, u: User = Depends(require(*ADMIN)), db: Session = Depends(get_db)):
    m = db.get(Meter, mid)
    if not m:
        raise HTTPException(404, "Meter not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    audit(db, u.id, "meter_updated", "meter", mid); db.commit()
    return dict(id=m.id, status=m.status)


@router.get("/meters/{mid}/readings")
def meter_readings(mid: int, limit: int = Query(96, le=2000), offset: int = 0, u: User = Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(Meter, mid)
    if not m:
        raise HTTPException(404, "Meter not found")
    check_building(db, u, db.get(Building, m.building_id))
    rows = db.scalars(select(EnergyReading).where(EnergyReading.meter_id == mid).order_by(EnergyReading.timestamp.desc()).limit(limit).offset(offset)).all()
    return dict(meter=m.meter_identifier, data_source=m.data_source, items=[dict(
        timestamp=r.timestamp.isoformat() + "Z", energy_kwh=r.energy_consumption_kwh, power_kw=r.power_demand_kw, voltage=r.voltage,
        current=r.current, data_source=r.data_source, quality_status=r.quality_status) for r in rows])
