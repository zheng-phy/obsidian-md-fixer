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
# Fence marker: opening (```lang) and closing (```) both match.
_FENCE_RE = re.compile(r"^```\s*\w*$")


def _is_anchor(line: str) -> bool:
    return bool(_ANCHOR_RE.match(line))


def _is_clean_code_line(line: str) -> bool:
    """A line confidently inside code: no CJK prose, no inline math."""
    return bool(line.strip()) and not _CJK_RE.search(line) and not _MATH_RE.search(line)


def _split_fence_runs(lines: list) -> list:
    """Split lines into (in_fence: bool, run: list[str]) runs.

    A fence marker line (^```lang$ or ^```$ — both matched by _FENCE_RE) toggles
    the fence state and belongs to the fence run. An unclosed fence keeps every
    line after it fenced (conservative: never auto-close, never re-open).
    """
    runs: list = []
    in_fence = False
    run: list = []
    for ln in lines:
        if _FENCE_RE.match(ln):
            if run:
                runs.append((in_fence, run))
                run = []
            in_fence = not in_fence
            run.append(ln)  # marker line itself belongs to the fence run
        else:
            run.append(ln)
    if run:
        runs.append((in_fence, run))
    return runs


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
    """Wrap high-confidence code blocks; ambiguous regions are left untouched.

    Existing fence blocks pass through verbatim — only unfenced runs are scanned.
    """
    out: list = []
    for in_fence, run in _split_fence_runs(text.split("\n")):
        if in_fence:
            out.extend(run)
            continue
        i = 0
        while i < len(run):
            end = _find_block(run, i)
            if end > i:
                out.append("```python")
                out.extend(run[i:end])
                out.append("```")
                i = end
            else:
                out.append(run[i])
                i += 1
    return "\n".join(out)


# Fence structural detects. Wrong labels MinerU sometimes emits for python
# content; the K3 tech report uses "prolog" for python blocks.
_WRONG_LANG = {"prolog", "txt", "makefile", "lua"}
_FENCE_OPEN_RE = re.compile(r"^```(\w*)$")
_FENCE_CLOSE_RE = re.compile(r"^```\s*$")
_KEYWORD_LINE_RE = re.compile(r"^\s*(def\s|for\s|if\s)")
_SHORT_GAP_LEN = 20  # lines between fragmented fences may be blank or short
_INDENT_LOSS_MIN_LINES = 8


def _fence_blocks(lines: list) -> list:
    """Yield (open_line_no, lang, content_lines) for each CLOSED fence block.

    An unclosed fence swallows the rest of the file (conservative, matching
    _split_fence_runs) and yields no block.
    """
    blocks: list = []
    i = 0
    n = len(lines)
    while i < n:
        m = _FENCE_OPEN_RE.match(lines[i])
        if not m:
            i += 1
            continue
        lang = m.group(1).lower()
        content: list = []
        j = i + 1
        while j < n and not _FENCE_CLOSE_RE.match(lines[j]):
            content.append(lines[j])
            j += 1
        if j < n:  # closed
            blocks.append((i + 1, lang, content))
            i = j + 1
        else:  # unclosed: rest is fenced
            i = n
    return blocks


def detect(text: str) -> list:
    """Report suspected code blocks needing agent review (with line number).

    Anchors inside an existing fence are never reported (fenced code is by
    definition already handled) — keeps fix/detect self-consistent.
    Also reports fence structure issues: wrong language label, adjacent
    fragmented fences, and possible indent loss.
    """
    problems = []
    lines = text.split("\n")
    lineno = 0
    for in_fence, run in _split_fence_runs(lines):
        if in_fence:
            lineno += len(run)
            continue
        for ln in run:
            lineno += 1
            if _is_anchor(ln):
                problems.append(Issue("code_fence", lineno, f"suspected code block (needs agent review): {ln.strip()[:40]}"))

    blocks = _fence_blocks(lines)
    for idx, (start, lang, content) in enumerate(blocks):
        if lang in _WRONG_LANG and sum(1 for ln in content if _is_anchor(ln)) >= 2:
            problems.append(Issue(
                "code_fence", start,
                f"fence labeled '{lang}' but content looks like python",
            ))
        if (
            len(content) >= _INDENT_LOSS_MIN_LINES
            and any(_KEYWORD_LINE_RE.match(ln) for ln in content)
            and all(not ln.startswith((" ", "\t")) for ln in content if ln.strip())
        ):
            problems.append(Issue(
                "code_fence", start,
                "code block has no indentation (possible indent loss)",
            ))
        if idx > 0:
            prev = blocks[idx - 1]
            close_line = prev[0] + 1 + len(prev[2])  # 1-based closing line
            gap = lines[close_line : start - 1]
            if len(gap) <= 3 and all(
                not ln.strip() or len(ln.strip()) <= _SHORT_GAP_LEN for ln in gap
            ):
                problems.append(Issue(
                    "code_fence", start,
                    "adjacent fragmented fences (possible pagination split) — consider merging",
                ))
    return problems
