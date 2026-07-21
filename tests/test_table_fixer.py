from scripts.fixers.table import convert_html_tables, detect


def test_convert_still_works():
    html = "<table><tr><td>a</td></tr></table>"
    assert "| a |" in convert_html_tables(html)


def test_detect_reports_line():
    text = "line1\n\n<table><tr><td>x</td></tr></table>\nline4"
    problems = detect(text)
    assert any(p.fixer == "table" and p.line == 3 for p in problems)


def test_detect_clean_when_no_table():
    assert detect("no table here") == []
