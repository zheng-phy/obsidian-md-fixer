"""Deterministic OCR-noise cleanup (class A only).

Fixes only patterns that are unambiguous and cannot misfire: letter-spaces inside
whitelisted LaTeX commands, f^{\\backslash *} variants -> f^{*}, split digits
(math only), HTML entities (text AND math), 5+ letter-runs in math (split words
like "a l l o w e d"), and the closed ff-ligature misspelling dictionary.
Semantic-class issues (Greek ?? placeholders, tuple-like sub/superscripts such
as X_{1 16}, 3-4 letter-runs, U+FFFD replacement chars, C0 control chars) are
reported by detect() but never auto-fixed.
"""

import re

from scripts.fixers.base import Issue, split_zones

# f-star variants MinerU emits: f^{\backslash *} and f^{\backslash^ {*}} both
# mean f^{*} (a backslash-as-asterisk OCR misread).
_FSTAR_RE = re.compile(r"f\^\{\\backslash\s*\^?\s*\{?\s*\*\s*\}?\}")
_HTML_ENTITIES = {"&gt;": ">", "&lt;": "<", "&amp;": "&", "&quot;": '"'}
_DIGIT_SPACE_RE = re.compile(r"(?<=[\d.])\s+(?=\d)")
_GREEK_PLACEHOLDER_RE = re.compile(r"\?\?")
_LETTER_RUN_RE = re.compile(r"\b[A-Za-z](?:\s+[A-Za-z])+\b")
_SIGN_DIGIT_SPACE_RE = re.compile(r"(?<=[\-+^])\s+(?=\d)")


def _clean_letter_spaces(body: str) -> str:
    """Collapse 'd r a f t' -> 'draft' (single letters separated by spaces)."""
    return _LETTER_RUN_RE.sub(lambda m: m.group(0).replace(" ", ""), body)


# Two or more complete integers in a sub/superscript (X_{1 16}) is likely a
# tuple MinerU split — never merge it silently, flag for review instead.
_TUPLE_SUBSCRIPT_BODY_RE = re.compile(r"\d+( \d+)+")


def _fix_braces(text: str) -> str:
    def cmd_rep(m):
        cmd = m.group(1)  # e.g. "\mathrm"
        body = _clean_letter_spaces(m.group(2)).strip()
        return cmd + "{" + body + "}"

    # normalize "\mathrm { body }" -> "\mathrm{body}" with letter-spaces collapsed
    text = re.sub(
        r"(\\(?:mathrm|text|operatorname|mathbf|mathit|mathsf|textbf|textit))\s*\{([^}]*)\}",
        cmd_rep, text,
    )

    def sub_rep(m):
        body = m.group(2).strip()
        if _TUPLE_SUBSCRIPT_BODY_RE.fullmatch(body):
            return m.group(0)  # possible tuple (X_{1 16}): keep verbatim
        # collapse split digits/signs inside ^/_ braces:
        # "10^{- 4}" -> "10^{-4}", "10 ^{-4}" -> "10^{-4}"
        cleaned = _DIGIT_SPACE_RE.sub("", _SIGN_DIGIT_SPACE_RE.sub("", m.group(2))).strip()
        return m.group(1) + "{" + cleaned + "}"

    text = re.sub(r"([\^_])\s*\{([^}]*)\}", sub_rep, text)
    return text


# Possible tuple in sub/superscript (X_{1 16}): stash it before the global
# digit-space merges below so it is never silently merged (B196).
_TUPLE_SUBSCRIPT_STASH_RE = re.compile(r"[\^_]\s*\{ *\d+( +\d+)+ *\}")
# Letter runs of 5+ single letters in math (a l l o w e d -> allowed, B196).
# 2-letter runs (x y) are variable pairs and stay; 3-4 are detect-only.
_LETTER_RUN5_RE = re.compile(r"\b[A-Za-z](?:\s+[A-Za-z]){4,}\b")
# Full maximal run (greedy, non-overlapping finditer makes this the whole
# run); the 3-4 letter case is decided by counting the spaces afterwards.
_LETTER_RUN_DETECT_RE = re.compile(r"\b[A-Za-z](?:\s+[A-Za-z])+\b")
# \begin{array}{r l r}: the column-format string is NOT a split word (MoE稀疏
# 门控 误报/误合并). Stash it (or blank it in detect) before letter-run work.
_ARRAY_DECL_RE = re.compile(
    r"\\begin\{(?:array|tabular|matrix|pmatrix|bmatrix|cases)\}\s*\{[^{}]*\}"
)


