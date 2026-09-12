import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as api_router
from app.database import engine, Base, SessionLocal
from app.config import get_settings
from app.db_migrate import run_additive_migration

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

Base.metadata.create_all(bind=engine)
run_additive_migration(engine)


def _bootstrap_initial_admin():
    """Creates exactly one admin account on first boot, and only if both
    INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD are set in the
    environment AND no user exists yet in the database. There is no
    hardcoded username/password anywhere in source - the normal way to
    create/reset an admin is backend/scripts/create_admin.py."""
    from app.models.domain import User
    from app.security.auth import get_password_hash

    if not (settings.INITIAL_ADMIN_USERNAME and settings.INITIAL_ADMIN_PASSWORD):
        return
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return
        if len(settings.INITIAL_ADMIN_PASSWORD) < 10:
            logger.warning("[BOOTSTRAP] INITIAL_ADMIN_PASSWORD is under 10 characters - skipping auto-created admin.")
            return
        db.add(User(
            username=settings.INITIAL_ADMIN_USERNAME,
            hashed_password=get_password_hash(settings.INITIAL_ADMIN_PASSWORD),
            role="ADMIN",
            is_active=True,
        ))
        db.commit()
        logger.warning(f"[BOOTSTRAP] Created initial admin account '{settings.INITIAL_ADMIN_USERNAME}' from environment variables.")
    finally:
        db.close()


_bootstrap_initial_admin()

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Not adding Strict-Transport-Security here - this dev server runs over
    # plain HTTP; forcing HSTS on an http:// origin can lock browsers out of
    # future non-TLS access. Add it at the production reverse proxy instead.
    return response


app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME} API"}
