"""Aggregate all fixers' detect() into a single issue list for the agent.

This is the interface between deterministic fixes and agent-driven semantic
fixes: each fixer reports what remains after its mechanical pass, with line
numbers, so the agent can repair semantics (superscripts, broken sentences).
Also retains checks no single fixer owns (e.g. $ delimiter balance).
"""

import re
from pathlib import Path

from scripts.fixers import all_fixers, select

_CODE_RE = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)
_DISPLAY_MATH_MARKER_RE = re.compile(r"\$\$")


def _check_dollar_balance(text: str) -> list[str]:
    """Report unpaired $ / $$ math delimiters, ignoring code where $ is literal."""
    problems: list[str] = []
    body = _CODE_RE.sub("", text)
    display_markers = len(_DISPLAY_MATH_MARKER_RE.findall(body))
    if display_markers % 2 != 0:
        problems.append("Unpaired $$ delimiters")
    if _DISPLAY_MATH_MARKER_RE.sub("", body).count("$") % 2 != 0:
        problems.append("Unpaired $ delimiters")
    return problems


def verify_issues(md_path: Path, fixer_ids: list | None = None) -> list:
    """Aggregate selected fixers' detect() into structured Issue objects."""
    from scripts.fixers.base import Issue

    md_path = Path(md_path)
    text = md_path.read_text(encoding="utf-8")
    chosen = select(fixer_ids) if fixer_ids else all_fixers()

    issues: list = []
    for fixer in chosen:
        target = md_path if fixer.file_based else text
        issues += fixer.detect(target)
    for msg in _check_dollar_balance(text):
        issues.append(Issue("verifier", 0, msg))
    return issues


def verify(md_path: Path, fixer_ids: list | None = None) -> list[str]:
    """Aggregate selected fixers' detect() into string issues (empty = pass)."""
    return [str(issue) for issue in verify_issues(md_path, fixer_ids)]
