"""Convert MinerU <div class="mineru-algorithm"> blocks to Markdown.

The div is an HTML block Obsidian won't render as Markdown, so any $...$ inside
is suppressed too. Unwrap it: anchor lines (Algorithm title, Input/Output,
numbered steps, control keywords) go into a code block; everything else returns
to prose so formulas render. Uncertain lines default to prose + a detect() note.
"""

import re

from scripts.fixers.base import Issue

_DIV_RE = re.compile(r'<div class="mineru-algorithm"[^>]*>(.*?)</div>', re.DOTALL)
_ANCHOR_RE = re.compile(
    r"^\s*(Algorithm\s+\d+|算法\s*\d+|Input:|Output:|输入:|输出:|\d+\.\s"
    r"|for\b|while\b|if\b|return\b|repeat\b|until\b)",
    re.IGNORECASE,
)


def _convert_div(match: re.Match) -> str:
    body = match.group(1).strip("\n")
    out: list = []
    code_buf: list = []

    def flush_code() -> None:
        if code_buf:
            out.append("```\n" + "\n".join(code_buf) + "\n```")
            code_buf.clear()

    for ln in body.splitlines():
        if _ANCHOR_RE.match(ln):
            code_buf.append(ln)
        else:
            flush_code()
            if ln.strip():
                out.append(ln)
    flush_code()
    return "\n".join(out)


def fix(text: str) -> str:
    """Unwrap mineru-algorithm divs; anchors to code block, rest to prose."""
    return _DIV_RE.sub(_convert_div, text)


def detect(text: str) -> list:
    """Report remaining mineru-algorithm divs (with line number)."""
    problems = []
    for i, ln in enumerate(text.splitlines(), 1):
        if "mineru-algorithm" in ln:
            problems.append(Issue("algorithm", i, "unconverted mineru-algorithm div"))
    return problems
