"""
Jobs API — query async job status
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import orm
from backend.models.schemas import JobStatus
from backend.auth.jwt import get_optional_user, get_current_user

router = APIRouter()


@router.get("", response_model=List[JobStatus])
def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[orm.User] = Depends(get_optional_user),
):
    q = db.query(orm.Job)
    if current_user:
        from sqlalchemy import or_
        q = q.filter(or_(orm.Job.user_id == current_user.id, orm.Job.user_id == None))
    if status:
        q = q.filter(orm.Job.status == status)
    jobs = q.order_by(orm.Job.created_at.desc()).limit(limit).all()
    return [JobStatus.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=JobStatus)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[orm.User] = Depends(get_optional_user),
):
    q = db.query(orm.Job).filter(orm.Job.id == job_id)
    if current_user:
        from sqlalchemy import or_
        q = q.filter(or_(orm.Job.user_id == current_user.id, orm.Job.user_id == None))
    job = q.first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus.model_validate(job)


@router.post("/requeue")
def requeue_stuck_jobs(db: Session = Depends(get_db)):
    """Re-enqueue jobs that have been pending/processing for too long."""
    from backend.workers.tasks import analyze_repository
    import os
    
    stuck_jobs = db.query(orm.Job).filter(
        orm.Job.status.in_(["pending", "processing"])
    ).all()
    
    count = 0
    github_token = os.getenv("GITHUB_TOKEN", "")
    
    for job in stuck_jobs:
        # We don't have the full payload in the DB, so we reconstruct it
        # Note: This is a simplified reconstruction. For a full fix, we'd store the payload.
        # But since we have the repo/commit, we can trigger a fresh analysis.
        task_payload = {
            "repo_url": f"https://github.com/{job.repository}.git",
            "repo_full_name": job.repository,
            "commit_sha": job.commit_sha,
            "branch": job.branch,
            "changed_files": [],
            "pr_number": None,
            "github_token": github_token,
        }
        analyze_repository.apply_async(
            args=[job.id, task_payload],
            queue="analysis_v1"
        )
        count += 1
        
    return {"status": "ok", "requeued_count": count}
