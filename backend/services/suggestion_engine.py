"""
Suggestion Engine — builds prompts, calls LLM, parses structured responses
"""
import json
import re
from typing import Optional
from backend.services.ai_service.factory import get_provider
from backend.models.schemas import Issue, AISuggestion


PROMPT_TEMPLATE = """\
You are a senior software engineer reviewing a code issue found by static analysis.

Issue Details:
- File: {file}
- Line: {line}
- Language: {language}
- Type: {type}
- Tool: {tool}
- Message: {message}

Relevant code snippet (line numbers shown):
```
{code_snippet}
```

Your tasks:
1. Explain WHY this is an issue clearly and concisely (1-2 sentences)
2. Describe the exact fix needed (1 sentence)
3. Provide ONLY the corrected version of line {line} (or the minimal surrounding block if context is needed)

The improved_code must be a drop-in replacement — same indentation, no extra imports, minimal diff.
Track what the original line(s) looked like in original_code.

Respond ONLY in valid JSON with this exact structure (no markdown, no extra text):
{{
  "explanation": "...",
  "fix": "...",
  "improved_code": "...",
  "original_code": "...",
  "start_line": {line},
  "end_line": {line}
}}
"""


def _extract_code_snippet(filepath: str, line: int, context: int = 6) -> str:
    try:
        with open(filepath, "r", errors="replace") as f:
            lines = f.readlines()
        start = max(0, line - context - 1)
        end = min(len(lines), line + context)
        return "".join(f"{i+1}: {l}" for i, l in enumerate(lines[start:end]))
    except Exception:
        return "(code unavailable)"


def _parse_ai_response(raw: str) -> AISuggestion:
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    # Find first JSON object
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
            explanation=raw[:500],
            fix="Could not parse structured response.",
            improved_code="",
        )


def get_ai_suggestion(issue: Issue, repo_local_path: str) -> Optional[AISuggestion]:
    filepath = f"{repo_local_path}/{issue.file}"
    snippet = _extract_code_snippet(filepath, issue.line)

    prompt = PROMPT_TEMPLATE.format(
        file=issue.file,
        line=issue.line,
        language=getattr(issue, "language", "python"),
        type=issue.type,
        tool=issue.tool,
        message=issue.message,
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
