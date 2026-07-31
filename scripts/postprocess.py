"""Main entry: fix an existing Markdown file for Obsidian rendering.

Usage:
    python -m scripts.postprocess paper.md [--fixers a,b] [--skip c] [--images-dir PATH] [--in-place]

Exit codes: 0 = success, 1 = failure (no output), 2 = success with warnings.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from scripts import verifier
from scripts.fixers import all_fixers, default_order, select
from scripts.textio import read_text_preserve, write_text_preserve


def _resolve_fixer_ids(fixers_arg: str | None, skip_arg: str | None) -> list:
    """Compute the ordered fixer id list from --fixers / --skip."""
    if fixers_arg:
        ids = [s.strip() for s in fixers_arg.split(",") if s.strip()]
    else:
        ids = default_order()
    if skip_arg:
        skip = {s.strip() for s in skip_arg.split(",") if s.strip()}
        ids = [i for i in ids if i not in skip]
    return [f.id for f in select(ids)]


_COLLAPSE_THRESHOLD = 15


def _write_issues_json(path: Path, issues: list) -> None:
    """Write structured verifier issues to a JSON file."""
    data = [
        {"fixer": issue.fixer, "line": issue.line, "message": issue.message}
        for issue in issues
    ]
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _format_issues(issues: list) -> list:
    """Format Issue objects for display; collapse a flooding fixer into a summary.

    Any single fixer producing more than _COLLAPSE_THRESHOLD issues is folded
    into one summary line (with a --skip hint) plus its first few examples, so a
    handful of real issues are not drowned out by a misfiring fixer.
    """
    from collections import defaultdict

    by_fixer: dict = defaultdict(list)
    for issue in issues:
        by_fixer[issue.fixer].append(issue)

    out: list = []
    for fixer, group in by_fixer.items():
        if len(group) > _COLLAPSE_THRESHOLD:
            out.append(
                f"[{fixer}] {len(group)} issues (showing 3) — "
                f"if these are mis-fires, consider --skip {fixer}"
            )
            out += [str(i) for i in group[:3]]
        else:
            out += [str(i) for i in group]
    return out


def process_markdown(md_path: Path, images_source_dir: Path | None, fixer_ids: list) -> list:
    """Run selected fixers in default order, then aggregate detect(). Returns problems."""
    md_path = Path(md_path)
    chosen = select(fixer_ids)

    text, newline = read_text_preserve(md_path)
    for fixer in chosen:
        if not fixer.file_based:
            text = fixer.run(text)
    write_text_preserve(md_path, text, newline)

    for fixer in chosen:
        if fixer.file_based:
            src = images_source_dir if images_source_dir is not None else md_path.parent / "images"
            fixer.run(md_path, src)

    return verifier.verify_issues(md_path, fixer_ids)


def _run_fix_mode(input_path: Path, in_place: bool, fixer_ids: list, images_dir: Path | None) -> tuple:
    """Fix an existing .md. Default writes <stem>_fixed.md; --in-place overwrites with .bak backup."""
    if in_place:
        target = input_path
        shutil.copy2(input_path, input_path.with_suffix(".md.bak"))
    else:
        target = input_path.with_name(input_path.stem + "_fixed.md")
        shutil.copy2(input_path, target)
    src = images_dir if images_dir is not None else input_path.parent / "images"
    problems = process_markdown(target, src, fixer_ids)
    return target, problems


def main(argv=None) -> int:
    """Run the pipeline. Exit codes: 0 = success, 1 = failure, 2 = warnings."""
    parser = argparse.ArgumentParser(description="Fix a Markdown file for Obsidian rendering.")
    parser.add_argument("input", type=Path, help="a .md file to fix")
    parser.add_argument("--fixers", default=None,
                        help="comma-separated fixer ids to run (default: all)")
    parser.add_argument("--skip", default=None,
                        help="comma-separated fixer ids to skip")
    parser.add_argument("--images-dir", type=Path, default=None,
                        help="source directory for images (default: <md_dir>/images)")
    parser.add_argument("--in-place", action="store_true",
                        help="overwrite the input file (a .bak backup is created)")
    parser.add_argument("--verify", action="store_true",
                        help="verify only: report issues, write nothing (exit 0=clean, 2=issues)")
    parser.add_argument("--dry-run", action="store_true",
                        help="run text fixers in memory and report changes without writing files")
    parser.add_argument("--issues-json", type=Path, default=None,
                        help="write structured issue list (JSON) to this path")
    args = parser.parse_args(argv)

    if not args.input.is_file():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        return 1

    if args.input.suffix.lower() != ".md":
        print(f"Error: unsupported input type '{args.input.suffix}', expected .md", file=sys.stderr)
        return 1

    fixer_ids = _resolve_fixer_ids(args.fixers, args.skip)

    if args.verify:
        problems = verifier.verify_issues(args.input, fixer_ids)
        if args.issues_json:
            _write_issues_json(args.issues_json, problems)
        if problems:
            print("Verification warnings:", file=sys.stderr)
            for problem in _format_issues(problems):
                print(f"  - {problem}", file=sys.stderr)
            return 2
        print(f"Clean: {args.input}")
        return 0

    if args.dry_run:
        text, _ = read_text_preserve(args.input)
        print("Dry run (no files written):")
        for fixer in select(fixer_ids):
            if fixer.file_based:
                continue
            updated = fixer.run(text)
            print(f"  [{fixer.id}] {'would modify' if updated != text else 'no change'}")
            text = updated
        if args.issues_json:
            _write_issues_json(
                args.issues_json, verifier.verify_issues(args.input, fixer_ids)
            )
        return 0

    target, problems = _run_fix_mode(args.input, args.in_place, fixer_ids, args.images_dir)
    if args.issues_json:
        _write_issues_json(args.issues_json, problems)
    print(f"Re-run: python -m scripts.postprocess {_rerun_args(args)}")

    if problems:
        print("Verification warnings:", file=sys.stderr)
        for problem in _format_issues(problems):
            print(f"  - {problem}", file=sys.stderr)
        print(f"Output: {target}")
        return 2

    print(f"Done: {target}")
    return 0


def _rerun_args(args) -> str:
    """Rebuild the CLI flags actually used, for a copy-paste re-run hint."""
    parts = [f'"{args.input}"']
    if args.fixers:
        parts += ["--fixers", args.fixers]
    if args.skip:
        parts += ["--skip", args.skip]
    if args.images_dir:
        parts += ["--images-dir", f'"{args.images_dir}"']
    if args.in_place:
        parts.append("--in-place")
    if args.issues_json:
        parts += ["--issues-json", f'"{args.issues_json}"']
    return " ".join(parts)


if __name__ == "__main__":
    sys.exit(main())
