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
# Caption window: ±3 lines covers blank-line variants while keeping figures
# from cross-talking; detect-only, so err tight.
_CAPTION_WINDOW = 3
_CAPTION_EN_RE = re.compile(r"^\s*(?:Figure\s+\d+\s*[:.]|Fig\.?\s*\d+)")
_CAPTION_CN_RE = re.compile(r"^\s*图\s*\d+")
_CAPTION_CN_MAX_LEN = 40  # longer lines are prose mentions, not captions
# B196 "## 利润值/元": axis label mis-tagged as a heading.
_AXIS_HEADING_RE = re.compile(r"^#{1,6}\s*\S{1,12}/(元|秒|米|千克|个|件|%|kg|cm|mm|m|s)$")


def organize(md_path: Path, source_images_dir: Path, out_dir_name: str = "images") -> None:
    """Copy images from source dir into <md_dir>/<out_dir_name>/ and fix paths.

    out_dir_name is relative to the md (default "images"; K3 parses need
    "Image/"), and the reference rewrite uses the same name.
    """
    md_path = Path(md_path)
    source_images_dir = Path(source_images_dir)
    target_dir = md_path.parent / out_dir_name

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
        return f"![{alt}]({out_dir_name}/{Path(path).name})"

    write_text_preserve(md_path, _MD_IMAGE_RE.sub(_rewrite, text), newline)


def detect(md_path: Path) -> list:
    """Report image problems: missing, mis-placed, orphan/pairing, order.

    All detect-only; the agent decides how to fix figures.
    """
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
        if _AXIS_HEADING_RE.match(line):
            problems.append(
                Issue("images", i, "possible axis label mis-tagged as heading")
            )

    # Figure-caption pairing within ±3 lines (detect-only).
    image_lines = {i for i, line in enumerate(lines, 1) if _MD_IMAGE_RE.search(line)}
    caption_lines: dict = {}
    for i, line in enumerate(lines, 1):
        is_en = bool(_CAPTION_EN_RE.match(line))
        is_cn = bool(
            _CAPTION_CN_RE.match(line)
            and len(line) <= _CAPTION_CN_MAX_LEN
            and not line.rstrip().endswith("。")
        )
        if is_en or is_cn:
            num = re.search(r"\d+", line)
            if num:
                caption_lines[i] = int(num.group(0))

    for img in sorted(image_lines):
        if not any(abs(img - c) <= _CAPTION_WINDOW for c in caption_lines):
            problems.append(
                Issue(
                    "images",
                    img,
                    "image has no caption within ±3 lines "
                    "(possible orphan/misplaced figure)",
                )
            )
    paired_nums: list = []
    for c, num in sorted(caption_lines.items()):
        if any(abs(c - im) <= _CAPTION_WINDOW for im in image_lines):
            paired_nums.append(num)
        else:
            problems.append(
                Issue(
                    "images",
                    c,
                    "caption has no image within ±3 lines (possible orphan caption)",
                )
            )
    if any(b <= a for a, b in zip(paired_nums, paired_nums[1:])):
        problems.append(
            Issue(
                "images",
                0,
                "possible figure order anomaly (captions out of sequence) — verify visually",
            )
        )

    # Image bundle audit: files in <md_dir>/images/ that no reference uses.
    # Read-only; a flood of issues folds via the standard _format_issues
    # collapse in postprocess.
    referred: set = set()
    for line in lines:
        for match in _MD_IMAGE_RE.finditer(line):
            path = match.group(2)
            if not path.startswith(("http://", "https://")):
                referred.add(Path(path).name)
    bundle = md_path.parent / "images"
    if bundle.is_dir():
        for img in sorted(bundle.iterdir()):
            if img.is_file() and img.name not in referred:
                problems.append(
                    Issue(
                        "images",
                        0,
                        "unreferenced image in bundle (possible missing figure "
                        f"or formula fragment): {img.name}",
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
