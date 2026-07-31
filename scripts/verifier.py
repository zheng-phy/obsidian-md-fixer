"""Aggregate all fixers' detect() into a single issue list for the agent.

This is the interface between deterministic fixes and agent-driven semantic
fixes: each fixer reports what remains after its mechanical pass, with line
numbers, so the agent can repair semantics (superscripts, broken sentences).
Also retains checks no single fixer owns (e.g. $ delimiter balance) and the
chem-opportunity hint (the inverse of the old doc-profile hint: since
chem_formula is opt-in, point chemistry documents at it).
"""

import re
from pathlib import Path

from scripts.fixers import all_fixers, select
from scripts.fixers.base import Issue, split_zones

_CODE_RE = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)
_DISPLAY_MATH_MARKER_RE = re.compile(r"\$\$")

# Closed list of chemistry-domain context words (stable domain vocabulary,
# allowed by the v2 constraint; everything else stays open in detect()).
_CHEM_CONTEXT_WORDS = ("溶液", "反应", "材料", "化学", "mol", "L", "XRD", "SEM", "TEM", "chemical", "reaction")
_CHEM_OPPORTUNITY_THRESHOLD = 3


def _chem_opportunity(text: str) -> Issue | None:
    """Suggest --fixers chem_formula when bare formula-like tokens cluster.

    Counts DISTINCT periodic-table-valid tokens (same _is_formula_token gate
    the fixer uses) surviving outside protected zones; >=3 distinct tokens
    triggers the hint. Chemistry-context words upgrade the wording; without
    them the hint stays neutral. Suppressed entirely when chem_formula is
    selected (its own detect() then handles reporting).
    """
    from scripts.fixers.chem_formula import _FORMULA_RE, _is_formula_token

    tokens: set = set()
    for kind, seg in split_zones(text):
        if kind == "text":
            tokens.update(
                m.group(0) for m in _FORMULA_RE.finditer(seg) if _is_formula_token(m.group(0))
            )
    if len(tokens) < _CHEM_OPPORTUNITY_THRESHOLD:
        return None
    examples = ", ".join(sorted(tokens)[:2])
    if any(w in text for w in _CHEM_CONTEXT_WORDS):
        msg = (f"detected {len(tokens)} formula-like tokens (e.g. {examples}) — "
               "likely a chemistry document; re-run with `--fixers chem_formula`")
    else:
        msg = (f"detected {len(tokens)} formula-like tokens (e.g. {examples}) — "
               "if this is a chemistry/materials document, re-run with `--fixers chem_formula`")
    return Issue("verifier", 0, msg)


def _check_dollar_balance(text: str) -> list[str]:
    """Report unpaired $ / $$ delimiters with their first unpaired line."""
    problems: list[str] = []
    body = _CODE_RE.sub(lambda match: "\n" * match.group(0).count("\n"), text)
    body = body.replace("\\$", "\x04")
    display_markers = len(_DISPLAY_MATH_MARKER_RE.findall(body))
    if display_markers % 2 != 0:
        line = body[: body.rfind("$$")].count("\n") + 1
        problems.append(f"line {line}: unpaired $$ delimiters")
    single_dollars = _DISPLAY_MATH_MARKER_RE.sub("", body)
    if single_dollars.count("$") % 2 != 0:
        line = single_dollars[: single_dollars.rfind("$")].count("\n") + 1
        problems.append(f"line {line}: unpaired $ delimiters")
    return problems


def verify_issues(md_path: Path, fixer_ids: list | None = None) -> list:
    """Aggregate selected fixers' detect() into structured Issue objects."""
    md_path = Path(md_path)
    text = md_path.read_text(encoding="utf-8")
    chosen = select(fixer_ids) if fixer_ids else all_fixers()

    issues: list = []
    for fixer in chosen:
        target = md_path if fixer.file_based else text
        issues += fixer.detect(target)
    for msg in _check_dollar_balance(text):
        issues.append(Issue("verifier", 0, msg))
    if not any(f.id == "chem_formula" for f in chosen):
        opportunity = _chem_opportunity(text)
        if opportunity:
            issues.insert(0, opportunity)
    return issues


def verify(md_path: Path, fixer_ids: list | None = None) -> list[str]:
    """Aggregate selected fixers' detect() into string issues (empty = pass)."""
    return [str(issue) for issue in verify_issues(md_path, fixer_ids)]
