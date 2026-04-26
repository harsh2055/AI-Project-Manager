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


@router.post("/github/{secret}")
async def github_webhook_secure(secret: str, request: Request, db: Session = Depends(get_db)):
    """
    Receive GitHub webhook with user secret → validate → queue async job.
    """
    # Find user by secret
    user = db.query(orm.User).filter(orm.User.webhook_secret == secret).first()
    if not user:
        raise HTTPException(status_code=404, detail="Invalid webhook secret")

    result = await parse_webhook(request)

    # ping event returns dict directly
    if isinstance(result, dict):
        return result

    payload = result

    # Create job record associated with user
    job = orm.Job(
        id=str(uuid.uuid4()),
        user_id=user.id,
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
        "user_id": user.id,
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


@router.post("/github")
async def github_webhook_legacy(request: Request, db: Session = Depends(get_db)):
    """
    Legacy anonymous webhook. Deprecated.
    """
    return await github_webhook_secure("legacy", request, db)
