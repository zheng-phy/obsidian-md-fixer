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

# Closed list of chemistry-domain context evidence (stable domain vocabulary,
# allowed by the v2 constraint; everything else stays open in detect()).
# Regex, not substring: a bare "L" would match every LLM paper, and "mol"
# matches "molecular".
_CHEM_CONTEXT_RE = re.compile(r"溶液|反应|材料|化学|mol/L|XRD|SEM|TEM|\bchemical\b|\breaction\b")
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
    if _CHEM_CONTEXT_RE.search(text):
        msg = (f"detected {len(tokens)} formula-like tokens (e.g. {examples}) — "
               "likely a chemistry document; re-run with `--fixers chem_formula`")
    else:
        msg = (f"detected {len(tokens)} formula-like tokens (e.g. {examples}) — "
               "if this is a chemistry/materials document, re-run with `--fixers chem_formula`")
    return Issue("verifier", 0, msg)


# Residual-risk net for chem_formula: a wrap like $V_{3}$ / $K_{3}$ (single
# element letter + digit subscript — braced since the v2 multi-digit fix)
# could just as well be a variable subscript (V_3 = version 3, K_3 = graph
# constant). The periodic-table gate cannot reject these, so when chem_formula
# ran they are flagged for agent review — small count by construction.
# Braces optional so hand-written/unbraced $V_3$ forms are caught too.
_LOW_CONFIDENCE_WRAP_RE = re.compile(r"^\$([A-Z][a-z]?)_\{?\d+\}?\$$")


def _low_confidence_wraps(text: str) -> list:
    """Report single-element wraps in math zones (run only with chem_formula).

    Same-shape tokens cluster into one issue (2021B: $C_{4}$ ×184 was a
    184-line flood); different tokens stay separate.
    """
    problems: list = []
    counts: dict = {}
    first_line: dict = {}
    pos = 0
    for kind, seg in split_zones(text):
        if kind == "math":
            m = _LOW_CONFIDENCE_WRAP_RE.match(seg)
            if m:
                token = m.group(0)
                line = text[:pos].count("\n") + 1
                counts[token] = counts.get(token, 0) + 1
                first_line.setdefault(token, line)
        pos += len(seg)
    for token, count in counts.items():
        msg = f"low-confidence wrap: {token}"
        if count > 1:
            msg += f" ×{count} (first at line {first_line[token]})"
        msg += " — verify formula vs name/label (single element + digits)"
        problems.append(Issue("chem_formula", first_line[token], msg))
    return problems


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
    else:
        issues += _low_confidence_wraps(text)
    return issues


def verify(md_path: Path, fixer_ids: list | None = None) -> list[str]:
    """Aggregate selected fixers' detect() into string issues (empty = pass)."""
    return [str(issue) for issue in verify_issues(md_path, fixer_ids)]
