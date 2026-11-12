"""Secure initial administrator creation:  python -m backend.app.cli create-admin --email you@x.org
Password is read from the GRIDWISE_ADMIN_PASSWORD env var or prompted (never passed on the command line)."""
import argparse, getpass, os, sys
from sqlalchemy import select
from .core.db import Base, engine, SessionLocal
from .core.security import hash_password
from .models import tables
from .models.tables import User


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-admin"); c.add_argument("--email", required=True); c.add_argument("--name", default="Administrator")
    a = ap.parse_args()
    pw = os.getenv("GRIDWISE_ADMIN_PASSWORD") or getpass.getpass("Password (min 12 chars): ")
    if len(pw) < 12:
        sys.exit("Password too short (min 12).")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == a.email.lower())):
            sys.exit("User exists.")
        db.add(User(name=a.name, email=a.email.lower(), password_hash=hash_password(pw), role="super_admin")); db.commit()
    print("Administrator created.")


if __name__ == "__main__":
    main()
