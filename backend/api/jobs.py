"""
Jobs API — user-scoped job status tracking. Users only see their own jobs.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import orm
from backend.models.schemas import JobStatus
from backend.auth.jwt import get_current_user

router = APIRouter()


@router.get("", response_model=List[JobStatus])
def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: orm.User = Depends(get_current_user),  # Always require auth
):
    """List jobs — only returns the authenticated user's own jobs."""
    q = db.query(orm.Job).filter(orm.Job.user_id == current_user.id)
    if status:
        q = q.filter(orm.Job.status == status)
    jobs = q.order_by(orm.Job.created_at.desc()).limit(limit).all()
    return [JobStatus.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=JobStatus)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: orm.User = Depends(get_current_user),
):
    """Get a job — user can only access their own jobs."""
    job = db.query(orm.Job).filter(
        orm.Job.id == job_id,
        orm.Job.user_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus.model_validate(job)


@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: orm.User = Depends(get_current_user),
):
    """Cancel a running or pending job."""
    job = db.query(orm.Job).filter(
        orm.Job.id == job_id,
        orm.Job.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job.status not in ["pending", "processing"]:
        return {"status": "already finished", "job_status": job.status}

    if job.celery_task_id:
        from backend.workers.celery_app import celery_app
        celery_app.control.revoke(job.celery_task_id, terminate=True)
    
    job.status = "failed"
    job.error_message = "Cancelled by user"
    db.commit()
    
    return {"status": "cancelled", "job_id": job_id}