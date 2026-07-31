"""Shared fixer protocol and protected-zone splitting.

Every fixer operates on Markdown text but must never corrupt protected zones
(code blocks, inline code, existing math, <eq> tags, images, links, URLs, HTML
tags). `split_zones` is the single tokenizer all text fixers reuse.
"""

import re
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Issue:
    """A problem a fixer's detect() found, located for agent-driven semantic fixes."""

    fixer: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"[{self.fixer}] line {self.line}: {self.message}"


@dataclass
class Fixer:
    """One deterministic repair tool. file_based=True means it needs the filesystem.

    default_on=False marks opt-in fixers (run only when explicitly requested
    via --fixers); they stay registered and selectable.
    """

    id: str
    description: str
    file_based: bool
    run: Callable
    detect: Callable[[Any], list]
    default_on: bool = True


_ZONE_RE = re.compile(
    r"(?P<code_block>```.*?```)"
    r"|(?P<inline_code>`[^`\n]+`)"
    r"|(?P<math>\$\$.*?\$\$|\$[^$\n]+\$)"
    r"|(?P<eq><eq>.*?</eq>)"
    r"|(?P<image>!\[\[[^\]]*\]\]|!\[[^\]]*\]\([^)]*\))"
    r"|(?P<link>\[[^\]]*\]\([^)]*\))"
    r"|(?P<url>https?://[^\s)>]+)"
    r"|(?P<html><[^>]+>)",
    re.DOTALL,
)


def split_zones(text: str) -> list[tuple[str, str]]:
    """Split text into (kind, segment) pairs. Gaps between zones are 'text'."""
    segs: list[tuple[str, str]] = []
    pos = 0
    for m in _ZONE_RE.finditer(text):
        if m.start() > pos:
            segs.append(("text", text[pos : m.start()]))
        segs.append((m.lastgroup, m.group(0)))
        pos = m.end()
    if pos < len(text):
        segs.append(("text", text[pos:]))
    return segs
