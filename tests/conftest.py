import os, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEST_DB = ROOT / "test_gridwise.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"  # separate test database
os.environ["SECRET_KEY"] = "test-secret-key"
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    from backend.app.core.db import Base, engine, SessionLocal
    from backend.app.models import tables  # noqa
    from backend.app.services.seed import seed
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    from backend.app.main import app
    with TestClient(app) as c:
        yield c
    TEST_DB.unlink(missing_ok=True)


def login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": "Gridwise#Demo1"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture(scope="session")
def admin(client): return login(client, "admin@gridwise.demo")
@pytest.fixture(scope="session")
def manager(client): return login(client, "manager@gridwise.demo")
@pytest.fixture(scope="session")
def zonemgr(client): return login(client, "zone@gridwise.demo")
@pytest.fixture(scope="session")
def viewer(client): return login(client, "viewer@gridwise.demo")
