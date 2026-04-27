"""
Reports API — fully user-scoped, no unauthenticated access to report data.
"""
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import orm
from backend.models.schemas import AnalysisReport, ReportSummary
from backend.services.report_service import get_report_db, list_reports_db, get_severity_trend
from backend.auth.jwt import get_current_user  # Always require auth
from backend.workers.tasks import apply_autofix

router = APIRouter()


@router.get("", response_model=List[ReportSummary])
def list_reports(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    severity_min: Optional[float] = Query(None, ge=0, le=10),
    repository: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: orm.User = Depends(get_current_user),  # Auth required
):
    """List reports — only returns the authenticated user's own reports."""
    return list_reports_db(
        db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        severity_min=severity_min,
        repository=repository,
    )


@router.get("/trend")
def severity_trend(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: orm.User = Depends(get_current_user),
):
    """Return severity trend for the authenticated user only."""
    return get_severity_trend(db, user_id=current_user.id, days=days)


@router.get("/{report_id}", response_model=AnalysisReport)
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: orm.User = Depends(get_current_user),
):
    """Get a specific report — user can only access their own reports."""
    report = get_report_db(db, report_id, user_id=current_user.id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.post("/{report_id}/autofix")
def trigger_autofix(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: orm.User = Depends(get_current_user),
):
    """Trigger automated fix PR for a report owned by the current user."""
    if not current_user.github_token:
        raise HTTPException(status_code=400, detail="Connect your GitHub account first")

    report = get_report_db(db, report_id, user_id=current_user.id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    job = orm.Job(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        repository=report.repository,
        commit_sha=report.commit_id,
        branch=report.branch,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    task = apply_autofix.apply_async(
        args=[job.id, report_id, current_user.github_token, report.repository],
        queue="autofix_v1",
    )
    job.celery_task_id = task.id
    db.commit()

    return {"status": "queued", "job_id": job.id, "celery_task_id": task.id}


@router.delete("/{report_id}")
def delete_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: orm.User = Depends(get_current_user),
):
    """Delete a report — user can only delete their own reports."""
    report = db.query(orm.Report).filter(
        orm.Report.id == report_id,
        orm.Report.user_id == current_user.id,
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    db.delete(report)
    db.commit()
    return {"status": "deleted"}


@router.delete("")
def delete_all_reports(
    db: Session = Depends(get_db),
    current_user: orm.User = Depends(get_current_user),
):
    """Delete ALL reports for the authenticated user."""
    db.query(orm.Report).filter(orm.Report.user_id == current_user.id).delete()
    db.commit()
    return {"status": "all deleted"}