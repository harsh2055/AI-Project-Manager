"""
Celery configuration — Redis broker + backend
"""
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

print(f"--- [CELERY] Starting Worker with Redis: {REDIS_URL.split('@')[-1]} ---")

celery_app = Celery(
    "ai_project_manager",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "backend.workers.tasks.analyze_repository": {"queue": "analysis_v1"},
        "backend.workers.tasks.apply_autofix": {"queue": "autofix_v1"},
    },
    task_soft_time_limit=300,   # 5 min soft limit
    task_time_limit=600,        # 10 min hard limit
)
