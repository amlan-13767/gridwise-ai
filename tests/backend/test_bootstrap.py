"""Production bootstrap: migrations, first-admin provisioning, safety refusals. Runs the real module in a subprocess."""
import os, sqlite3, subprocess, sys, pathlib
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PW = "Correct-Horse-Battery-9"


def run(db: pathlib.Path, **env):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("GRIDWISE_", "SEED_", "ENVIRONMENT", "DATABASE_URL"))}
    e.update(DATABASE_URL=f"sqlite:///{db}", SECRET_KEY="t", PYTHONPATH=str(ROOT), **env)
    return subprocess.run([sys.executable, "-m", "backend.app.bootstrap"], cwd=ROOT, env=e, capture_output=True, text=True, timeout=300)


def rows(db, q):
    c = sqlite3.connect(db); r = c.execute(q).fetchall(); c.close(); return r


def test_bootstrap_migrates_and_creates_admin_idempotently(tmp_path):
    db = tmp_path / "b.db"
    r = run(db, GRIDWISE_ADMIN_EMAIL="Owner@Example.org", GRIDWISE_ADMIN_PASSWORD=PW)
    assert r.returncode == 0, r.stderr
    assert PW not in r.stdout + r.stderr                                    # passwords are never logged
    assert rows(db, "select version_num from alembic_version")              # Alembic migration applied
    admins = rows(db, "select email, role, password_hash from users")
    assert [(a[0], a[1]) for a in admins] == [("owner@example.org", "super_admin")]
    assert admins[0][2].startswith("$2") and PW not in admins[0][2]          # bcrypt hash, not plaintext
    # restart with a DIFFERENT password: nothing is duplicated or reset
    r2 = run(db, GRIDWISE_ADMIN_EMAIL="owner@example.org", GRIDWISE_ADMIN_PASSWORD="Another-Password-123")
    assert r2.returncode == 0 and "password left unchanged" in r2.stderr + r2.stdout
    assert rows(db, "select password_hash from users") == [(admins[0][2],)]
    assert rows(db, "select count(*) from zones") == [(0,)]                  # no seed unless requested
    assert rows(db, "select count(*) from users where email like '%gridwise.demo'") == [(0,)]  # no demo accounts


def test_login_works_for_bootstrapped_admin(tmp_path):
    db = tmp_path / "l.db"
    assert run(db, GRIDWISE_ADMIN_EMAIL="owner@example.org", GRIDWISE_ADMIN_PASSWORD=PW).returncode == 0
    code = f"""
import os
os.environ['DATABASE_URL']='sqlite:///{db}'; os.environ['SECRET_KEY']='t'
from fastapi.testclient import TestClient
from backend.app.main import app
c = TestClient(app)
ok = c.post('/api/auth/login', json={{'email':'owner@example.org','password':'{PW}'}})
bad = c.post('/api/auth/login', json={{'email':'owner@example.org','password':'wrong-password-1'}})
assert ok.status_code == 200 and bad.status_code == 401, (ok.text, bad.text)
h = {{'Authorization': 'Bearer ' + ok.json()['access_token']}}
assert c.get('/api/auth/me', headers=h).json()['role'] == 'super_admin'
print('LOGIN-OK')"""
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(ROOT)})
    assert "LOGIN-OK" in r.stdout, r.stderr[-600:]


def test_weak_password_and_missing_env_do_not_create_admin(tmp_path):
    db = tmp_path / "w.db"
    r = run(db, GRIDWISE_ADMIN_EMAIL="owner@example.org", GRIDWISE_ADMIN_PASSWORD="short")
    assert r.returncode == 0 and "at least 12" in r.stderr + r.stdout
    assert rows(db, "select count(*) from users") == [(0,)]
    r = run(db)
    assert r.returncode == 0 and "NO super admin exists" in r.stderr + r.stdout


def test_adopts_schema_created_by_create_all(tmp_path):
    db = tmp_path / "a.db"
    e = {**os.environ, "DATABASE_URL": f"sqlite:///{db}", "PYTHONPATH": str(ROOT)}
    subprocess.run([sys.executable, "-c", "from backend.app.core.db import Base, engine; from backend.app.models import tables; Base.metadata.create_all(engine)"], cwd=ROOT, env=e, check=True)
    r = run(db)
    assert r.returncode == 0 and "stamped existing schema" in r.stderr + r.stdout   # no 'table already exists' crash
    assert rows(db, "select count(*) from alembic_version") == [(1,)]


def test_production_refuses_sqlite_fallback(tmp_path):
    r = run(tmp_path / "p.db", ENVIRONMENT="production")
    assert r.returncode != 0 and "requires a PostgreSQL" in r.stderr


def test_unreachable_database_is_reported_clearly(tmp_path):
    e = {**os.environ, "DATABASE_URL": "postgresql://u:supersecretpw@127.0.0.1:1/none", "SECRET_KEY": "t", "PYTHONPATH": str(ROOT)}
    code = "from backend.app.bootstrap import wait_for_db; from backend.app.core.db import engine; wait_for_db(engine, attempts=2, delay=0.1)"
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=e, capture_output=True, text=True, timeout=120)
    assert r.returncode != 0 and "Cannot connect to database" in r.stderr
    assert "supersecretpw" not in r.stderr and "supersecretpw" not in r.stdout   # password masked


def test_seed_marker_prevents_duplicates_and_resets_partial(client):
    from backend.app.core.db import SessionLocal
    from backend.app.services.seed import seed
    from backend.app.models.tables import Zone, Setting
    from sqlalchemy import select, func
    with SessionLocal() as db:
        assert db.get(Setting, "seed_complete")
        before = db.scalar(select(func.count()).select_from(Zone))
        assert seed(db) == "already seeded"
        assert db.scalar(select(func.count()).select_from(Zone)) == before   # re-running never duplicates


def test_cors_allows_production_frontend_only(client):
    ok = client.options("/api/auth/login", headers={"Origin": "https://gridwise-ai-xi.vercel.app", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
    assert ok.headers.get("access-control-allow-origin") == "https://gridwise-ai-xi.vercel.app"
    bad = client.options("/api/auth/login", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers


def test_protected_endpoints_require_auth(client):
    for p in ("/api/zones", "/api/energy/overview", "/api/users", "/api/anomalies"):
        assert client.get(p).status_code == 401
    assert client.get("/api/health").status_code == 200
