from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from .db import get_db
from .security import decode_token
from ..models.tables import User, Building, Zone, AuditLog

ROLES = ("super_admin", "energy_manager", "zone_manager", "viewer")


def current_user(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    data = decode_token(authorization.split(" ", 1)[1])
    if not data:
        raise HTTPException(401, "Invalid or expired token")
    u = db.get(User, int(data["sub"]))
    if not u or not u.is_active:
        raise HTTPException(401, "User inactive")
    return u


def require(*roles):
    def dep(u: User = Depends(current_user)) -> User:
        if u.role not in roles:
            raise HTTPException(403, f"Role '{u.role}' is not permitted for this action")
        return u
    return dep


ADMIN = ("super_admin",)
MANAGE = ("super_admin", "energy_manager")
ANY = ROLES


def zone_scope(db: Session, u: User) -> list[int] | None:
    """Zone ids visible to the user; None = all zones."""
    if u.role == "zone_manager":
        return [u.assigned_zone_id] if u.assigned_zone_id else []
    return None


def check_building(db: Session, u: User, b: Building, detail=True):
    scope = zone_scope(db, u)
    if scope is not None and b.zone_id not in scope:
        raise HTTPException(403, "Building is outside your authorised zone")
    zone = db.get(Zone, b.zone_id)
    if detail and zone and zone.zone_type == "Residential" and u.role == "viewer":
        raise HTTPException(403, "Building-level residential data is restricted for the viewer role (privacy)")


def audit(db: Session, user_id, action, entity=None, entity_id=None, detail=None):
    db.add(AuditLog(user_id=user_id, action=action, entity=entity,
                    entity_id=str(entity_id) if entity_id is not None else None, detail=detail))
