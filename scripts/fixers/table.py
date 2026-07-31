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
        self.has_span = False
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._current_row = []
        elif tag in ("td", "th") and self._current_row is not None:
            attributes = dict(attrs)
            if attributes.get("rowspan") not in (None, "1") or attributes.get(
                "colspan"
            ) not in (None, "1"):
                self.has_span = True
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
        if parser.has_span:
            return match.group(0)
        return _render_markdown_table(parser.rows)

    return _TABLE_RE.sub(_replace, markdown_text)


_TABLE_DETECT_RE = re.compile(r"<table\b", re.IGNORECASE)


def detect(text: str) -> list:
    """Report each line still containing an HTML <table> tag."""
    from scripts.fixers.base import Issue

    problems = []
    table_blocks = list(_TABLE_RE.finditer(text))
    for table in table_blocks:
        line = text[: table.start()].count("\n") + 1
        parser = _TableParser()
        parser.feed(table.group(0))
        message = (
            "table with merged cells kept as HTML (needs agent)"
            if parser.has_span
            else "unconverted HTML <table>"
        )
        problems.append(Issue("table", line, message))

    for line, text_line in enumerate(text.splitlines(), 1):
        for match in _TABLE_DETECT_RE.finditer(text_line):
            position = sum(len(previous) + 1 for previous in text.splitlines()[: line - 1]) + match.start()
            if not any(table.start() <= position < table.end() for table in table_blocks):
                problems.append(Issue("table", line, "unconverted HTML <table>"))
    return problems


def _cli(argv=None) -> int:
    import sys
    from pathlib import Path

    from scripts.textio import read_text_preserve, write_text_preserve

    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print("usage: python -m scripts.fixers.table <file.md>", file=sys.stderr)
        return 1
    p = Path(argv[0])
    text, newline = read_text_preserve(p)
    write_text_preserve(p, convert_html_tables(text), newline)
    print(f"Done: {p}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_cli())
