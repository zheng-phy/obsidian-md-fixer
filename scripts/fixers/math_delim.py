"""Math delimiter fixer.

Unifies the various delimiter systems MinerU emits into Obsidian-compatible
$...$:  <eq>...</eq> tags, paired \\(...\\) delimiters, and broken \\(... OMML
fragments (degraded to plain text to stop ParseError). Only touches 'text'
and 'eq' segments; existing $...$ math is left intact.
"""

import re

from scripts.fixers.base import split_zones

_EQ_RE = re.compile(r"<eq>(.*?)</eq>", re.DOTALL)
_LPAREN_PAIR_RE = re.compile(r"\\\((.+?)\\\)")
_BROKEN_LPAREN_RE = re.compile(r"\\\(([^)]*?)\)")


def _fix_segment(seg: str) -> str:
    seg = _EQ_RE.sub(lambda m: "$" + m.group(1) + "$", seg)
    seg = _LPAREN_PAIR_RE.sub(lambda m: "$" + m.group(1) + "$", seg)
    seg = _BROKEN_LPAREN_RE.sub(lambda m: "(" + m.group(1) + ")", seg)
    return seg


def fix(text: str) -> str:
    """Return text with delimiter issues repaired; eq tags and text segments fixed."""
    out: list[str] = []
    for k, s in split_zones(text):
        if k == "eq":
            out.append("$" + s[len("<eq>") : -len("</eq>")] + "$")
        elif k == "text":
            out.append(_fix_segment(s))
        else:
            out.append(s)
    return "".join(out)


_TAG_RE = re.compile(r"\\tag\{")


def _detect_tag(ln: str, lineno: int) -> list:
    """Detect malformed \\tag{...} blocks (MinerU equation-number-range misassembly).

    Flags: unbalanced braces inside the tag, stray ( ) mixed into the tag body,
    and a bare ~ (renders as a space in math mode, breaking a number range).
    """
    from scripts.fixers.base import Issue

    problems: list = []
    for m in _TAG_RE.finditer(ln):
        # take from \tag{ to end-of-line as the candidate body (tags close at line end)
        body = ln[m.start():]
        if body.count("{") != body.count("}"):
            problems.append(Issue("math_delim", lineno, f"unbalanced braces in \\tag: {body[:40]}"))
        inner = body[len("\\tag{"):]
        if "(" in inner or ")" in inner:
            problems.append(Issue("math_delim", lineno, f"stray parenthesis in \\tag: {body[:40]}"))
        if "~" in inner:
            problems.append(Issue("math_delim", lineno, f"bare ~ in \\tag (renders as space): {body[:40]}"))
    return problems


def detect(text: str) -> list:
    """Report lines with broken \\(... delimiters, leftover <eq> tags, or malformed \\tag."""
    from scripts.fixers.base import Issue

    problems: list = []
    for i, ln in enumerate(text.splitlines(), 1):
        for m in _BROKEN_LPAREN_RE.finditer(ln):
            problems.append(Issue("math_delim", i, f"broken \\(... delimiter: {m.group(0)[:30]}"))
        for _ in _EQ_RE.finditer(ln):
            problems.append(Issue("math_delim", i, "unconverted <eq> tag"))
        problems += _detect_tag(ln, i)
    return problems


def _cli(argv=None) -> int:
    import sys
    from pathlib import Path

    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print("usage: python -m scripts.fixers.math_delim <file.md>", file=sys.stderr)
        return 1
    p = Path(argv[0])
    p.write_text(fix(p.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"Done: {p}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_cli())
