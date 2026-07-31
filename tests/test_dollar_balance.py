from scripts.verifier import _check_dollar_balance


def test_escaped_dollar_not_counted():
    assert _check_dollar_balance(r"price \$2.03 done") == []


def test_unpaired_dollar_reports_line():
    problems = _check_dollar_balance("line one\nbroken $x here")
    assert any("2" in problem for problem in problems)


def test_paired_dollar_clean():
    assert _check_dollar_balance("ok $x^2$ end") == []
