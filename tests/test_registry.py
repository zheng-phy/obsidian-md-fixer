from scripts.fixers import all_fixers, select, default_order
from scripts.fixers.base import Issue, Fixer


def test_default_order():
    # fffd_restore 必须最先运行(ocr_cleanup 合并空格会破坏 U+FFFD 对齐);
    # table_flatten 紧随 table(只有 span 表会被保留为 HTML)
    assert default_order() == ["fffd_restore", "table", "table_flatten", "chem_formula", "math_delim", "ocr_cleanup", "algorithm", "code_fence", "url_join", "images"]


def test_all_fixers_registered():
    ids = {f.id for f in all_fixers()}
    assert {"fffd_restore", "table", "chem_formula", "math_delim", "ocr_cleanup", "algorithm", "code_fence", "url_join", "images"} <= ids


def test_select_subset():
    ids = [f.id for f in select(["table", "images"])]
    assert ids == ["table", "images"]


def test_select_preserves_default_order_not_input_order():
    ids = [f.id for f in select(["images", "table"])]
    assert ids == ["table", "images"]  # 按 default_order 排序


def test_issue_str():
    assert str(Issue("table", 3, "unconverted")) == "[table] line 3: unconverted"


def test_chem_formula_is_opt_in():
    # v2:chem_formula 退出默认集合,但仍注册可被显式选中
    fixers = {f.id: f for f in all_fixers()}
    assert fixers["chem_formula"].default_on is False
    assert fixers["table"].default_on is True
    assert fixers["images"].default_on is True
    assert "chem_formula" in default_order()  # _ORDER 不变


def test_select_chem_formula_still_works():
    assert [f.id for f in select(["chem_formula"])] == ["chem_formula"]
