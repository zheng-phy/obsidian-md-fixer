"""Chemical formula subscript fixer (opt-in since v2.0.0).

Wraps bare formulas like SiO2 / C4 / C6H12O6 as $SiO_2$ / $C_4$ / $C_6H_{12}O_6$
so they render as LaTeX subscripts in Obsidian. Only touches 'text' segments;
protected zones (images, code, URLs, existing math) are left intact.

Since v2: a token is only treated as a formula when it contains >=1 digit and
every letter segments into symbols of the closed 118-element periodic table.
This prunes the ML/AI flood (GPT2, MoE, LoRA, SiLU, BRCA1, ...) that the v1
layout heuristic accepted. Segmentation is a single left-to-right greedy pass
(2-letter symbol first, then 1-letter; no backtracking) — deliberately stricter
than full backtracking so glued common terms like BRCA (Br+Ca) stay rejected.
"""

import re

from scripts.fixers.base import split_zones

# The 118 IUPAC element symbols (case-sensitive; e.g. "Si" yes, "sI" no).
_ELEMENTS: frozenset[str] = frozenset(
    """H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni
    Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe
    Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg
    Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg
    Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og""".split()
)

_FORMULA_RE = re.compile(
    r"(?<![A-Za-z0-9$-])(?:(?:[A-Z][a-z]?\d*){2,}|[A-Z][a-z]?\d+)(?![A-Za-z0-9])"
)
_DIGIT_RUN_RE = re.compile(r"(\d+)")
_ML_LIKE_RE = re.compile(
    r"^(?:(?=.*[A-Z])(?=.*[a-z])[A-Za-z]+|[A-Z]{3,}\d+)$"
)


def _segmentable(letters: str) -> bool:
    """Return whether letters can be fully split into element symbols.

    Greedy left-to-right pass: try a 2-letter symbol at each position, fall
    back to a 1-letter one, never revisit an earlier position (no
    backtracking). See module docstring for why stricter-than-backtracking.
    """
    i = 0
    n = len(letters)
    while i < n:
        if letters[i : i + 2] in _ELEMENTS:
            i += 2
        elif letters[i] in _ELEMENTS:
            i += 1
        else:
            return False
    return True


def _is_formula_token(token: str) -> bool:
    """Return whether token is a plausible chemical formula.

    Requires >=1 digit (letter-only tokens like SiC / SiLU / XRD are never
    formulas here) and all letters segmentable into element symbols.
    """
    if not re.search(r"\d", token):
        return False
    letters = re.sub(r"[^A-Za-z]", "", token)
    return bool(letters) and _segmentable(letters)


def _fix_segment(seg: str) -> str:
    def rep(m: re.Match) -> str:
        t = m.group(0)
        if not _is_formula_token(t):
            return t
        return "$" + _DIGIT_RUN_RE.sub(r"_{\1}", t) + "$"

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
                if _is_formula_token(m.group(0))
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
                if _is_formula_token(token):
                    problems.append(Issue(
                        "chem_formula",
                        base_line + seg[: m.start()].count("\n"),
                        f"possible unfixed formula: {token}",
                    ))
                elif _looks_like_ml_term(token):
                    # still-bare suspicious token the periodic table rejected;
                    # agent decides whether it is an ML term (or a real formula
                    # needing a manual wrap)
                    problems.append(Issue(
                        "chem_formula",
                        base_line + seg[: m.start()].count("\n"),
                        f"possible ML/AI term (left bare by periodic-table validation): {token} "
                        "(review; wrap manually only if it is a real formula)",
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
