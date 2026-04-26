"""
Repository processing — clone, checkout, cleanup
"""
import os
import shutil
import tempfile
from typing import List, Optional
from git import Repo, GitCommandError
from github import Github, GithubException

TEMP_BASE = os.getenv("TEMP_DIR", "/tmp/ai_pm_repos")


def clone_and_checkout(repo_url: str, commit_sha: str, github_token: Optional[str] = None) -> str:
    os.makedirs(TEMP_BASE, exist_ok=True)
    local_path = tempfile.mkdtemp(prefix=f"repo_{commit_sha[:8]}_", dir=TEMP_BASE)
    if github_token and repo_url.startswith("https://"):
        repo_url = repo_url.replace("https://", f"https://x-access-token:{github_token}@")
    try:
        repo = Repo.clone_from(repo_url, local_path, depth=10)
        repo.git.checkout(commit_sha)
        return local_path
    except GitCommandError as e:
        shutil.rmtree(local_path, ignore_errors=True)
        raise RuntimeError(f"Failed to clone/checkout repo: {e}")


def get_changed_files_from_pr(repo_full_name: str, pr_number: int, github_token: Optional[str] = None) -> List[str]:
    try:
        g = Github(github_token or os.getenv("GITHUB_TOKEN", ""))
        repo = g.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        return [f.filename for f in pr.get_files()]
    except GithubException as e:
        print(f"[repo_processor] Could not fetch PR files: {e}")
        return []


def cleanup_repo(local_path: str):
    shutil.rmtree(local_path, ignore_errors=True)
