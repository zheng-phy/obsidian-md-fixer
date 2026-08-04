import json

from scripts.fixers.fffd_restore import run, detect, restore_text, _extract_fragments


def _flat_paragraph(pieces):
    return [
        {"type": "paragraph", "content": {"paragraph_content": pieces}},
    ]


def test_restore_unique_alignment(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("contains \ufffd=128 tokens", encoding="utf-8")
    cl = tmp_path / "cl.json"
    cl.write_text(
        json.dumps(_flat_paragraph([
            {"type": "text", "content": "contains "},
            {"type": "equation_inline", "content": "$N$"},
            {"type": "text", "content": "=128 tokens"},
        ])),
        encoding="utf-8",
    )
    residuals = run(md, cl)
    assert residuals == []
    assert md.read_text(encoding="utf-8") == "contains $N$=128 tokens"


def test_restore_gap_is_a_fragment_run(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("v = \ufffd + 1", encoding="utf-8")
    cl = tmp_path / "cl.json"
    cl.write_text(
        json.dumps(_flat_paragraph([{"type": "text", "content": "v = $\\pi$ + 1"}])),
        encoding="utf-8",
    )
    residuals = run(md, cl)
    assert residuals == []
    assert md.read_text(encoding="utf-8") == "v = $\\pi$ + 1"


def test_ambiguous_alignment_left_untouched(tmp_path):
    # "x � y" 可对齐到片段 A(x a y)也可对齐到片段 B(x b y):≥2 候选 → 保留 + 报残留
    md = tmp_path / "p.md"
    md.write_text("x \ufffd y", encoding="utf-8")
    cl = tmp_path / "cl.json"
    cl.write_text(
        json.dumps([
            {"type": "paragraph", "content": {"paragraph_content": [
                {"type": "text", "content": "x a y"}]}},
            {"type": "paragraph", "content": {"paragraph_content": [
                {"type": "text", "content": "x b y"}]}},
        ]),
        encoding="utf-8",
    )
    residuals = run(md, cl)
    assert residuals == [1]
    assert md.read_text(encoding="utf-8") == "x \ufffd y"


def test_intra_fragment_ambiguity_left_untouched(tmp_path):
    # 同一片段内两种对齐(第一个 � 可以是 "x" 或 "xb")→ 不还原
    md = tmp_path / "p.md"
    md.write_text("a \ufffd b \ufffd", encoding="utf-8")
    cl = tmp_path / "cl.json"
    cl.write_text(
        json.dumps(_flat_paragraph([{"type": "text", "content": "a x b b x"}])),
        encoding="utf-8",
    )
    residuals = run(md, cl)
    assert residuals == [1]
    assert md.read_text(encoding="utf-8") == "a \ufffd b \ufffd"


def test_no_candidate_left_untouched(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("完全不同的 \ufffd 内容", encoding="utf-8")
    cl = tmp_path / "cl.json"
    cl.write_text(json.dumps(_flat_paragraph([{"type": "text", "content": "unrelated content"}])), encoding="utf-8")
    residuals = run(md, cl)
    assert residuals == [1]
    assert md.read_text(encoding="utf-8") == "完全不同的 \ufffd 内容"


def test_fragment_fffd_noop_alignment(tmp_path):
    # 片段同位置也有 U+FFFD:对齐成立但无可回填,行保留(不算残留)
    md = tmp_path / "p.md"
    md.write_text("a \ufffd b", encoding="utf-8")
    cl = tmp_path / "cl.json"
    cl.write_text(json.dumps(_flat_paragraph([{"type": "text", "content": "a \ufffd b"}])), encoding="utf-8")
    residuals = run(md, cl)
    assert residuals == []
    assert md.read_text(encoding="utf-8") == "a \ufffd b"


def test_paginated_structure_supported(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("each token activates \ufffd experts", encoding="utf-8")
    cl = tmp_path / "cl.json"
    cl.write_text(
        json.dumps([[{"type": "paragraph", "content": {"paragraph_content": [
            {"type": "text", "content": "each token activates $N_{Z}$ experts"},
        ]}}]]),
        encoding="utf-8",
    )
    residuals = run(md, cl)
    assert residuals == []
    assert md.read_text(encoding="utf-8") == "each token activates $N_{Z}$ experts"


def test_multiple_fffd_per_line(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("a\ufffdb\ufffdc", encoding="utf-8")
    cl = tmp_path / "cl.json"
    cl.write_text(json.dumps(_flat_paragraph([{"type": "text", "content": "aXYbZc"}])), encoding="utf-8")
    residuals = run(md, cl)
    assert residuals == []
    assert md.read_text(encoding="utf-8") == "aXYbZc"


def test_detect_hint_without_content_list(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("有 \ufffd 符号\n干净行", encoding="utf-8")
    problems = detect(md)
    assert len(problems) == 1
    assert "1 line(s) contain U+FFFD" in problems[0].message
    assert "--content-list" in problems[0].message


def test_detect_clean_when_no_fffd(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("干净文本", encoding="utf-8")
    assert detect(md) == []


def test_restore_text_counts_fffd_lines(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("line1\ufffd\nline2\ufffd\nline3", encoding="utf-8")
    cl = tmp_path / "cl.json"
    cl.write_text(
        json.dumps([
            {"type": "paragraph", "content": {"paragraph_content": [
                {"type": "text", "content": "line1ok"}]}},
            {"type": "paragraph", "content": {"paragraph_content": [
                {"type": "text", "content": "line2ok"}]}},
        ]),
        encoding="utf-8",
    )
    residuals = run(md, cl)
    assert residuals == []
    assert md.read_text(encoding="utf-8") == "line1ok\nline2ok\nline3"


def test_extract_fragments_title_and_equations():
    data = [
        {"type": "title", "content": {"title_content": [
            {"type": "text", "content": "Title"}]}},
        {"type": "paragraph", "content": {"paragraph_content": [
            {"type": "equation_inline", "content": "$x$"},
            {"type": "text", "content": "body"}]}},
        {"type": "image", "content": {}},  # 非 text/equation 片段忽略
    ]
    # 段落内 pieces 拼接为一条片段
    assert _extract_fragments(data) == ["Title", "$x$body"]
