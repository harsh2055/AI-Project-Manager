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
        q = q.filter(orm.Job.user_id == current_user.id)
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
        q = q.filter(orm.Job.user_id == current_user.id)
    job = q.first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus.model_validate(job)
