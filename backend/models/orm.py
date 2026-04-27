"""
ORM Models — Users, Reports, Jobs
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from backend.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    github_token = Column(String, nullable=True)
    github_username = Column(String, nullable=True)
    webhook_secret = Column(String, unique=True, nullable=False, default=gen_uuid)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    reports = relationship("Report", back_populates="owner", cascade="all, delete")
    jobs = relationship("Job", back_populates="owner", cascade="all, delete")


class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    repository = Column(String, nullable=False)
    commit_id = Column(String, nullable=False)
    branch = Column(String, nullable=False)
    analyzed_files = Column(JSON, default=list)
    issues = Column(JSON, default=list)       # serialized IssueWithSuggestion list
    severity_score = Column(Float, default=0.0)
    github_comment_url = Column(String, nullable=True)
    github_pr_url = Column(String, nullable=True)
    autofix_pr_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="reports")
    jobs = relationship("Job", back_populates="report", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    celery_task_id = Column(String, nullable=True, index=True)
    status = Column(String, default="pending")   # pending | processing | done | failed
    repository = Column(String, nullable=False)
    commit_sha = Column(String, nullable=False)
    branch = Column(String, nullable=False)
    report_id = Column(String, ForeignKey("reports.id"), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="jobs")
    report = relationship("Report", back_populates="jobs")
