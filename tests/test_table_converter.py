from pathlib import Path

from scripts.fixers.table import convert_html_tables

FIXTURES = Path(__file__).parent / "fixtures"


def test_converts_html_table_to_markdown():
    html = (FIXTURES / "sample_table.html").read_text(encoding="utf-8")
    expected = (FIXTURES / "sample_table_expected.md").read_text(encoding="utf-8").strip()
    assert convert_html_tables(html).strip() == expected


def test_preserves_formulas_inside_cells():
    html = "<table><tr><td>$E=mc^2$</td></tr></table>"
    result = convert_html_tables(html)
    assert "$E=mc^2$" in result


def test_preserves_surrounding_text():
    md = "Before.\n\n<table><tr><td>x</td></tr></table>\n\nAfter."
    result = convert_html_tables(md)
    assert result.startswith("Before.")
    assert result.endswith("After.")
    assert "<table>" not in result
