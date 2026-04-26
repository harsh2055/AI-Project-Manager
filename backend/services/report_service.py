"""
Report Service — DB-backed report management with in-memory cache fallback
"""
import os
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from backend.models import orm
from backend.models.schemas import (
    AnalysisReport, ReportSummary, IssueWithSuggestion
)

# In-memory fallback (used when DB is unavailable or for legacy support)
_reports: Dict[str, AnalysisReport] = {}

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


def _severity_score(issues: List[IssueWithSuggestion]) -> float:
    weights = {"security": 3.0, "error": 2.0, "dependency": 1.5, "warning": 0.5}
    total = sum(weights.get(iws.issue.type, 0.5) for iws in issues)
    return min(round(total, 2), 10.0)


def create_report_db(
    db: Session,
    user_id: Optional[str],
    repository: str,
    commit_id: str,
    branch: str,
    analyzed_files: List[str],
    issues_with_suggestions: List[IssueWithSuggestion],
) -> AnalysisReport:
    score = _severity_score(issues_with_suggestions)
    report_id = str(uuid.uuid4())

    # Serialize issues for JSON storage
    issues_json = [iws.model_dump() for iws in issues_with_suggestions]

    report_orm = orm.Report(
        id=report_id,
        user_id=user_id,
        repository=repository,
        commit_id=commit_id,
        branch=branch,
        analyzed_files=analyzed_files,
        issues=issues_json,
        severity_score=score,
    )
    db.add(report_orm)
    db.commit()
    db.refresh(report_orm)

    schema = AnalysisReport(
        id=report_id,
        user_id=user_id,
        repository=repository,
        commit_id=commit_id,
        branch=branch,
        analyzed_files=analyzed_files,
        issues=issues_with_suggestions,
        severity_score=score,
    )
    _reports[report_id] = schema
    return schema


def get_report_db(db: Session, report_id: str, user_id: Optional[str] = None) -> Optional[AnalysisReport]:
    q = db.query(orm.Report).filter(orm.Report.id == report_id)
    if user_id:
        q = q.filter(orm.Report.user_id == user_id)
    report_orm = q.first()
    if not report_orm:
        return None
    return _orm_to_schema(report_orm)


def list_reports_db(
    db: Session,
    user_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    severity_min: Optional[float] = None,
    repository: Optional[str] = None,
) -> List[ReportSummary]:
    q = db.query(orm.Report)
    if user_id:
        q = q.filter(orm.Report.user_id == user_id)
    if severity_min is not None:
        q = q.filter(orm.Report.severity_score >= severity_min)
    if repository:
        q = q.filter(orm.Report.repository.ilike(f"%{repository}%"))
    reports = q.order_by(orm.Report.created_at.desc()).offset(offset).limit(limit).all()

    return [
        ReportSummary(
            id=r.id,
            repository=r.repository,
            commit_id=r.commit_id[:8],
            branch=r.branch,
            severity_score=r.severity_score,
            issue_count=len(r.issues or []),
            created_at=r.created_at,
            autofix_pr_url=r.autofix_pr_url,
        )
        for r in reports
    ]


def get_severity_trend(db: Session, user_id: Optional[str] = None, days: int = 30) -> List[dict]:
    """Return daily average severity scores for the dashboard chart."""
    from sqlalchemy import func
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    q = db.query(
        func.date(orm.Report.created_at).label("date"),
        func.avg(orm.Report.severity_score).label("avg_score"),
        func.count(orm.Report.id).label("count"),
    ).filter(orm.Report.created_at >= cutoff)
    if user_id:
        q = q.filter(orm.Report.user_id == user_id)
    rows = q.group_by(func.date(orm.Report.created_at)).order_by("date").all()
    return [{"date": str(r.date), "avg_score": round(r.avg_score, 2), "count": r.count} for r in rows]


def _orm_to_schema(r: orm.Report) -> AnalysisReport:
    issues = []
    for raw in (r.issues or []):
        try:
            issues.append(IssueWithSuggestion(**raw))
        except Exception:
            pass
    return AnalysisReport(
        id=r.id,
        user_id=r.user_id,
        repository=r.repository,
        commit_id=r.commit_id,
        branch=r.branch,
        analyzed_files=r.analyzed_files or [],
        issues=issues,
        severity_score=r.severity_score,
        github_comment_url=r.github_comment_url,
        github_pr_url=r.github_pr_url,
        autofix_pr_url=r.autofix_pr_url,
        created_at=r.created_at,
    )


def load_persisted_reports():
    """Load old JSON-persisted reports into memory on startup."""
    if not os.path.isdir(REPORTS_DIR):
        return
    for filename in os.listdir(REPORTS_DIR):
        if not filename.endswith(".json"):
            continue
        try:
            with open(os.path.join(REPORTS_DIR, filename)) as f:
                data = json.load(f)
            report = AnalysisReport.model_validate(data)
            _reports[report.id] = report
        except Exception:
            pass
