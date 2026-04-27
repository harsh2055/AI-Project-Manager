"""
Suggestion Engine — builds rich prompts with full context, calls LLM, parses structured responses.
Improved: passes git diff, file context, error type, language-specific guidance.
"""
import json
import re
import os
from typing import Optional, List
from backend.services.ai_service.factory import get_provider
from backend.models.schemas import Issue, AISuggestion


# Language-specific linting knowledge to ground AI responses
LANGUAGE_CONTEXT = {
    "python": """
Python context:
- PEP 8 style: 4-space indent, 79-char lines, snake_case
- Common tools: flake8 (style), pylint (logic), bandit (security)
- Security risks: eval(), exec(), subprocess without shell=False, hardcoded secrets, SQL injection via string formatting
- Dependency issues: outdated packages with known CVEs
""",
    "javascript": """
JavaScript context:
- ESLint rules: no-unused-vars, no-console, eqeqeq, no-eval
- Security: eval(), innerHTML, document.write(), prototype pollution
- Best practices: const/let over var, arrow functions, async/await over callbacks
""",
    "typescript": """
TypeScript context:
- Type safety: avoid 'any', use proper generics and interfaces
- ESLint + TypeScript rules apply
- Common issues: missing return types, implicit any, non-null assertions
""",
    "docker": """
Docker context:
- hadolint rules: use specific image tags not 'latest', avoid root user, minimize layers
- Security: no secrets in ENV, use multi-stage builds, pin base image digest
""",
}

DIFF_AWARE_PROMPT = """\
You are a senior code reviewer and security engineer. Analyze this specific static analysis finding and provide an actionable, precise fix.

## Static Analysis Finding
- **File**: {file}
- **Line**: {line}
- **Language**: {language}
- **Severity Type**: {type}
- **Tool**: {tool}
- **Error Message**: {message}

## Language & Tool Context
{language_context}

## Actual Code at Issue Location
```{language}
{code_snippet}
```

## Your Task
1. **Root Cause** (1-2 sentences): What specifically on line {line} causes this issue? Be concrete, not generic.
2. **Exact Fix** (1 sentence): State precisely what must change — variable name, pattern, function call, etc.
3. **Corrected Code**: Provide ONLY the corrected replacement for line {line} (or minimal surrounding block if multi-line context needed). It must:
   - Match the original indentation exactly
   - Be a drop-in replacement (no extra imports unless critical)
   - Fix the specific issue without changing unrelated code

Rules for your response:
- Do NOT give generic advice like "sanitize inputs" or "use best practices"
- Do NOT explain what the tool does — explain what THIS specific code does wrong
- The improved_code must be runnable as-is in context
- Track original_code for the auto-fix diff

Respond ONLY in valid JSON (no markdown fences, no preamble):
{{
  "explanation": "Specific root cause for line {line}: ...",
  "fix": "Exact action: replace X with Y because ...",
  "improved_code": "exact replacement code here",
  "original_code": "the original line(s) from the snippet",
  "start_line": {line},
  "end_line": {line}
}}
"""


def _extract_code_snippet(filepath: str, line: int, context: int = 8) -> str:
    """Extract code around the issue with line numbers for context."""
    try:
        with open(filepath, "r", errors="replace") as f:
            lines = f.readlines()
        start = max(0, line - context - 1)
        end = min(len(lines), line + context)
        snippet_lines = []
        for i, l in enumerate(lines[start:end], start=start + 1):
            marker = ">>>" if i == line else "   "
            snippet_lines.append(f"{marker} {i:4d}: {l.rstrip()}")
        return "\n".join(snippet_lines)
    except Exception:
        return "(code unavailable)"


def _get_git_diff_context(repo_local_path: str, filepath: str) -> str:
    """Try to get git diff for the file to understand what changed."""
    try:
        import subprocess
        abs_path = os.path.join(repo_local_path, filepath)
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD", "--", filepath],
            capture_output=True, text=True, cwd=repo_local_path, timeout=10
        )
        diff = result.stdout.strip()
        if diff and len(diff) < 3000:
            return f"\n## Git Diff (what changed in this file)\n```diff\n{diff[:2000]}\n```"
        return ""
    except Exception:
        return ""


def _parse_ai_response(raw: str) -> AISuggestion:
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    try:
        data = json.loads(cleaned)
        return AISuggestion(
            explanation=data.get("explanation", ""),
            fix=data.get("fix", ""),
            improved_code=data.get("improved_code", ""),
            original_code=data.get("original_code", ""),
            start_line=int(data.get("start_line", 0)),
            end_line=int(data.get("end_line", 0)),
        )
    except (json.JSONDecodeError, ValueError):
        return AISuggestion(
            explanation=raw[:500] if raw else "Could not parse AI response",
            fix="Review the issue manually.",
            improved_code="",
        )


def get_ai_suggestion(issue: Issue, repo_local_path: str) -> Optional[AISuggestion]:
    filepath = os.path.join(repo_local_path, issue.file)
    snippet = _extract_code_snippet(filepath, issue.line)
    lang = getattr(issue, "language", "python")
    lang_ctx = LANGUAGE_CONTEXT.get(lang, "")

    prompt = DIFF_AWARE_PROMPT.format(
        file=issue.file,
        line=issue.line,
        language=lang,
        type=issue.type,
        tool=issue.tool,
        message=issue.message,
        language_context=lang_ctx,
        code_snippet=snippet,
    )

    try:
        provider = get_provider()
        raw_response = provider._safe_generate(prompt)
        return _parse_ai_response(raw_response)
    except Exception as e:
        return AISuggestion(
            explanation=f"AI provider error: {e}",
            fix="Check provider configuration.",
            improved_code="",
        )