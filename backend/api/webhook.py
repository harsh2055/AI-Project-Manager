"""
Webhook route — validates and queues analysis jobs
"""
import os
import uuid
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session
from fastapi import Depends
from backend.database import get_db
from backend.models import orm
from backend.webhook import parse_webhook
from backend.workers.tasks import analyze_repository

router = APIRouter()


@router.post("/github")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receive GitHub webhook → validate → queue async job.
    Returns immediately with job_id.
    """
    result = await parse_webhook(request)

    # ping event returns dict directly
    if isinstance(result, dict):
        return result

    payload = result

    # Create job record
    job = orm.Job(
        id=str(uuid.uuid4()),
        repository=payload.repo_full_name,
        commit_sha=payload.commit_sha,
        branch=payload.branch,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Build task payload
    github_token = os.getenv("GITHUB_TOKEN", "")
    task_payload = {
        "repo_url": payload.repo_url,
        "repo_full_name": payload.repo_full_name,
        "commit_sha": payload.commit_sha,
        "branch": payload.branch,
        "changed_files": payload.changed_files,
        "pr_number": payload.pr_number,
        "github_token": github_token,
        "user_id": None,  # Webhook calls are unauthenticated
    }

    # Queue Celery task
    task = analyze_repository.apply_async(
        args=[job.id, task_payload],
        queue="analysis_v1",
    )
    job.celery_task_id = task.id
    db.commit()

    return {
        "status": "queued",
        "job_id": job.id,
        "celery_task_id": task.id,
        "repository": payload.repo_full_name,
        "commit": payload.commit_sha[:8],
    }
