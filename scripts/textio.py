"""Line-ending preserving text IO.

Path.write_text on Windows translates \\n to \\r\\n via the default text mode,
silently rewriting LF files (the historical root cause of B196 CRLF damage).
These helpers detect the file's newline style and write it back verbatim, so
fixing a file never changes its line endings.
"""

from pathlib import Path


def read_text_preserve(path) -> tuple[str, str]:
    """Return (text, newline); newline is the style seen in the first 8KB.

    Detection scans the raw bytes (not decoded text) so \\r\\n inside a
    multi-byte UTF-8 sequence cannot be misread.
    """
    raw = Path(path).read_bytes()
    newline = "\r\n" if b"\r\n" in raw[:8192] else "\n"
    return raw.decode("utf-8"), newline


def write_text_preserve(path, text, newline) -> None:
    """Write text using the given newline style, byte-exactly.

    Any \\r\\n or stray \\r already in text is normalized to \\n first, so a
    fixer that preserves trailing CRs cannot produce \\r\\r\\n on output.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(normalized.replace("\n", newline))
