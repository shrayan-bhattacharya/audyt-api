import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import audit, health
from app.routes.auth_routes import router as auth_router
from app.routes.history import router as history_router

# ── Ensure data files exist and admin user is seeded ──────────────────────────

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(_DATA_DIR, exist_ok=True)

for _path, _default in [
    (os.path.join(_DATA_DIR, "users.json"), []),
    (os.path.join(_DATA_DIR, "audits.json"), []),
]:
    if not os.path.exists(_path):
        with open(_path, "w") as _f:
            json.dump(_default, _f)

# Seed admin account on every startup (idempotent)
from app.services.auth import hash_password
from app.services.user_store import create_user, get_user_by_email

_ADMIN_EMAIL = "admin@greychain.ai"
_ADMIN_PASSWORD = "Admin@123"

if not get_user_by_email(_ADMIN_EMAIL):
    create_user(_ADMIN_EMAIL, hash_password(_ADMIN_PASSWORD))

# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Audyt.ai API",
    description="Verify AI-generated reports against source documents — claim by claim.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://audyt-web.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(audit.router)
app.include_router(auth_router)
app.include_router(history_router)
