from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .core.db import Base, engine
from .models import tables  # noqa: F401
from .api import auth, campus, energy, intel, ops


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="GRIDWISE AI API", version="1.0.0", lifespan=lifespan,
              description="Smart campus energy intelligence. Demo data is SIMULATED. Monitoring and recommendation only - no equipment control.")
origins = [settings.FRONTEND_URL, "http://localhost:3000", "http://127.0.0.1:3000"] + [o for o in settings.EXTRA_CORS_ORIGINS.split(",") if o]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_origin_regex=r"https://gridwise-ai[a-z0-9-]*\.vercel\.app",
                   allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type", "X-Device-Key"])
for r in (auth.router, campus.router, energy.router, intel.router, ops.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return dict(status="ok", mode="monitoring_and_recommendation_only", data="SIMULATED DEMONSTRATION DATA" if settings.DEMO_MODE else "see source labels")
