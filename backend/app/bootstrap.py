"""Production start-up tasks, run once per container start BEFORE the API:
  1. wait for / validate the database connection (clear errors, password never printed)
  2. apply Alembic migrations (adopting a pre-existing create_all schema with `stamp head`)
  3. create the first Super Administrator from GRIDWISE_ADMIN_EMAIL / GRIDWISE_ADMIN_PASSWORD (idempotent)
  4. optionally load the SIMULATED demo dataset when SEED_DEMO_DATA=true and the database is empty
All steps are safe to repeat. Nothing here prints passwords or secrets."""
import logging, re, sys, time
from pathlib import Path
from sqlalchemy import inspect, select, func, text
from sqlalchemy.engine import make_url
from .core.config import settings

log = logging.getLogger("gridwise.bootstrap")
ROOT = Path(__file__).resolve().parents[2]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def safe_url(url: str) -> str:
    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return "<unparseable DATABASE_URL>"


def wait_for_db(engine, attempts: int = 10, delay: float = 3.0):
    last = None
    for i in range(1, attempts + 1):
        try:
            with engine.connect() as c:
                c.execute(text("select 1"))
            log.info("Database reachable: %s (%s)", safe_url(str(engine.url)), engine.dialect.name)
            return
        except Exception as e:  # noqa: BLE001
            last = e
            log.warning("Database not reachable (attempt %d/%d): %s", i, attempts, type(e).__name__)
            time.sleep(delay)
    raise RuntimeError(f"Cannot connect to database {safe_url(str(engine.url))}: {type(last).__name__}. Check DATABASE_URL.") from last


def run_migrations(engine) -> str:
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(ROOT / "alembic.ini"))
    tables = set(inspect(engine).get_table_names())
    try:
        if "users" in tables and "alembic_version" not in tables:
            command.stamp(cfg, "head")  # schema was created earlier by create_all: adopt it, do not recreate
            return "stamped existing schema at head"
        command.upgrade(cfg, "head")
        return "upgraded to head"
    finally:
        logging.getLogger().setLevel(logging.INFO)  # alembic's fileConfig resets the root level to WARNING


def ensure_admin(db, email: str, password: str) -> str:
    from .core.security import hash_password
    from .models.tables import User
    if not email and not password:
        n = db.scalar(select(func.count()).select_from(User).where(User.role == "super_admin"))
        return "no admin env vars set; " + ("a super admin already exists" if n else
                                           "NO super admin exists: set GRIDWISE_ADMIN_EMAIL and GRIDWISE_ADMIN_PASSWORD and restart")
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError("GRIDWISE_ADMIN_EMAIL is not a valid email address")
    if db.scalar(select(User).where(User.email == email)):
        return f"admin {email} already exists: password left unchanged"
    if len(password) < 12:
        raise ValueError("GRIDWISE_ADMIN_PASSWORD must be at least 12 characters")
    db.add(User(name="Administrator", email=email, password_hash=hash_password(password), role="super_admin"))
    db.commit()
    return f"created super administrator {email}"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from .core.db import engine, SessionLocal
    try:
        wait_for_db(engine)
        log.info("Migrations: %s", run_migrations(engine))
    except Exception as e:  # noqa: BLE001
        log.error("FATAL database/migration failure: %s", e)
        return 1
    with SessionLocal() as db:
        try:
            log.info("Admin: %s", ensure_admin(db, settings.GRIDWISE_ADMIN_EMAIL, settings.GRIDWISE_ADMIN_PASSWORD))
        except ValueError as e:
            log.error("Admin bootstrap skipped: %s", e)
        if settings.SEED_DEMO_DATA:
            try:
                from .services.seed import seed
                log.info("Seed (SIMULATED data): %s", seed(db, with_demo_users=settings.SEED_DEMO_USERS))
            except Exception:  # noqa: BLE001
                log.exception("Seeding failed; API will still start and seeding is retried on next start")
    return 0


if __name__ == "__main__":
    sys.exit(main())
