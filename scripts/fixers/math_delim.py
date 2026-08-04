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
# Obsidian strips the backslash from \[..\] (CommonMark), so MathJax never
# sees the formula; convert to $$..$$ (T1 24 处实证). Runs before <eq>/\\(..
# so its body is converted as-is.
_DBRACKET_RE = re.compile(r"\\\[(.*?)\\\]", re.DOTALL)
_RESIDUAL_DBRACKET_RE = re.compile(r"\\\[|\\\]")


# Numeric-range tilde: 36%\~41% -> 36%~41% (2021B 实样:percent-or-digit on
# both sides). Letter contexts (X\~B) are downgraded math and stay untouched.
_TILDE_RANGE_RE = re.compile(r"(?<=[\d%])\\~(?=[\d%])")


def _fix_segment(seg: str) -> str:
    seg = _DBRACKET_RE.sub(lambda m: "$$" + m.group(1).strip() + "$$", seg)
    seg = _TILDE_RANGE_RE.sub("~", seg)
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
# Inline math downgraded to text: X\~B(n,p) (literal backslash-tilde outside
# math) and 0<p<1 (bare inequality). A \~ between digits (1\~8, Chinese
# range) is NOT math.
_DOWNGRADED_TILDE_RE = re.compile(r"[A-Za-z]\\~[A-Za-z(]")
_DOWNGRADED_LT_RE = re.compile(r"\d<[A-Za-z](?:<[0-9])?")


# Sub/superscript braces (_{i = 1}) legitimately contain "="; strip them
# before counting so only body-level equals count (MoE稀疏门控 6 条误报).
# Allow spaces around the brace (_ { i = 1 }) — MinerU's raw output is not
# normalized, so the detect must not depend on ocr_cleanup running first.
_SUBSUP_BRACED_RE = re.compile(r"[\^_]\s*\{[^{}]*\}")


def _bare_eq_count(seg: str) -> int:
    """Count bare = with whitespace on at least one side, deduplicated.

    Garbled math bodies (K3 AttnRes "= 1 = 1 1") have several; a normal
    equation ($x = y + 1$) has exactly one. Braced sub/superscript content
    is excluded (sum indices like i = 1 are not garbled).
    """
    seg = _SUBSUP_BRACED_RE.sub("", seg)
    eqs: set = set()
    for m in re.finditer(r"= ", seg):
        eqs.add(m.start())
    for m in re.finditer(r" =", seg):
        eqs.add(m.start() + 1)
    return len(eqs)


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
    """Report broken delimiters, downgraded inline math, and garbled math.

    Broken \\(..., leftover <eq>, and malformed \\tag are line-based; the
    downgrade and garbled checks are zone-based (text vs math).
    """
    from scripts.fixers.base import Issue

    problems: list = []
    pos = 0
    for kind, seg in split_zones(text):
        base_line = text[:pos].count("\n") + 1
        if kind == "text":
            # Complete \[...\] pairs are auto-fixed; only the leftovers
            # (unpaired \[/\]) are residuals for agent review.
            residual = _DBRACKET_RE.sub(lambda m: "  ", seg)
            for m in _RESIDUAL_DBRACKET_RE.finditer(residual):
                problems.append(Issue(
                    "math_delim",
                    base_line + seg[: m.start()].count("\n"),
                    "leftover \\[...\\] display-math delimiter — review",
                ))
            for m in _DOWNGRADED_TILDE_RE.finditer(seg):
                problems.append(Issue(
                    "math_delim",
                    base_line + seg[: m.start()].count("\n"),
                    "inline math downgraded to text (\\~ outside math) — wrap with $...$",
                ))
            for m in _DOWNGRADED_LT_RE.finditer(seg):
                problems.append(Issue(
                    "math_delim",
                    base_line + seg[: m.start()].count("\n"),
                    "inline math downgraded to text (bare inequality) — wrap with $...$",
                ))
        elif kind == "math" and _bare_eq_count(seg) >= 2:
            problems.append(Issue(
                "math_delim",
                base_line,
                "math content looks garbled (balanced delimiters but broken body) — compare with PDF",
            ))
        pos += len(seg)

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

    from scripts.textio import read_text_preserve, write_text_preserve

    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print("usage: python -m scripts.fixers.math_delim <file.md>", file=sys.stderr)
        return 1
    p = Path(argv[0])
    text, newline = read_text_preserve(p)
    write_text_preserve(p, fix(text), newline)
    print(f"Done: {p}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_cli())
