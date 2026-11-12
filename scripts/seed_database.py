import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from backend.app.core.db import Base, engine, SessionLocal
from backend.app.models import tables  # noqa
from backend.app.services.seed import seed
Base.metadata.create_all(engine)
with SessionLocal() as db:
    print(seed(db))
