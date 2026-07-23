"""Fixer package: deterministic, single-responsibility Markdown repair tools.

Registry: each fixer is a module in this package; register() it here once and it
joins the pipeline (postprocess) and the verifier's aggregated detect().
"""

from scripts.fixers.base import Fixer, Issue
from scripts.fixers import algorithm, chem_formula, images, math_delim, ocr_cleanup, table

__all__ = ["Fixer", "Issue", "register", "all_fixers", "select", "default_order"]

_ORDER = ["table", "chem_formula", "math_delim", "ocr_cleanup", "algorithm", "images"]
_REGISTRY: dict = {}


def register(fixer: Fixer) -> None:
    _REGISTRY[fixer.id] = fixer


def all_fixers() -> list:
    return [_REGISTRY[i] for i in _ORDER if i in _REGISTRY]


def select(ids: list) -> list:
    """Return the chosen fixers, ordered by default_order (not by input order)."""
    wanted = set(ids)
    return [_REGISTRY[i] for i in _ORDER if i in wanted and i in _REGISTRY]


def default_order() -> list:
    return list(_ORDER)


register(Fixer("table", "HTML tables to Markdown", False, table.convert_html_tables, table.detect))
register(Fixer("chem_formula", "chemical formula subscripts", False, chem_formula.fix, chem_formula.detect))
register(Fixer("math_delim", "math delimiter repair", False, math_delim.fix, math_delim.detect))
register(Fixer("ocr_cleanup", "deterministic OCR-noise cleanup", False, ocr_cleanup.fix, ocr_cleanup.detect))
register(Fixer("algorithm", "mineru-algorithm div conversion", False, algorithm.fix, algorithm.detect))
register(Fixer("images", "image copy and path rewrite", True, images.organize, images.detect))
