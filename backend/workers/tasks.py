"""
Celery Tasks — async analysis and auto-fix pipeline
"""
import os
import logging
from datetime import datetime
from celery import shared_task
from backend.workers.celery_app import celery_app
from backend.database import SessionLocal
from backend.models import orm

logger = logging.getLogger(__name__)


def _update_job(db, job_id: str, **kwargs):
    job = db.query(orm.Job).filter(orm.Job.id == job_id).first()
    if job:
        for k, v in kwargs.items():
            setattr(job, k, v)
        job.updated_at = datetime.utcnow()
        db.commit()


@celery_app.task(bind=True, name="backend.workers.tasks.analyze_repository")
def analyze_repository(self, job_id: str, payload: dict):
    print(f"--- [CELERY] Task Received: analyze_repository (Job: {job_id}) ---")
    logger.info(f"Task analyze_repository received for job {job_id}")
    """
    Main analysis pipeline:
    1. Clone repo at commit
    2. Run all analyzers
    3. Get AI suggestions
    4. Save report
    5. Optionally post GitHub comment
    """
    db = SessionLocal()
    try:
        _update_job(db, job_id, status="processing", celery_task_id=self.request.id)

        # ── Imports here to avoid circular imports ──
        from backend.utils.repo_processor import clone_and_checkout, cleanup_repo, get_changed_files_from_pr
        from backend.services.analyzers.runner import analyze_files
        from backend.services.suggestion_engine import get_ai_suggestion
        from backend.services.report_service import create_report_db
        from backend.services.github_service import comment_on_commit
        from backend.models.schemas import IssueWithSuggestion

        repo_url = payload["repo_url"]
        commit_sha = payload["commit_sha"]
        branch = payload["branch"]
        repo_full_name = payload["repo_full_name"]
        changed_files = payload.get("changed_files", [])
        pr_number = payload.get("pr_number")
        user_id = payload.get("user_id")
        github_token = payload.get("github_token") or os.getenv("GITHUB_TOKEN", "")
        enable_comments = os.getenv("ENABLE_GH_COMMENTS", "false").lower() == "true"

        # Clone repo
        local_path = clone_and_checkout(repo_url, commit_sha, github_token)

        try:
            # Get changed files for PRs
            if pr_number and not changed_files:
                changed_files = get_changed_files_from_pr(repo_full_name, pr_number, github_token)

            # Run analysis
            raw_issues = analyze_files(changed_files, local_path)

            # Get AI suggestions
            issues_with_suggestions = []
            for issue in raw_issues[:30]:  # cap at 30 to avoid timeout
                suggestion = get_ai_suggestion(issue, local_path)
                issues_with_suggestions.append(
                    IssueWithSuggestion(issue=issue, suggestion=suggestion)
                )

            # Save report to DB
            report = create_report_db(
                db=db,
                user_id=user_id,
                repository=repo_full_name,
                commit_id=commit_sha,
                branch=branch,
                analyzed_files=changed_files,
                issues_with_suggestions=issues_with_suggestions,
            )

            # Post GitHub comment if enabled
            if enable_comments and github_token:
                comment_url = comment_on_commit(report)
                if comment_url:
                    report_orm = db.query(orm.Report).filter(orm.Report.id == report.id).first()
                    if report_orm:
                        report_orm.github_comment_url = comment_url
                        db.commit()

            _update_job(db, job_id, status="done", report_id=report.id)
            return {"status": "done", "report_id": report.id}

        finally:
            cleanup_repo(local_path)

    except Exception as e:
        logger.exception(f"[analyze_repository] Job {job_id} failed: {e}")
        _update_job(db, job_id, status="failed", error_message=str(e)[:500])
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="backend.workers.tasks.apply_autofix")
def apply_autofix(self, job_id: str, report_id: str, github_token: str, repo_full_name: str):
    print(f"--- [CELERY] Task Received: apply_autofix (Job: {job_id}) ---")
    logger.info(f"Task apply_autofix received for job {job_id}")
    """
    Auto-fix pipeline:
    1. Clone repo
    2. Apply AI-suggested fixes to files
    3. Create branch + commit
    4. Open PR
    """
    db = SessionLocal()
    try:
        _update_job(db, job_id, status="processing", celery_task_id=self.request.id)

        from backend.services.autofix_service import AutoFixService

        svc = AutoFixService(github_token)
        pr_url = svc.run(db, report_id)

        report_orm = db.query(orm.Report).filter(orm.Report.id == report_id).first()
        if report_orm and pr_url:
            report_orm.autofix_pr_url = pr_url
            db.commit()

        _update_job(db, job_id, status="done", report_id=report_id)
        return {"status": "done", "pr_url": pr_url}

    except Exception as e:
        logger.exception(f"[apply_autofix] Job {job_id} failed: {e}")
        _update_job(db, job_id, status="failed", error_message=str(e)[:500])
        raise
    finally:
        db.close()
