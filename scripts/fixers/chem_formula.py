"""Chemical formula subscript fixer.

Wraps bare formulas like SiO2 / C4 / C6H12O6 as $SiO_2$ / $C_4$ / $C_6H_{12}O_6$
so they render as LaTeX subscripts in Obsidian. Only touches 'text' segments;
protected zones (images, code, URLs, existing math) are left intact.
"""

import re

from scripts.fixers.base import split_zones

_FORMULA_RE = re.compile(
    r"(?<![A-Za-z0-9$])(?:(?:[A-Z][a-z]?\d*){2,}|[A-Z][a-z]?\d+)(?![A-Za-z0-9])"
)
_ACRONYM_RE = re.compile(r"[A-Z]+")
_DIGIT_RUN_RE = re.compile(r"(\d+)")
_ML_LIKE_RE = re.compile(
    r"^(?:(?=.*[A-Z])(?=.*[a-z])[A-Za-z]+|[A-Z]{3,}\d+)$"
)


def _fix_segment(seg: str) -> str:
    def rep(m: re.Match) -> str:
        t = m.group(0)
        if _ACRONYM_RE.fullmatch(t):
            return t  # all-caps word (XRD, SEM) is an acronym, not a formula
        return "$" + _DIGIT_RUN_RE.sub(r"_\1", t) + "$"

    return _FORMULA_RE.sub(rep, seg)


def fix(text: str) -> str:
    """Return text with bare chemical formulas wrapped as LaTeX math."""
    return "".join(_fix_segment(s) if k == "text" else s for k, s in split_zones(text))


def find_unfixed_formulas(text: str) -> list[str]:
    """Return formula-like tokens still bare outside protected zones."""
    out: list[str] = []
    for k, s in split_zones(text):
        if k == "text":
            out += [
                m.group(0)
                for m in _FORMULA_RE.finditer(s)
                if not _ACRONYM_RE.fullmatch(m.group(0))
            ]
    return out


def _looks_like_ml_term(token: str) -> bool:
    """Return whether a formula-like token looks like an ML/AI term."""
    return bool(_ML_LIKE_RE.fullmatch(token))


def detect(text: str) -> list:
    """Report each line still containing a bare chemical formula.

    Scans the whole document by zone (only 'text' segments), so fenced code is
    never reported. Line numbers are translated from each segment's offset in
    the original text.
    """
    from scripts.fixers.base import Issue

    problems: list = []
    pos = 0
    for kind, seg in split_zones(text):
        if kind == "text":
            base_line = text[:pos].count("\n") + 1
            for m in _FORMULA_RE.finditer(seg):
                token = m.group(0)
                if _ACRONYM_RE.fullmatch(token):
                    continue
                message = (
                    f"possible ML/AI term mis-flagged as formula: {token} "
                    "(review; consider --skip chem_formula)"
                    if _looks_like_ml_term(token)
                    else f"possible unfixed formula: {token}"
                )
                problems.append(Issue("chem_formula", base_line + seg[: m.start()].count("\n"), message))
        pos += len(seg)
    return problems


def _cli(argv=None) -> int:
    import sys
    from pathlib import Path

    from scripts.textio import read_text_preserve, write_text_preserve

    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print("usage: python -m scripts.fixers.chem_formula <file.md>", file=sys.stderr)
        return 1
    p = Path(argv[0])
    text, newline = read_text_preserve(p)
    write_text_preserve(p, fix(text), newline)
    print(f"Done: {p}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_cli())
