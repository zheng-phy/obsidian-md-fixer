---
name: obsidian-md-fixer
description: Use when a Markdown file converted from a PDF or Word document (especially by MinerU, but also pandoc/Marker/any converter) shows tables as raw HTML, chemical formulas like SiO2 unrendered, broken \( ... \) math delimiters causing ParseError, or images not displaying in Obsidian.
---

# Obsidian MD Fixer

## Overview

Repair Markdown files (already converted from PDF/Word by any tool) so tables,
formulas, and images render correctly in Obsidian. All mechanical fixes (HTML
tables, chemical-formula subscripts, math delimiters, image paths, verification)
run as deterministic Python fixers in `scripts/fixers/` — never hand-edit the
content. Semantic judgment (superscripts, sentence repair) is left to the agent,
driven by the verifier's line-numbered issue list.

## When to Use

- A converted Markdown's tables render as raw `<table>` HTML in Obsidian
- Chemical formulas (SiO2, C4, C6H12O6) not rendering as subscripts
- `\(...` math delimiters unpaired, causing Obsidian ParseError
- Images not displaying after conversion

## When NOT to Use

- Converting PDF/Word to Markdown itself — use MinerU / the mineru skill first
- Plain text extraction only
- LaTeX math outside tables not rendering — Obsidian/MathJax issue
- .tex compilation errors — LaTeX compiler issue

## Quick Reference

Run from the skill's root directory. Always `python -m`, never `python scripts/x.py`.

| Goal | Command |
|------|---------|
| Fix a Markdown file | `python -m scripts.postprocess <file.md>` |
| Run only some fixers | `python -m scripts.postprocess <file.md> --fixers table,images` |
| Skip a fixer | `python -m scripts.postprocess <file.md> --skip chem_formula` |
| Supply an image bundle | `python -m scripts.postprocess <file.md> --images-dir <dir>` |
| Run one fixer alone | `python -m scripts.fixers.<name> <file.md>` |

Fixers (in pipeline order): `table` → `chem_formula` → `math_delim` → `ocr_cleanup` → `algorithm` → `code_fence` → `images`.
Exit codes: 0 = success, 1 = failure (no output), 2 = output produced with verification warnings.

## Workflow

1. **Confirm input is `.md`.** Anything else (.pdf/.docx) is out of scope — tell the user to convert first.
2. **Choose fixers.** Default runs all. If the source is a physics/math-modeling document (superscripts like `Sv2` mean `Sv^2`), pass `--skip chem_formula` so subscript rules don't corrupt them.
3. **Run the fix command.** Output is `<name>_fixed.md` next to the original; the original is never overwritten. Use `--in-place` only if the user explicitly asks (a `.bak` backup is created first).
4. **Handle the exit code:**
   - 0 → report the output path.
   - 1 → report the error message verbatim; do not retry blindly.
   - 2 → report the output path AND list every verifier issue (each is `[fixer] line N: message`).
5. **Missing images.** If the verifier reports `missing image`, the fixer only rewrites paths — it cannot restore image files. Ask the user where the converter's image bundle is, then re-run with `--images-dir <dir>`. If there is no bundle, tell the user to re-convert with an image-producing tool (e.g. MinerU Standard API).
6. **Semantic issues stay for you.** Issues the fixers cannot resolve (superscripts like `Sv2`, sentence fragments) are yours to repair by reading the flagged lines — not by editing the scripts.
7. **User-reported structural misses.** When the user points out content MinerU downgraded to plain text:
   - **A table that didn't become a table (e.g. a three-line table)** — do NOT auto-convert; the column structure is already lost. Read the flagged text, understand which column is which, and hand-write the Markdown table yourself.
   - **A code block missing its fence** — run `--fixers code_fence`; it wraps only high-confidence code and reports ambiguous spots (`needs agent review`). After wrapping, fix any math mixed into the block or crammed single-line statements yourself.
8. **Report**: tell the user the `.md` and `images/` paths, and remind them to open the note in Obsidian to confirm tables, formulas, and images render. If the file is outside their vault, suggest moving the whole `<name>/` folder (md + images/) into it.

## Optional: Formula Semantic Review

After the main fix, you MAY offer a formula review — but only under these three hard rules:

1. **Explicit opt-in only.** Ask the user first; never run a full-document formula review by default. It is the most token-expensive step in this skill.
2. **Target systematic MinerU recognition patterns, not mathematical correctness.** Look for repeated error modes: `\times` misread as `x`, superscript/subscript swaps, broken `\frac`, misrecognized Greek letters. Do NOT try to prove a formula is academically correct (paper formulas are novel; there is no canonical form to compare against).
3. **Report only, never edit.** Output a list: suspicious formula + what you believe is correct + why. The user confirms each before any change is made.

## Common Mistakes

- Running `python scripts/postprocess.py` directly — it breaks package imports; always `python -m scripts.postprocess`.
- Hand-converting HTML tables or formulas instead of using the fixers — the fixers protect image paths, inline code, and URLs that manual edits corrupt.
- Overwriting the user's original Markdown — always produce `<name>_fixed.md` unless `--in-place` was explicitly requested.
- Letting `chem_formula` touch physics/modeling documents — pass `--skip chem_formula` when superscripts (Sv2, m3) carry meaning.
- Trying to convert PDF/Word here — this skill only repairs already-converted Markdown.
