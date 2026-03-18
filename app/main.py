from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import audit, health

app = FastAPI(
    title="Audyt.ai API",
    description="Verify AI-generated reports against source documents — claim by claim.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(audit.router)
