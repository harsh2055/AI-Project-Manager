"""
AI Project Manager — Production FastAPI Application
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.database import engine, Base
from backend.api import webhook, reports, auth, jobs
from backend.services.report_service import load_persisted_reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure schema is up to date
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("users")]
        
        if "webhook_secret" not in columns:
            print("Detected missing webhook_secret column. Migrating...")
            with engine.begin() as conn:
                # 1. Add column as nullable
                conn.execute(text("ALTER TABLE users ADD COLUMN webhook_secret VARCHAR"))
                # 2. Populate with ID
                conn.execute(text("UPDATE users SET webhook_secret = id WHERE webhook_secret IS NULL"))
                
                # PostgreSQL specific: Set NOT NULL and UNIQUE
                if "postgresql" in str(engine.url):
                    conn.execute(text("ALTER TABLE users ALTER COLUMN webhook_secret SET NOT NULL"))
                    conn.execute(text("ALTER TABLE users ADD CONSTRAINT uq_users_webhook_secret UNIQUE (webhook_secret)"))
                
                print("Manual migration successful")
    except Exception as e:
        print(f"Manual migration error: {e}")

    # Ensure tables exist (fallback)
    Base.metadata.create_all(bind=engine)
    load_persisted_reports()
    yield
    # Shutdown (nothing needed)


app = FastAPI(
    title="AI Project Manager",
    description="Automated DevOps assistant with GitHub webhook integration",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(webhook.router, prefix="/api/webhook", tags=["webhook"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.2"}


@app.get("/debug/schema")
async def debug_schema():
    from sqlalchemy import inspect
    inspector = inspect(engine)
    columns = inspector.get_columns("users")
    return {"users_columns": [c["name"] for c in columns]}


# Serve frontend
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "index.html"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(frontend_path, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_path, "index.html"))
