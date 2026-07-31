"""Join URLs split by a stray space (Agent World: "arxiv.org/abs/ 2601.05808").

A URL segment ending in / . - followed on the SAME line by a space and a
token made entirely of URL characters (with at least one digit/dot/slash/
dash, no CJK) is joined back into one URL. The same shape split ACROSS a
line break is only reported (the agent must decide whether the continuation
belongs to the URL). Everything else is left untouched.
"""

import re

from scripts.fixers.base import Issue, split_zones

_URL_CHARSET = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._~:/?#@!$&'()*+,;=-"
)
_CJK_RE = re.compile(r"[一-鿿]")
_URL_TAIL_RE = re.compile(r"^ +([^\s]+)")
_CROSS_LINE_TAIL_RE = re.compile(r"\n +([^\s]+)")


def _is_url_fragment(tok: str) -> bool:
    """Return whether tok could be the continuation of a URL."""
    if _CJK_RE.search(tok):
        return False
    if not all(ch in _URL_CHARSET for ch in tok):
        return False
    return bool(re.search(r"[0-9./-]", tok))


def fix(text: str) -> str:
    """Join same-line split URLs; cross-line splits are left for detect()."""
    segs = split_zones(text)
    out: list = []
    i = 0
    n = len(segs)
    while i < n:
        kind, seg = segs[i]
        if kind == "url" and seg.endswith(("/", ".", "-")) and i + 1 < n and segs[i + 1][0] == "text":
            nxt = segs[i + 1][1]
            m = _URL_TAIL_RE.match(nxt)
            if m and _is_url_fragment(m.group(1)):
                out.append(seg + m.group(1))
                out.append(nxt[m.end():])
                i += 2
                continue
        out.append(seg)
        i += 1
    return "".join(out)


def detect(text: str) -> list:
    """Report URLs split across lines (never auto-joined)."""
    problems: list = []
    segs = split_zones(text)
    pos = 0
    for i, (kind, seg) in enumerate(segs):
        if kind == "url" and i + 1 < len(segs) and segs[i + 1][0] == "text":
            nxt = segs[i + 1][1]
            m = _CROSS_LINE_TAIL_RE.match(nxt)
            if m and _is_url_fragment(m.group(1)):
                line = text[: pos + len(seg) + m.end()].count("\n") + 1
                problems.append(Issue(
                    "url_join", line,
                    f"possible URL split across lines — review: {seg} {m.group(1)[:30]}",
                ))
        pos += len(seg)
    return problems


def _cli(argv=None) -> int:
    import sys
    from pathlib import Path

    from scripts.textio import read_text_preserve, write_text_preserve

    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print("usage: python -m scripts.fixers.url_join <file.md>", file=sys.stderr)
        return 1
    p = Path(argv[0])
    text, newline = read_text_preserve(p)
    write_text_preserve(p, fix(text), newline)
    print(f"Done: {p}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_cli())
