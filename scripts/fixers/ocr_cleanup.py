"""Deterministic OCR-noise cleanup (class A only).

Fixes only patterns that are unambiguous and cannot misfire: letter-spaces inside
whitelisted LaTeX commands, f^{\\backslash *} -> f^{*}, split digits (math only),
and HTML entities. Semantic-class issues (Greek-letter ?? placeholders) are
reported by detect() but never auto-fixed.
"""

import re

from scripts.fixers.base import Issue, split_zones

_FSTAR_RE = re.compile(r"f\^\{\\backslash \*\}")
_HTML_ENTITIES = {"&gt;": ">", "&lt;": "<", "&amp;": "&", "&quot;": '"'}
_DIGIT_SPACE_RE = re.compile(r"(?<=[\d.])\s+(?=\d)")
_GREEK_PLACEHOLDER_RE = re.compile(r"\?\?")
_LETTER_RUN_RE = re.compile(r"\b[A-Za-z](?:\s+[A-Za-z])+\b")
_SIGN_DIGIT_SPACE_RE = re.compile(r"(?<=[\-+^])\s+(?=\d)")


def _clean_letter_spaces(body: str) -> str:
    """Collapse 'd r a f t' -> 'draft' (single letters separated by spaces)."""
    return _LETTER_RUN_RE.sub(lambda m: m.group(0).replace(" ", ""), body)


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
    # collapse split digits/signs inside ^/_ braces: "10^{- 4}" -> "10^{-4}", "10 ^{-4}" -> "10^{-4}"
    text = re.sub(
        r"([\^_])\s*\{([^}]*)\}",
        lambda m: m.group(1) + "{" + _DIGIT_SPACE_RE.sub("", _SIGN_DIGIT_SPACE_RE.sub("", m.group(2))).strip() + "}",
        text,
    )
    return text


def _fix_math(seg: str) -> str:
    seg = _FSTAR_RE.sub("f^{*}", seg)
    seg = _fix_braces(seg)
    seg = re.sub(r"\s+(?=[\^_])", "", seg)  # "10 ^{-4}" -> "10^{-4}"
    seg = _SIGN_DIGIT_SPACE_RE.sub("", seg)
    seg = _DIGIT_SPACE_RE.sub("", seg)  # split digits; only safe inside math
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


def detect(text: str) -> list:
    """Report semantic-class OCR issues (Greek ?? placeholders); never auto-fixed."""
    problems = []
    for i, ln in enumerate(text.splitlines(), 1):
        if _GREEK_PLACEHOLDER_RE.search(ln):
            problems.append(Issue("ocr_cleanup", i, "suspected OCR char-mapping error (?? placeholder)"))
    return problems
