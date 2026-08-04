"""Flatten HTML tables with merged cells (rowspan/colspan) into Markdown.

Opt-in (default_on=False): MinerU's rowspan/colspan data can be mis-aligned,
so the output is a DRAFT — each flattened table carries a marker line above
it and a detect issue telling the user to verify against the PDF (平衡:
MoE稀疏门控 要求保守 vs 2021B 要求半成品可用)。

Header reconstruction: row-0 spans decide the header depth (rowspan covers
rows; a colspan-only group header like 表11 covers 2 rows). Multi-row header
cells are joined per column into compound names (deduped), duplicate column
names get a number, empty names become 列N.
"""

import re
from html.parser import HTMLParser

from scripts.fixers.base import Issue
from scripts.fixers.table import _render_markdown_table

_TABLE_RE = re.compile(r"<table>.*?</table>", re.DOTALL | re.IGNORECASE)
_MARKER = "<!-- auto-flattened from merged-cell table — verify against PDF -->"


class _SpanParser(HTMLParser):
    """Collect (text, rowspan, colspan) per cell, in document order."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list = []
        self._cur_row: list | None = None
        self._cur_cell: list | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._cur_row = []
        elif tag in ("td", "th") and self._cur_row is not None:
            a = dict(attrs)
            self._cur_cell = [a.get("rowspan", "1"), a.get("colspan", "1"), []]

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cur_cell is not None:
            rs = int(self._cur_cell[0] or "1")
            cs = int(self._cur_cell[1] or "1")
            self._cur_row.append(("".join(self._cur_cell[2]).strip(), rs, cs))
            self._cur_cell = None
        elif tag == "tr" and self._cur_row is not None:
            self.rows.append(self._cur_row)
            self._cur_row = None

    def handle_data(self, data):
        if self._cur_cell is not None:
            self._cur_cell[2].append(data)


def _expand_grid(rows: list) -> list:
    """Place cells into a rectangular grid: rowspan fills down, colspan right."""
    if not rows:
        return []
    width = sum(cs for _, _, cs in rows[0])
    grid: list = []
    r = 0
    for row in rows:
        while len(grid) < r + 1:
            grid.append([None] * width)
        c = 0
        for text, rs, cs in row:
            while c < width and grid[r][c] is not None:
                c += 1
            if c >= width:
                continue
            while len(grid) < r + rs:
                grid.append([None] * width)
            for rr in range(r, r + rs):
                for cc in range(c, c + cs):
                    grid[rr][cc] = text
            c += cs
        r += 1
    return [[cell if cell is not None else "" for cell in row] for row in grid]


def _header_rows(rows: list) -> int:
    """Header depth: rows covered by row-0 spans; colspan-group headers span 2."""
    if not rows:
        return 1
    max_row = max((rs for _, rs, _ in rows[0]), default=1)
    if max_row > 1:
        return max_row
    if any(cs > 1 for _, _, cs in rows[0]) and len(rows) > 1:
        row1 = rows[1]
        if all(rs == 1 and cs == 1 for _, rs, cs in row1):
            return 2
    return 1


def _column_names(grid: list, header_rows: int) -> list:
    names: list = []
    used: set = set()
    for c in range(len(grid[0])):
        parts: list = []
        prev = None
        for r in range(header_rows):
            t = grid[r][c].strip()
            if t and t != prev:
                parts.append(t)
            if t:
                prev = t
        name = " ".join(parts).strip()
        if not name:
            name = f"列{c + 1}"
        base = name
        n = 1
        while name in used:
            n += 1
            name = f"{base} ({n})"
        used.add(name)
        names.append(name)
    return names


def fix(text: str) -> str:
    """Replace every HTML <table> with a flattened Markdown table + marker."""

    def _replace(match: re.Match) -> str:
        parser = _SpanParser()
        parser.feed(match.group(0))
        grid = _expand_grid(parser.rows)
        if not grid:
            return match.group(0)
        names = _column_names(grid, _header_rows(parser.rows))
        return _MARKER + "\n" + _render_markdown_table([names] + grid[_header_rows(parser.rows):])

    return _TABLE_RE.sub(_replace, text)


def detect(text: str) -> list:
    """Report each flattened table as a draft needing PDF verification."""
    problems: list = []
    for m in _TABLE_RE.finditer(text):
        line = text[: m.start()].count("\n") + 1
        parser = _SpanParser()
        parser.feed(m.group(0))
        if _expand_grid(parser.rows):
            problems.append(Issue(
                "table_flatten",
                line,
                "flattened merged-cell table (draft) — verify against PDF",
            ))
    return problems


def _cli(argv=None) -> int:
    import sys
    from pathlib import Path

    from scripts.textio import read_text_preserve, write_text_preserve

    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print("usage: python -m scripts.fixers.table_flatten <file.md>", file=sys.stderr)
        return 1
    p = Path(argv[0])
    text, newline = read_text_preserve(p)
    write_text_preserve(p, fix(text), newline)
    print(f"Done: {p}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_cli())
