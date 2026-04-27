"""
Analyzer Runner — plugin-based multi-language analysis system
"""
import os
import subprocess
import json
import re
from typing import List, Protocol, runtime_checkable
from backend.models.schemas import Issue


@runtime_checkable
class Analyzer(Protocol):
    """Plugin interface — every analyzer implements this."""
    name: str
    supported_extensions: List[str]

    def analyze(self, filepath: str, repo_root: str) -> List[Issue]:
        ...


# ── Python analyzers ──────────────────────────────────────────────────────────

class Flake8Analyzer:
    name = "flake8"
    supported_extensions = [".py"]

    def analyze(self, filepath: str, repo_root: str) -> List[Issue]:
        result = subprocess.run(
            ["flake8", "--format=%(path)s:%(row)d:%(col)d: %(code)s %(text)s", filepath],
            capture_output=True, text=True, cwd=repo_root
        )
        issues = []
        for line in result.stdout.splitlines():
            m = re.match(r"(.+?):(\d+):\d+: ([EWF]\d+) (.+)", line)
            if m:
                rel = os.path.relpath(m.group(1), repo_root)
                code = m.group(3)
                issues.append(Issue(
                    file=rel, line=int(m.group(2)),
                    type="error" if code.startswith("E") else "warning",
                    message=f"[flake8 {code}] {m.group(4)}",
                    tool="flake8", language="python",
                ))
        return issues


class PylintAnalyzer:
    name = "pylint"
    supported_extensions = [".py"]

    def analyze(self, filepath: str, repo_root: str) -> List[Issue]:
        result = subprocess.run(
            ["pylint", "--output-format=json", "--disable=C", filepath],
            capture_output=True, text=True, cwd=repo_root
        )
        issues = []
        try:
            data = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            return issues
        for item in data:
            msg_type = item.get("type", "")
            if msg_type == "error":
                issue_type = "error"
            elif msg_type in ("warning", "refactor"):
                issue_type = "warning"
            else:
                continue
            rel = os.path.relpath(item.get("path", filepath), repo_root)
            issues.append(Issue(
                file=rel, line=item.get("line", 0),
                type=issue_type,
                message=f"[pylint {item.get('message-id', '')}] {item.get('message', '')}",
                tool="pylint", language="python",
            ))
        return issues


class BanditAnalyzer:
    name = "bandit"
    supported_extensions = [".py"]

    def analyze(self, filepath: str, repo_root: str) -> List[Issue]:
        result = subprocess.run(
            ["bandit", "-f", "json", "-q", filepath],
            capture_output=True, text=True, cwd=repo_root
        )
        issues = []
        try:
            data = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            return issues
        for item in data.get("results", []):
            rel = os.path.relpath(item.get("filename", filepath), repo_root)
            issues.append(Issue(
                file=rel, line=item.get("line_number", 0),
                type="security",
                message=f"[bandit {item.get('test_id', '')}] {item.get('issue_text', '')} (severity: {item.get('issue_severity', 'UNKNOWN')})",
                tool="bandit", language="python",
            ))
        return issues


class PipAuditAnalyzer:
    """Repo-level dependency audit — runs once, not per-file."""
    name = "pip-audit"
    supported_extensions = [".txt"]  # requirements.txt

    def analyze(self, filepath: str, repo_root: str) -> List[Issue]:
        req_file = os.path.join(repo_root, "requirements.txt")
        if not os.path.exists(req_file):
            return []
        result = subprocess.run(
            ["pip-audit", "-r", req_file, "--format=json"],
            capture_output=True, text=True, cwd=repo_root
        )
        issues = []
        try:
            data = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            return issues
        for item in data:
            pkg = item.get("name", "unknown")
            for vuln in item.get("vulns", []):
                issues.append(Issue(
                    file="requirements.txt", line=0,
                    type="dependency",
                    message=f"[pip-audit] {pkg}: {vuln.get('id', '')} — {vuln.get('description', '')[:120]}",
                    tool="pip-audit", language="python",
                ))
        return issues


# ── JavaScript / TypeScript analyzers ────────────────────────────────────────

