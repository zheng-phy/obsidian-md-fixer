"""Convert HTML <table> blocks in Markdown text to Markdown tables.

Uses only the standard library so the skill has no extra dependencies.
"""

import re
from html.parser import HTMLParser

_TABLE_RE = re.compile(r"<table>.*?</table>", re.DOTALL | re.IGNORECASE)


class _TableParser(HTMLParser):
    """Extract rows/cells from a single HTML table."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._current_row = []
        elif tag in ("td", "th") and self._current_row is not None:
            self._current_cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._current_cell is not None:
            self._current_row.append("".join(self._current_cell).strip())
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None:
            self.rows.append(self._current_row)
            self._current_row = None

    def handle_data(self, data):
        if self._current_cell is not None:
            self._current_cell.append(data)


def _render_markdown_table(rows: list[list[str]]) -> str:
    """Render parsed rows as a Markdown table. First row becomes the header."""
    if not rows:
        return ""
    col_count = max(len(r) for r in rows)
    rows = [r + [""] * (col_count - len(r)) for r in rows]
    lines = [
        "| " + " | ".join(rows[0]) + " |",
        "| " + " | ".join(["---"] * col_count) + " |",
    ]
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def convert_html_tables(markdown_text: str) -> str:
    """Replace every HTML <table> in the text with a Markdown table."""

    def _replace(match: re.Match) -> str:
        parser = _TableParser()
        parser.feed(match.group(0))
        return _render_markdown_table(parser.rows)

    return _TABLE_RE.sub(_replace, markdown_text)


_TABLE_DETECT_RE = re.compile(r"<table\b", re.IGNORECASE)


def detect(text: str) -> list:
    """Report each line still containing an HTML <table> tag."""
    from scripts.fixers.base import Issue

    return [
        Issue("table", i, "unconverted HTML <table>")
        for i, ln in enumerate(text.splitlines(), 1)
        if _TABLE_DETECT_RE.search(ln)
    ]


def _cli(argv=None) -> int:
    import sys
    from pathlib import Path

    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print("usage: python -m scripts.fixers.table <file.md>", file=sys.stderr)
        return 1
    p = Path(argv[0])
    p.write_text(convert_html_tables(p.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"Done: {p}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_cli())
