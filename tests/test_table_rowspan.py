from scripts.fixers.table import convert_html_tables, detect


def test_table_with_colspan_kept_as_html():
    html = '<table><tr><th colspan="2">Header</th></tr><tr><td>a</td><td>b</td></tr></table>'
    out = convert_html_tables(html)
    assert "<table" in out


def test_table_with_rowspan_kept_as_html():
    html = '<table><tr><td rowspan="2">X</td><td>a</td></tr><tr><td>b</td></tr></table>'
    out = convert_html_tables(html)
    assert "<table" in out


def test_simple_table_still_converted():
    html = "<table><tr><td>a</td><td>b</td></tr></table>"
    out = convert_html_tables(html)
    assert "| a | b |" in out and "<table" not in out


def test_detect_flags_merged_cell_table():
    html = 'line1\n<table><tr><td colspan="2">H</td></tr></table>'
    problems = detect(html)
    assert any("merged" in p.message.lower() or "colspan" in p.message.lower() for p in problems)


def test_detect_simple_table_still_flagged_unconverted():
    problems = detect("<table><tr><td>x</td></tr></table>")
    assert any("table" in p.message.lower() for p in problems)