class ESLintAnalyzer:
    name = "eslint"
    supported_extensions = [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]

    def analyze(self, filepath: str, repo_root: str) -> List[Issue]:
        result = subprocess.run(
            ["npx", "--yes", "eslint", "--format=json", filepath],
            capture_output=True, text=True, cwd=repo_root, timeout=60,
        )
        issues = []
        try:
            data = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            return issues
        for file_result in data:
            rel = os.path.relpath(file_result.get("filePath", filepath), repo_root)
            for msg in file_result.get("messages", []):
                severity = msg.get("severity", 1)
                issues.append(Issue(
                    file=rel,
                    line=msg.get("line", 0),
                    type="error" if severity == 2 else "warning",
                    message=f"[eslint {msg.get('ruleId', '')}] {msg.get('message', '')}",
                    tool="eslint",
                    language="javascript" if filepath.endswith((".js", ".jsx", ".mjs")) else "typescript",
                ))
        return issues


# ── Docker analyzer ────────────────────────────────────────────────────────────

class HadolintAnalyzer:
    name = "hadolint"
    supported_extensions = ["Dockerfile", ".dockerfile"]

    def analyze(self, filepath: str, repo_root: str) -> List[Issue]:
        result = subprocess.run(
            ["hadolint", "--format", "json", filepath],
            capture_output=True, text=True, cwd=repo_root, timeout=30,
        )
        issues = []
        try:
            data = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            return issues
        for item in data:
            rel = os.path.relpath(item.get("file", filepath), repo_root)
            level = item.get("level", "warning")
            issues.append(Issue(
                file=rel,
                line=item.get("line", 0),
                type="error" if level == "error" else "warning",
                message=f"[hadolint {item.get('code', '')}] {item.get('message', '')}",
                tool="hadolint",
                language="docker",
            ))
        return issues


# ── Registry & Runner ──────────────────────────────────────────────────────────

ANALYZER_REGISTRY: List[Analyzer] = [
    Flake8Analyzer(),
    PylintAnalyzer(),
    BanditAnalyzer(),
    PipAuditAnalyzer(),
    ESLintAnalyzer(),
    HadolintAnalyzer(),
]


def _get_analyzers_for_file(filepath: str) -> List[Analyzer]:
    """Select analyzers based on file extension or name."""
    filename = os.path.basename(filepath)
    ext = os.path.splitext(filepath)[1].lower()

    matches = []
    for analyzer in ANALYZER_REGISTRY:
        for supported in analyzer.supported_extensions:
            if supported.startswith(".") and ext == supported:
                matches.append(analyzer)
                break
            elif not supported.startswith(".") and filename == supported:
                matches.append(analyzer)
                break
    return matches


from pathlib import Path

def analyze_files(changed_files: List[str], repo_root: str) -> List[Issue]:
    """
    Run all applicable analyzers on changed files.
    Returns deduplicated list of issues.
    """
    # Use absolute path for repo_root to avoid confusion with relative paths in subprocess.run
    root_path = Path(repo_root).resolve()
    all_issues: List[Issue] = []
    ran_dep_audit = False

    for rel_path_str in changed_files:
        # rel_path_str might be something like "backend/main.py"
        rel_path = Path(rel_path_str)
        abs_path = root_path / rel_path

        if not abs_path.is_file():
            # If file doesn't exist in the clone (e.g. deleted in this commit), skip it
            continue

        analyzers = _get_analyzers_for_file(rel_path_str)
        for analyzer in analyzers:
            if analyzer.name == "pip-audit":
                if ran_dep_audit:
                    continue
                ran_dep_audit = True
            try:
                # Pass absolute path as string to analyzer.
                # Tools like flake8/pylint will run in root_path (via cwd) 
                # and handle the absolute path correctly.
                issues = analyzer.analyze(str(abs_path), str(root_path))
                all_issues.extend(issues)
            except Exception as e:
                # Don't let one analyzer crash the whole pipeline
                print(f"[runner] {analyzer.name} failed on {rel_path_str}: {e}")

    # Dedup by (file, line, message)
    seen = set()
    deduped = []
    for issue in all_issues:
        key = (issue.file, issue.line, issue.message)
        if key not in seen:
            seen.add(key)
            deduped.append(issue)

    return deduped
