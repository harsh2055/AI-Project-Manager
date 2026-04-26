"""
AutoFix Service — applies AI suggestions to files, creates branch, opens PR.
Uses precise line-level patching for safety.
"""
import os
import json
import logging
from typing import Optional, List
from github import Github, GithubException
from sqlalchemy.orm import Session
from backend.models import orm
from backend.models.schemas import IssueWithSuggestion, AISuggestion

logger = logging.getLogger(__name__)


class AutoFixService:
    def __init__(self, github_token: str):
        if not github_token:
            raise ValueError("GitHub token required for auto-fix")
        self.gh = Github(github_token)

    def run(self, db: Session, report_id: str) -> Optional[str]:
        """
        Full auto-fix flow:
        1. Load report
        2. Collect fixable issues (those with improved_code)
        3. Apply patches to repo via GitHub API
        4. Open PR
        Returns PR URL or None.
        """
        report_orm = db.query(orm.Report).filter(orm.Report.id == report_id).first()
        if not report_orm:
            raise ValueError(f"Report {report_id} not found")

        issues_data: List[dict] = report_orm.issues or []
        issues = [IssueWithSuggestion(**i) for i in issues_data]

        fixable = [
            iws for iws in issues
            if iws.suggestion and iws.suggestion.improved_code.strip()
        ]

        if not fixable:
            logger.info(f"[autofix] No fixable issues in report {report_id}")
            return None

        try:
            repo = self.gh.get_repo(report_orm.repository)
        except GithubException as e:
            raise RuntimeError(f"Cannot access repo: {e}")

        # Group fixes by file
        fixes_by_file: dict = {}
        for iws in fixable:
            fname = iws.issue.file
            if fname not in fixes_by_file:
                fixes_by_file[fname] = []
            fixes_by_file[fname].append(iws)

        # Create branch
        base_branch = report_orm.branch or "main"
        new_branch = f"ai-autofix/{report_orm.commit_id[:8]}"

        try:
            source = repo.get_branch(base_branch)
            repo.create_git_ref(ref=f"refs/heads/{new_branch}", sha=source.commit.sha)
        except GithubException as e:
            if "already exists" in str(e):
                pass  # Branch already exists, proceed
            else:
                raise RuntimeError(f"Could not create branch: {e}")

        # Apply file patches
        applied_files = []
        for filepath, iws_list in fixes_by_file.items():
            try:
                patched = self._patch_file(repo, filepath, new_branch, iws_list)
                if patched:
                    applied_files.append(filepath)
            except Exception as e:
                logger.warning(f"[autofix] Could not patch {filepath}: {e}")

        if not applied_files:
            return None

        # Open PR
        pr_title = f"[AI Autofix] Fixes for commit {report_orm.commit_id[:8]}"
        pr_body = self._build_pr_body(report_orm, fixable, applied_files)

        try:
            pr = repo.create_pull(
                title=pr_title,
                body=pr_body,
                head=new_branch,
                base=base_branch,
            )
            return pr.html_url
        except GithubException as e:
            raise RuntimeError(f"Could not open PR: {e}")

    def _patch_file(
        self,
        repo,
        filepath: str,
        branch: str,
        iws_list: List[IssueWithSuggestion],
    ) -> bool:
        """
        Apply line-level patches to a file via GitHub Contents API.
        Patches are applied from bottom to top to preserve line numbers.
        """
        try:
            file_content = repo.get_contents(filepath, ref=branch)
            original_lines = file_content.decoded_content.decode("utf-8").splitlines(keepends=True)
        except GithubException:
            return False

        # Sort fixes from last line to first (bottom-up) to keep line numbers stable
        sorted_fixes = sorted(iws_list, key=lambda x: x.issue.line, reverse=True)

        patched_lines = list(original_lines)
        for iws in sorted_fixes:
            line_no = iws.issue.line - 1  # 0-indexed
            improved = iws.suggestion.improved_code

            if 0 <= line_no < len(patched_lines):
                # Replace the problematic line(s) with improved code
                improved_lines = improved.splitlines(keepends=True)
                if not improved_lines[-1].endswith("\n"):
                    improved_lines[-1] += "\n"
                patched_lines[line_no:line_no + 1] = improved_lines

        new_content = "".join(patched_lines)
        if new_content == file_content.decoded_content.decode("utf-8"):
            return False  # No actual change

        repo.update_file(
            path=filepath,
            message=f"fix: AI autofix for issues in {filepath}",
            content=new_content,
            sha=file_content.sha,
            branch=branch,
        )
        return True

    def _build_pr_body(self, report_orm, fixable: List[IssueWithSuggestion], applied_files: List[str]) -> str:
        lines = [
            "## 🤖 AI Project Manager — Automated Fix PR",
            "",
            f"**Repository:** `{report_orm.repository}`",
            f"**Based on commit:** `{report_orm.commit_id[:8]}`",
            f"**Branch:** `{report_orm.branch}`",
            f"**Files patched:** {len(applied_files)}",
            "",
            "### Changes Applied",
            "",
        ]
        for iws in fixable:
            if iws.issue.file in applied_files:
                lines += [
                    f"#### `{iws.issue.file}` line {iws.issue.line} [{iws.issue.type.upper()}]",
                    f"**Issue:** {iws.issue.message}",
                    f"**Fix:** {iws.suggestion.fix}",
                    "",
                ]
        lines += [
            "---",
            "> ⚠️ **Review carefully before merging.** AI-generated fixes should be validated by a human.",
            "> Generated by [AI Project Manager](https://github.com)",
        ]
        return "\n".join(lines)
