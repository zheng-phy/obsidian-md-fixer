"""Deterministic OCR-noise cleanup (class A only).

Fixes only patterns that are unambiguous and cannot misfire: letter-spaces inside
whitelisted LaTeX commands, f^{\\backslash *} -> f^{*}, split digits (math only),
and HTML entities. Semantic-class issues (Greek-letter ?? placeholders) are
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


def _fix_math(seg: str) -> str:
    saved: list = []

    def stash(m: re.Match) -> str:
        saved.append(m.group(0))
        return f"\x01T{len(saved) - 1}\x01"

    seg = _TUPLE_SUBSCRIPT_STASH_RE.sub(stash, seg)
    seg = _FSTAR_RE.sub("f^{*}", seg)
    seg = _fix_braces(seg)
    seg = re.sub(r"\s+(?=[\^_])", "", seg)  # "10 ^{-4}" -> "10^{-4}"
    seg = _SIGN_DIGIT_SPACE_RE.sub("", seg)
    seg = _DIGIT_SPACE_RE.sub("", seg)  # split digits; only safe inside math
    for ent, ch in _HTML_ENTITIES.items():  # math zones get entities too (B157)
        seg = seg.replace(ent, ch)
    for i, orig in enumerate(saved):
        seg = seg.replace(f"\x01T{i}\x01", orig)
    return seg


def _fix_text_zone(seg: str) -> str:
    for ent, ch in _HTML_ENTITIES.items():
        seg = seg.replace(ent, ch)
    seg = _fix_braces(seg)  # whitelisted letter-spaces can appear inline
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


def detect(text: str) -> list:
    """Report semantic-class OCR issues (Greek ?? placeholders); never auto-fixed."""
    problems = []
    pos = 0
    for kind, seg in split_zones(text):
        if kind == "math":
            base_line = text[:pos].count("\n") + 1
            for m in _TUPLE_SUBSCRIPT_RE.finditer(seg):
                problems.append(Issue(
                    "ocr_cleanup",
                    base_line + seg[: m.start()].count("\n"),
                    "space-separated numbers in sub/superscript "
                    "(possible tuple, e.g. X_{1,16}) — review",
                ))
        pos += len(seg)
    for i, ln in enumerate(text.splitlines(), 1):
        if _GREEK_PLACEHOLDER_RE.search(ln):
            problems.append(Issue("ocr_cleanup", i, "suspected OCR char-mapping error (?? placeholder)"))
    return problems
