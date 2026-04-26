"""
Pydantic schemas — request/response models
"""
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal, Any
from datetime import datetime


# ── Issue & Analysis ──────────────────────────────────────────────────────────

class Issue(BaseModel):
    file: str
    line: int
    type: Literal["error", "warning", "security", "dependency"]
    message: str
    tool: str
    language: str = "python"


class AISuggestion(BaseModel):
    explanation: str
    fix: str
    improved_code: str
    original_code: str = ""
    start_line: int = 0
    end_line: int = 0


class IssueWithSuggestion(BaseModel):
    issue: Issue
    suggestion: Optional[AISuggestion] = None


class AnalysisReport(BaseModel):
    id: str
    user_id: Optional[str] = None
    repository: str
    commit_id: str
    branch: str
    analyzed_files: List[str]
    issues: List[IssueWithSuggestion]
    severity_score: float
    github_comment_url: Optional[str] = None
    github_pr_url: Optional[str] = None
    autofix_pr_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReportSummary(BaseModel):
    id: str
    repository: str
    commit_id: str
    branch: str
    severity_score: float
    issue_count: int
    created_at: datetime
    autofix_pr_url: Optional[str] = None


# ── Webhook ───────────────────────────────────────────────────────────────────

class WebhookPayload(BaseModel):
    event_type: str
    repo_url: str
    repo_full_name: str
    branch: str
    commit_sha: str
    commit_message: str
    changed_files: List[str]
    pr_number: Optional[int] = None


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    github_username: Optional[str] = None
    webhook_secret: str
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class GitHubConnectRequest(BaseModel):
    github_token: str


# ── Jobs ──────────────────────────────────────────────────────────────────────

class JobStatus(BaseModel):
    id: str
    celery_task_id: Optional[str] = None
    status: str
    repository: str
    commit_sha: str
    branch: str
    report_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
