from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..core.db import get_db
from ..core.deps import current_user, require, audit, ADMIN
from ..core.security import hash_password, verify_password, create_token
from ..models.tables import User, Zone

router = APIRouter(prefix="/api/auth", tags=["auth"])
PW = Field(min_length=10, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = PW
    role: str = Field(pattern="^(super_admin|energy_manager|zone_manager|viewer)$")
    assigned_zone_id: int | None = None


def user_out(u: User):
    return dict(id=u.id, name=u.name, email=u.email, role=u.role, assigned_zone_id=u.assigned_zone_id,
                is_active=u.is_active, created_at=u.created_at.isoformat())


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if not u or not u.is_active or not verify_password(body.password, u.password_hash):
        audit(db, u.id if u else None, "login_failed", "user", body.email); db.commit()
        raise HTTPException(401, "Invalid email or password")
    audit(db, u.id, "login", "user", u.id); db.commit()
    return dict(access_token=create_token(str(u.id), u.role), token_type="bearer", user=user_out(u))


@router.post("/logout")
def logout(u: User = Depends(current_user), db: Session = Depends(get_db)):
    audit(db, u.id, "logout", "user", u.id); db.commit()
    return {"ok": True, "detail": "Token is stateless; discard it client-side."}


@router.get("/me")
def me(u: User = Depends(current_user)):
    return user_out(u)


@router.post("/register", status_code=201)
def register(body: RegisterIn, admin: User = Depends(require(*ADMIN)), db: Session = Depends(get_db)):
    """Admin-only user creation. There is NO public registration."""
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "Email already registered")
    if body.role == "zone_manager" and not (body.assigned_zone_id and db.get(Zone, body.assigned_zone_id)):
        raise HTTPException(422, "zone_manager requires a valid assigned_zone_id")
    u = User(name=body.name, email=body.email.lower(), password_hash=hash_password(body.password), role=body.role,
             assigned_zone_id=body.assigned_zone_id)
    db.add(u); db.flush(); audit(db, admin.id, "user_created", "user", u.id, dict(role=u.role)); db.commit()
    return user_out(u)
