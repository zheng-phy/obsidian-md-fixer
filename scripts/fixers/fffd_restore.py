"""Restore U+FFFD replacement chars from MinerU content_list_v2.json.

MinerU renders the .md from its content_list JSON; when glyphs are lost in
the .md (U+FFFD), the JSON fragments can still carry the original text.
Restore is deliberately conservative — "skeleton alignment, never fabricate":

* for each line containing U+FFFD, its skeleton (line minus U+FFFD, minus
  whitespace) must align inside exactly ONE JSON fragment, with every U+FFFD
  position mapping to a unique contiguous run of fragment characters;
* 0 or >=2 ways to align (or the fragment itself has U+FFFD where the line
  does not) -> the line is left untouched and reported as unaligned.

The content_list_v2.json comes in two shapes: a flat list of items (B007) or
a paginated list of lists (ZEDA); both are handled.
"""

import json
import re
import sys
from pathlib import Path

from scripts.fixers.base import Issue
from scripts.textio import read_text_preserve, write_text_preserve

# The alignment DP recurses one level per line character (every branch advances
# the line index), so depth is bounded by line length; raise the limit well
# beyond the longest md line (ZEDA worst case ~1400 chars).
sys.setrecursionlimit(20000)

_FFFD = "\ufffd"
_WS_RE = re.compile(r"\s")
_GAP_MAX = 12  # longest accepted gap (chars a single U+FFFD may have replaced)


def _norm(s: str) -> str:
    """Remove all whitespace (line-wrap differences are insignificant)."""
    return _WS_RE.sub("", s)


def _extract_fragments(data) -> list:
    """Ordered text fragments from content_list_v2.json (flat or paginated).

    Each paragraph/title's text+equation_inline pieces are CONCATENATED into
    one fragment (the paragraph body), in document order.
    """
    pages = (
        data
        if isinstance(data, list) and data and isinstance(data[0], list)
        else [data]
    )
    out = []
    for page in pages:
        for item in page:
            if not isinstance(item, dict):
                continue
            kind = item.get("type")
            if kind == "title":
                pieces = item.get("content", {}).get("title_content", [])
            elif kind == "paragraph":
                pieces = item.get("content", {}).get("paragraph_content", [])
            else:
                pieces = []
            joined = "".join(
                piece.get("content", "")
                for piece in pieces
                if isinstance(piece, dict)
                and piece.get("type") in ("text", "equation_inline")
            )
            if joined:
                out.append(joined)
    return out


def _is_subsequence(needle: str, haystack: str) -> bool:
    it = iter(haystack)
    return all(ch in it for ch in needle)


def _count_align(line_chars: str, frag_chars: str, i: int, j: int, memo: dict) -> int:
    """Number of ways (capped at 2) to align line_chars[i:] with frag_chars[j:].

    The line must consume the WHOLE fragment (skeleton-equality per the plan:
    fragment minus whitespace equals the skeleton), so both must end together.
    Rules: identical chars match 1:1; a line U+FFFD consumes a contiguous run
    of non-U+FFFD fragment chars (its gap); a fragment U+FFFD where the line
    has a real char is not alignable.
    """
    key = (i, j)
    if key in memo:
        return memo[key]
    if i == len(line_chars):
        return 1 if j == len(frag_chars) else 0
    if j == len(frag_chars):
        return 0
    lc, fc = line_chars[i], frag_chars[j]
    total = 0
    if lc == fc:
        total += _count_align(line_chars, frag_chars, i + 1, j + 1, memo)
    if lc == _FFFD:
        k = j + 1
        while k <= len(frag_chars) and k - j <= _GAP_MAX:
            if frag_chars[k - 1] == _FFFD:
                break
            total += _count_align(line_chars, frag_chars, i + 1, k, memo)
            if total >= 2:
                break
            k += 1
    memo[key] = 2 if total >= 2 else total
    return memo[key]


def _align_gaps(line_chars: str, frag_chars: str) -> list | None:
    """Return [(pos_in_line_chars, gap), ...] per gap-FFFD, or None unless UNIQUE."""
    memo: dict = {}
    if _count_align(line_chars, frag_chars, 0, 0, memo) != 1:
        return None
    gaps: list = []
    i = j = 0
    while i < len(line_chars):
        lc = line_chars[i]
        if j < len(frag_chars) and lc == frag_chars[j]:
            i += 1
            j += 1
            continue
        if lc != _FFFD or j >= len(frag_chars):
            return None
        best_k = None
        k = j + 1
        while k <= len(frag_chars) and k - j <= _GAP_MAX:
            if frag_chars[k - 1] == _FFFD:
                break
            if _count_align(line_chars, frag_chars, i + 1, k, memo) == 1:
                best_k = k
                break
            k += 1
        if best_k is None:
            return None
        gaps.append((i, frag_chars[j:best_k]))
        i += 1
        j = best_k
    return gaps


def _apply_gaps(line: str, gaps_by_pos: dict) -> str:
    """Replace U+FFFD at the given line_chars positions with their gap text."""
    out = []
    pos = 0  # index into the whitespace-stripped line
    for ch in line:
        if ch.isspace():
            out.append(ch)
        else:
            out.append(gaps_by_pos.get(pos, ch))
            pos += 1
    return "".join(out)


def restore_text(text: str, fragments: list) -> tuple:
    """Return (fixed text, residual line numbers still containing U+FFFD)."""
    frag_chars_list = [_norm(f) for f in fragments if _norm(f)]
    lines = text.split("\n")
    out: list = []
    residuals: list = []
    for n, line in enumerate(lines, 1):
        if _FFFD not in line:
            out.append(line)
            continue
        line_chars = _norm(line)
        skeleton = line_chars.replace(_FFFD, "")
        candidates: list = []
        for f in frag_chars_list:
            if len(f) < len(skeleton) or not _is_subsequence(skeleton, f):
                continue
            gaps = _align_gaps(line_chars, f)
            if gaps is not None:
                candidates.append(gaps)
        if len(candidates) == 1:
            # aligned (possibly no-op when the fragment is equally broken)
            out.append(_apply_gaps(line, dict(candidates[0])))
            continue
        residuals.append(n)
        out.append(line)
    return "\n".join(out), residuals


def run(md_path: Path, content_list_path: Path) -> list:
    """Restore U+FFFD in md_path from content_list JSON; returns residual lines."""
    md_path = Path(md_path)
    data = json.loads(Path(content_list_path).read_text(encoding="utf-8"))
    fragments = _extract_fragments(data)
    text, newline = read_text_preserve(md_path)
    fixed, residuals = restore_text(text, fragments)
    if fixed != text:
        write_text_preserve(md_path, fixed, newline)
    return residuals


def detect(md_path: Path) -> list:
    """Hint when U+FFFD remains and no --content-list restore was attempted."""
    md_path = Path(md_path)
    text = md_path.read_text(encoding="utf-8")
    n = sum(1 for ln in text.splitlines() if _FFFD in ln)
    if not n:
        return []
    return [
        Issue(
            "fffd_restore",
            0,
            f"{n} line(s) contain U+FFFD replacement char (lost glyph); "
            "MinerU content_list_v2.json may allow automatic restore — "
            "pass --content-list PATH",
        )
    ]


def _cli(argv=None) -> int:
    import sys

    if argv is None:
        argv = sys.argv[1:]
    if len(argv) < 2:
        print("usage: python -m scripts.fixers.fffd_restore <file.md> <content_list_v2.json>", file=sys.stderr)
        return 1
    residuals = run(Path(argv[0]), Path(argv[1]))
    print(f"Done: {argv[0]} (unaligned lines: {len(residuals)})")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_cli())
