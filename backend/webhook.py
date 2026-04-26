"""
Webhook layer — validates and parses GitHub webhook payloads
"""
import hashlib
import hmac
import os
from typing import Optional, Dict, Any, List
from fastapi import Request, HTTPException
from backend.models.schemas import WebhookPayload

GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")


def _verify_signature(body: bytes, signature_header: Optional[str]) -> bool:
    if not GITHUB_WEBHOOK_SECRET:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature_header)


def _extract_changed_files(commits: List[Dict]) -> List[str]:
    files = set()
    for commit in commits:
        for key in ("added", "modified", "removed"):
            files.update(commit.get(key, []))
    return list(files)


async def parse_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    event_type = request.headers.get("X-GitHub-Event", "")

    if not _verify_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if event_type == "ping":
        return {"status": "ok", "message": "pong"}

    if event_type not in ("push", "pull_request"):
        raise HTTPException(status_code=422, detail=f"Event '{event_type}' not supported")

    payload: Dict[str, Any] = await request.json()
    repo = payload.get("repository", {})

    if event_type == "push":
        return WebhookPayload(
            event_type="push",
            repo_url=repo.get("clone_url", ""),
            repo_full_name=repo.get("full_name", ""),
            branch=payload.get("ref", "").replace("refs/heads/", ""),
            commit_sha=payload.get("after", ""),
            commit_message=payload.get("head_commit", {}).get("message", ""),
            changed_files=_extract_changed_files(payload.get("commits", [])),
        )

    pr = payload.get("pull_request", {})
    return WebhookPayload(
        event_type="pull_request",
        repo_url=repo.get("clone_url", ""),
        repo_full_name=repo.get("full_name", ""),
        branch=pr.get("head", {}).get("ref", ""),
        commit_sha=pr.get("head", {}).get("sha", ""),
        commit_message=pr.get("title", ""),
        changed_files=[],
        pr_number=pr.get("number"),
    )
