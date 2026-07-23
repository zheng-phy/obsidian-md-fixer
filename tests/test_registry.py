from scripts.fixers import all_fixers, select, default_order
from scripts.fixers.base import Issue, Fixer


def test_default_order():
    assert default_order() == ["table", "chem_formula", "math_delim", "ocr_cleanup", "algorithm", "code_fence", "images"]


def test_all_fixers_registered():
    ids = {f.id for f in all_fixers()}
    assert {"table", "chem_formula", "math_delim", "ocr_cleanup", "algorithm", "code_fence", "images"} <= ids


def test_select_subset():
    ids = [f.id for f in select(["table", "images"])]
    assert ids == ["table", "images"]


def test_select_preserves_default_order_not_input_order():
    ids = [f.id for f in select(["images", "table"])]
    assert ids == ["table", "images"]  # 按 default_order 排序


def test_issue_str():
    assert str(Issue("table", 3, "unconverted")) == "[table] line 3: unconverted"
