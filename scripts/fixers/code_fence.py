"""Wrap un-fenced code blocks that MinerU downgraded to plain text lines.

Principle: do NOT try to catch everything. Only wrap a block when confidence is
high (2+ consecutive clean anchor lines, no math, no Chinese prose). Anything
ambiguous (math mixed in, Chinese mixed in, single anchor, unclear language) is
reported by detect() and left for the agent — never auto-wrapped.
"""

import re

from scripts.fixers.base import Issue

# High-confidence code anchors at line start.
_ANCHOR_RE = re.compile(
    r"^\s*(import\s+\w|from\s+\w+\s+import|def\s+\w+\s*\(|class\s+\w+|print\(|return\s+\S"
    r"|#include|plt\.|for\s+\w+\s+in\s+.+:)"
)
_CJK_RE = re.compile(r"[一-鿿]")
_MATH_RE = re.compile(r"\$")
_MIN_BLOCK = 2  # need at least this many consecutive anchor lines to wrap


def _is_anchor(line: str) -> bool:
    return bool(_ANCHOR_RE.match(line))


def _is_clean_code_line(line: str) -> bool:
    """A line confidently inside code: no CJK prose, no inline math."""
    return bool(line.strip()) and not _CJK_RE.search(line) and not _MATH_RE.search(line)


def _find_block(lines: list, start: int) -> int:
    """Return end index (exclusive) of a high-confidence block starting at `start`.

    Requires >= _MIN_BLOCK consecutive lines that are anchor-or-continuation and
    all clean (no math/CJK). Returns start if no confident block.
    """
    if not (_is_anchor(lines[start]) and _is_clean_code_line(lines[start])):
        return start
    j = start + 1
    while j < len(lines) and _is_clean_code_line(lines[j]) and (
        _is_anchor(lines[j]) or lines[j].startswith((" ", "\t")) or not _CJK_RE.search(lines[j])
    ):
        j += 1
    return j if (j - start) >= _MIN_BLOCK else start


def fix(text: str) -> str:
    """Wrap high-confidence code blocks; ambiguous regions are left untouched."""
    lines = text.splitlines()
    out: list = []
    i = 0
    while i < len(lines):
        end = _find_block(lines, i)
        if end > i:
            out.append("```python")
            out.extend(lines[i:end])
            out.append("```")
            i = end
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


def detect(text: str) -> list:
    """Report suspected code blocks needing agent review (with line number)."""
    problems = []
    lines = text.splitlines()
    for i, ln in enumerate(lines, 1):
        if _is_anchor(ln):
            problems.append(Issue("code_fence", i, f"suspected code block (needs agent review): {ln.strip()[:40]}"))
    return problems