def _fix_math(seg: str) -> str:
    saved: list = []

    def stash(m: re.Match) -> str:
        saved.append(m.group(0))
        return f"\x01T{len(saved) - 1}\x01"

    seg = _CONTROL_RE.sub("", seg)  # C0 chars first, before stashing markers
    seg = _ARRAY_DECL_RE.sub(stash, seg)
    seg = _TUPLE_SUBSCRIPT_STASH_RE.sub(stash, seg)
    seg = _FSTAR_RE.sub("f^{*}", seg)
    seg = _fix_braces(seg)
    seg = re.sub(r"\s+(?=[\^_])", "", seg)  # "10 ^{-4}" -> "10^{-4}"
    seg = _SIGN_DIGIT_SPACE_RE.sub("", seg)
    seg = _DIGIT_SPACE_RE.sub("", seg)  # split digits; only safe inside math
    seg = _LETTER_RUN5_RE.sub(lambda m: re.sub(r"\s+", "", m.group(0)), seg)  # split words
    for ent, ch in _HTML_ENTITIES.items():  # math zones get entities too (B157)
        seg = seg.replace(ent, ch)
    for i, orig in enumerate(saved):
        seg = seg.replace(f"\x01T{i}\x01", orig)
    return seg


def _fix_text_zone(seg: str) -> str:
    seg = _CONTROL_RE.sub("", seg)  # C0 control chars are never legal in md (B026)
    for ent, ch in _HTML_ENTITIES.items():
        seg = seg.replace(ent, ch)
    seg = _fix_braces(seg)  # whitelisted letter-spaces can appear inline
    # ligature misses: lowercase word-boundary only (Dificult untouched)
    seg = _LIGATURE_RE.sub(lambda m: _LIGATURE_DICT[m.group(1)], seg)
    return seg


def fix(text: str) -> str:
    """Fix deterministic OCR noise; protected zones untouched."""
    out = []
    for kind, seg in split_zones(text):
        if kind == "math":
            out.append(_fix_math(seg))
        elif kind == "text":
            out.append(_fix_text_zone(seg))
        else:
            out.append(seg)
    return "".join(out)


_TUPLE_SUBSCRIPT_RE = re.compile(r"[\^_]\{ *\d+( +\d+)+\}")
_FFFD_RE = re.compile(r"�")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# Closed ligature-miss dictionary: forms where a lost "ff" produces a spelling
# that is NEVER a valid English word (class-A: auto-fix is safe). Every entry
# is a misspelling of one word only; anything that could be a real word is
# excluded (e.g. "of" was considered and rejected). Annotated with the sample
# document the form was observed in. Do not grow this list with guesses.
_LIGATURE_DICT = {
    "dificult": "difficult",
    "dificulty": "difficulty",
    "dificulties": "difficulties",
    "efect": "effect",
    "efective": "effective",
    "efectively": "effectively",
    "efectiveness": "effectiveness",
    "eficiency": "efficiency",
    "eficient": "efficient",
    "ofline": "offline",
    "ofers": "offers",
    "ofer": "offer",
    "ofce": "office",
    "diferent": "different",
    "diference": "difference",
    "efort": "effort",
    "aect": "affect",
    "afected": "affected",
    "eect": "effect",
    "specication": "specification",
    "conguration": "configuration",
    "proling": "profiling",
}
_LIGATURE_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in _LIGATURE_DICT) + r")\b"
)


def detect(text: str) -> list:
    """Report semantic-class OCR issues (Greek ?? placeholders); never auto-fixed."""
    problems = []
    pos = 0
    fffd_lines: set = set()  # dedup across zones: one issue per LINE
    for kind, seg in split_zones(text):
        base_line = text[:pos].count("\n") + 1
        if kind == "math":
            for m in _TUPLE_SUBSCRIPT_RE.finditer(seg):
                problems.append(Issue(
                    "ocr_cleanup",
                    base_line + seg[: m.start()].count("\n"),
                    "space-separated numbers in sub/superscript "
                    "(possible tuple, e.g. X_{1,16}) — review",
                ))
            # array 格式串逐字符 blank 掉(位置对齐),r l r 不参与 letter-run 判定
            no_array = _ARRAY_DECL_RE.sub(lambda m: " " * len(m.group(0)), seg)
            for m in _LETTER_RUN_DETECT_RE.finditer(no_array):
                if 2 <= m.group(0).count(" ") <= 3:  # exactly 3-4 letters
                    problems.append(Issue(
                        "ocr_cleanup",
                        base_line + seg[: m.start()].count("\n"),
                        "letter-run in math (possible split word) — review",
                    ))
        if kind in ("text", "math"):
            fffd_lines.update(
                base_line + seg[: m.start()].count("\n") for m in _FFFD_RE.finditer(seg)
            )
        # C0 chars are auto-removed from text/math; code zones are untouched,
        # so detect still reports them there (fixer cannot reach into fences).
        if kind in ("text", "math", "code_block", "inline_code"):
            ctl = _CONTROL_RE.search(seg)
            if ctl:
                problems.append(Issue(
                    "ocr_cleanup",
                    base_line + seg[: ctl.start()].count("\n"),
                    f"control char U+{ord(ctl.group(0)):04X} in text",
                ))
        pos += len(seg)
    for line in sorted(fffd_lines):
        problems.append(Issue(
            "ocr_cleanup", line,
            "U+FFFD replacement char (lost glyph; restore from PDF)",
        ))
    for i, ln in enumerate(text.splitlines(), 1):
        if _GREEK_PLACEHOLDER_RE.search(ln):
            problems.append(Issue("ocr_cleanup", i, "suspected OCR char-mapping error (?? placeholder)"))
    return problems
