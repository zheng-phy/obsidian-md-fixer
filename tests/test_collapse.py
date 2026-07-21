from scripts.postprocess import _format_issues
from scripts.fixers.base import Issue


def test_few_issues_not_collapsed():
    issues = [Issue("table", 1, "t1"), Issue("images", 2, "i1")]
    out = _format_issues(issues)
    assert len(out) == 2
    assert any("table" in o for o in out)


def test_many_issues_collapsed_with_summary_and_skip_hint():
    issues = [Issue("chem_formula", i, f"formula F{i}") for i in range(1, 31)]
    out = _format_issues(issues)
    # 折叠为一行汇总 + 少量示例,而不是 30 行
    assert len(out) < 31
    summary = out[0]
    assert "chem_formula" in summary and "30" in summary
    assert "--skip chem_formula" in summary


def test_mixed_fixers_only_flood_one_collapsed():
    issues = [Issue("chem_formula", i, f"F{i}") for i in range(25)]
    issues += [Issue("math_delim", 5, "broken tag")]
    out = _format_issues(issues)
    # chem_formula 折叠,math_delim 那条真实告警保留可见
    assert any("math_delim" in o and "broken tag" in o for o in out)
    assert any("chem_formula" in o and "25" in o for o in out)
