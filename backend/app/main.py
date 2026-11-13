from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .core.db import Base, engine
from .models import tables  # noqa: F401
from .api import auth, campus, energy, intel, ops


@asynccontextmanager
async def lifespan(app):
    import anyio.to_thread
    # Render free = 512 MB: bound concurrent sync handlers so parallel dashboard requests cannot multiply pandas working sets
    anyio.to_thread.current_default_thread_limiter().total_tokens = int(__import__("os").getenv("API_THREADS", "6"))
    if settings.ENVIRONMENT != "production":  # production schema is managed by Alembic (see bootstrap)
        Base.metadata.create_all(engine)
    if settings.ENVIRONMENT == "production":
        import threading

        def warm():  # build the cached analytics frame in the background so the first dashboard load is fast
            try:
                from .core.db import SessionLocal
                from .services import analytics
                with SessionLocal() as db:
                    analytics.frame(db)
            except Exception:  # noqa: BLE001
                pass
        threading.Thread(target=warm, daemon=True, name="warmup").start()
    yield


app = FastAPI(title="GRIDWISE AI API", version="1.0.0", lifespan=lifespan,
              description="Smart campus energy intelligence. Demo data is SIMULATED. Monitoring and recommendation only - no equipment control.")
from .core.cache import ResponseCache
app.add_middleware(ResponseCache)  # added before CORS so CORS headers wrap cached responses too
origins = [settings.FRONTEND_URL, "http://localhost:3000", "http://127.0.0.1:3000"] + [o for o in settings.EXTRA_CORS_ORIGINS.split(",") if o]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_origin_regex=r"https://gridwise-ai[a-z0-9-]*\.vercel\.app",
                   allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type", "X-Device-Key"])
for r in (auth.router, campus.router, energy.router, intel.router, ops.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    """Liveness plus non-sensitive deployment state (booleans only) to diagnose first-run setup."""
    from sqlalchemy import select, func
    from .core.db import SessionLocal
    from .models.tables import User, Zone
    out = dict(status="ok", mode="monitoring_and_recommendation_only", data="SIMULATED DEMONSTRATION DATA" if settings.DEMO_MODE else "see source labels",
               version="1.1.4", environment=settings.ENVIRONMENT)
    try:
        with SessionLocal() as db:
            out.update(database="ok", simulated_data_loaded=bool(db.scalar(select(func.count()).select_from(Zone))),
                       first_admin_configured=bool(db.scalar(select(func.count()).select_from(User).where(User.role == "super_admin"))))
    except Exception:  # noqa: BLE001
        out.update(status="degraded", database="unreachable")
    return out
