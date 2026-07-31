"""Copy images next to the .md file and rewrite image references.

Images are COPIED (never moved) so the source directory stays intact.
External image URLs (http/https) are left unchanged.
"""

import re
import shutil
from pathlib import Path

from scripts.textio import read_text_preserve, write_text_preserve

_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^#{1,6}\s")


def organize(md_path: Path, source_images_dir: Path) -> None:
    """Copy images from source dir into <md_dir>/images/ and fix paths in the .md."""
    md_path = Path(md_path)
    source_images_dir = Path(source_images_dir)
    target_dir = md_path.parent / "images"

    if source_images_dir.is_dir() and source_images_dir.resolve() != target_dir.resolve():
        target_dir.mkdir(exist_ok=True)
        for img in source_images_dir.iterdir():
            if img.is_file():
                shutil.copy2(img, target_dir / img.name)

    text, newline = read_text_preserve(md_path)

    def _rewrite(match: re.Match) -> str:
        alt, path = match.group(1), match.group(2)
        if path.startswith(("http://", "https://")):
            return match.group(0)
        return f"![{alt}](images/{Path(path).name})"

    write_text_preserve(md_path, _MD_IMAGE_RE.sub(_rewrite, text), newline)


def detect(md_path: Path) -> list:
    """Report missing local images and images appearing before the first heading."""
    from scripts.fixers.base import Issue

    md_path = Path(md_path)
    lines = md_path.read_text(encoding="utf-8").splitlines()
    problems: list = []
    first_heading = next(
        (i for i, line in enumerate(lines, 1) if _HEADING_RE.match(line)), None
    )
    for i, line in enumerate(lines, 1):
        for match in _MD_IMAGE_RE.finditer(line):
            path = match.group(2)
            if not path.startswith(("http://", "https://")) and not (
                md_path.parent / path
            ).exists():
                problems.append(Issue("images", i, f"missing image: {path}"))
            if first_heading is not None and i < first_heading:
                problems.append(
                    Issue(
                        "images",
                        i,
                        "image appears before first heading "
                        f"(possible figure-caption misplacement): {path}",
                    )
                )
    return problems


def _cli(argv=None) -> int:
    import sys

    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print("usage: python -m scripts.fixers.images <file.md> [images_source_dir]", file=sys.stderr)
        return 1
    md = Path(argv[0])
    src = Path(argv[1]) if len(argv) > 1 else md.parent / "images"
    organize(md, src)
    print(f"Done: {md}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_cli())
