---
name: obsidian-md-fixer
description: Use when a Markdown file converted from a PDF or Word document (especially by MinerU, but also pandoc/Marker/any converter) shows tables as raw HTML, broken \( ... \) math delimiters causing ParseError, code blocks missing their ``` fences or mislabeled, images missing or misplaced with orphan/out-of-order captions, OCR artifacts like U+FFFD or split words, or unreferenced image files — in Obsidian. Chemical subscripts (SiO2) are handled by an optional fixer.
---

# Obsidian MD Fixer

## Overview

Repair Markdown files (already converted from PDF/Word by any tool) so tables,
formulas, code, and images render correctly in Obsidian. All mechanical fixes
(HTML tables, math delimiters, OCR noise, image paths, URL joins, verification)
run as deterministic Python fixers in `scripts/fixers/` — never hand-edit the
content. Chemical-formula subscripts are an optional fixer, opt-in via
`--fixers chem_formula` for chemistry/materials documents. Semantic judgment
(superscripts, sentence repair, figure order) is left to the agent, driven by
the verifier's line-numbered issue list.

## When to Use

- A converted Markdown's tables render as raw `<table>` HTML in Obsidian
- `\(...` math delimiters unpaired, causing Obsidian ParseError; inline math downgraded to plain text (`X\~B(`, `0<p<1`)
- Code blocks missing their ``` fences, fenced code mislabeled (e.g. `prolog` for python) or fragmented
- Images not displaying, misplaced relative to their captions, captions out of order, or unreferenced image files in the bundle
- OCR artifacts: U+FFFD replacement chars (`�`), split words (dificulty), split URLs, garbled math bodies
- (Optional) Chemical formulas (SiO2, C6H12O6) not rendering as subscripts — needs `--fixers chem_formula`

## When NOT to Use

- Converting PDF/Word to Markdown itself — use MinerU / the mineru skill first
- Plain text extraction only
- LaTeX math outside tables not rendering — Obsidian/MathJax issue
- .tex compilation errors — LaTeX compiler issue

## Quick Reference

Run from the skill's root directory. Always `python -m`, never `python scripts/x.py`.

| Goal | Command |
|------|---------|
| Fix a Markdown file (default CS/AI/math/physics-safe) | `python -m scripts.postprocess <file.md>` |
| Run only some fixers | `python -m scripts.postprocess <file.md> --fixers table,images` |
| Enable chemical subscripts (chemistry/materials only) | `python -m scripts.postprocess <file.md> --fixers chem_formula` |
| Flatten merged-cell HTML tables (draft — verify!) | `python -m scripts.postprocess <file.md> --flatten-merged-tables` |
| Supply an image bundle | `python -m scripts.postprocess <file.md> --images-dir <dir>` |
| Name the image output dir | `python -m scripts.postprocess <file.md> --images-out-dir Image` |
| Run one fixer alone | `python -m scripts.fixers.<name> <file.md>` |

Fixers (in pipeline order): `table` → `table_flatten` (opt-in) → `chem_formula` (opt-in) → `math_delim` → `ocr_cleanup` → `algorithm` → `code_fence` → `url_join` → `images`.
Exit codes: 0 = success, 1 = failure (no output), 2 = output produced with verification warnings.

## Workflow

1. **Confirm input is `.md`.** Anything else (.pdf/.docx) is out of scope — tell the user to convert first.
2. **Run the default fix command.** The default set is already the safe configuration for CS/AI/math/physics papers — chemical subscripts are opt-in, so no `--skip` magic is needed. Output is `<name>_fixed.md` next to the original; the original is never overwritten. Use `--in-place` only if the user explicitly asks (a `.bak` backup is created first).
3. **Chemistry/materials documents.** If the verifier reports a chem-opportunity hint (`formula-like tokens ... --fixers chem_formula`) and the document is genuinely chemistry/materials, re-run with `--fixers chem_formula`. Then work through the `low-confidence wrap` list: each flagged `$X_N$` could be a variable subscript — compare with the original text and unwrap (restore the name) where it isn't a formula.
4. **Handle the exit code:**
   - 0 → report the output path (the fix summary printed per fixer is informational).
   - 1 → report the error message verbatim; do not retry blindly.
   - 2 → report the output path AND list every verifier issue (each is `[fixer] line N: message`).
5. **Missing images.** If the verifier reports `missing image`, the fixer only rewrites paths — it cannot restore image files. Ask the user where the converter's image bundle is, then re-run with `--images-dir <dir>` (use `--images-out-dir <name>` if the vault needs a different folder name). If there is no bundle, tell the user to re-convert with an image-producing tool (e.g. MinerU Standard API).
6. **U+FFFD (lost glyph) — restore it yourself, no auto-fix.** The verifier reports each `�` line. On real MinerU output the `content_list_v2.json` loses the same glyphs as the md (verified 0% mechanical restore), so there is no script shortcut. Two recovery paths, in order of reliability:
   - **Cross-check the PDF text layer** (e.g. `pdftotext` / PyMuPDF extract, then read the symbol at the matching position) — this is what actually recovered Agent World's 70 chars.
   - **Infer from context** — the content_list's `equation_inline` structure shows where math symbols belong (e.g. "contains �=128" + the formula `$N$` nearby → the glyph is `N`). Confirm against the PDF before editing.
   Never guess a glyph you cannot confirm.
7. **Image audit.** For `unreferenced image in bundle` and figure-caption pairing/order issues: the verifier can only flag mechanical signals. Read the actual image files to verify figure order visually, then move image references next to their captions / delete or re-integrate unreferenced files — as the document demands. If the MinerU output has a `layout.json`, cross-check the image order against it (B026 实证: page layout order can differ from the md insertion order).
8. **Semantic issues stay for you.** Issues the fixers cannot resolve are yours to repair by reading the flagged lines — not by editing the scripts:
   - `U+FFFD` (lost glyph) → restore the character from the PDF (see step 6); `control char U+00XX` → delete the stray control byte.
   - `URL split across lines` → join the continuation into the URL if the token is clearly its tail; leave prose that merely starts with a number.
   - `inline math downgraded to text` (`X\~B(`, `0<p<1`) → wrap in `$...$`; do NOT wrap digit ranges like `1\~8` (Chinese ranges are prose).
   - `garbled math body` / `space-separated numbers` (`X_{1 16}`) → compare with the PDF and repair the formula body.
   - `suspicious word form` (`wtih`) / `possible same identifier` (`k t h \_ excluding`) → fix the spelling/join manually; these are detect-only on purpose.
   - Superscripts like `Sv2`, sentence fragments, `??` OCR placeholders.
9. **User-reported structural misses.** When the user points out content MinerU downgraded to plain text:
   - **A table that didn't become a table (e.g. a three-line table)** — do NOT auto-convert; the column structure is already lost. Read the flagged text, understand which column is which, and hand-write the Markdown table yourself.
   - **A table kept as HTML (merged cells)** — the issue message notes `$...$` inside HTML tables does not render in Obsidian. Either flatten it by hand (compound header names, fill spans down), or offer `--flatten-merged-tables` for a machine draft — but every flattened table carries a "verify against PDF" marker, so check the spans against the PDF before trusting it.
   - **A code block missing its fence** — run `--fixers code_fence`; it wraps only high-confidence code and reports ambiguous spots (`needs agent review`). After wrapping, fix any math mixed into the block or crammed single-line statements yourself.
10. **Report**: tell the user the `.md` and `images/` paths, and remind them to open the note in Obsidian to confirm tables, formulas, and images render. If the file is outside their vault, suggest moving the whole `<name>/` folder (md + images/) into it.

## Optional: Formula Semantic Review

After the main fix, you MAY offer a formula review — but only under these three hard rules:

1. **Explicit opt-in only.** Ask the user first; never run a full-document formula review by default. It is the most token-expensive step in this skill.
2. **Target systematic MinerU recognition patterns, not mathematical correctness.** Look for repeated error modes: `\times` misread as `x`, superscript/subscript swaps, broken `\frac`, misrecognized Greek letters. Do NOT try to prove a formula is academically correct (paper formulas are novel; there is no canonical form to compare against).
3. **Report only, never edit.** Output a list: suspicious formula + what you believe is correct + why. The user confirms each before any change is made.

## Common Mistakes

- Running `python scripts/postprocess.py` directly — it breaks package imports; always `python -m scripts.postprocess`.
- On Windows, running `python3` — the Microsoft Store alias often points to a stub; use `python`.
- Hand-converting HTML tables or formulas instead of using the fixers — the fixers protect image paths, inline code, and URLs that manual edits corrupt.
- Overwriting the user's original Markdown — always produce `<name>_fixed.md` unless `--in-place` was explicitly requested.
- Still passing `--skip chem_formula` out of habit — since v2.0.0 chem_formula is opt-in and absent from the default set; `--skip` is a harmless no-op. Use `--fixers chem_formula` only for chemistry/materials documents.
- Ignoring the `low-confidence wrap` list after running chem_formula — those `$X_N$` wraps may be variable subscripts; verify each against the original text and unwrap the false ones.
- Wrapping Chinese digit ranges (`1\~8`) as math when fixing downgraded inline formulas — they are prose.
- Thinking sub-figure assembly (stitching cropped subplots into one figure) is this skill's job — it is not; do it by hand (e.g. PIL) if the user asks.
- Trying to convert PDF/Word here — this skill only repairs already-converted Markdown.
