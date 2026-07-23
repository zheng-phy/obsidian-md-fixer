from scripts.fixers.algorithm import fix, detect


def test_div_removed_and_anchors_to_code_block():
    md = '<div class="mineru-algorithm" style="white-space: pre-wrap;">\nAlgorithm 1 反演\nInput: $x$\n1. step one\n</div>'
    out = fix(md)
    assert "<div" not in out and "</div>" not in out
    assert "```" in out


def test_non_anchor_lines_return_to_prose():
    md = '<div class="mineru-algorithm">两阶段初始化 我们采用全谱段 $2500 \\sim 3800$ 拟合。</div>'
    out = fix(md)
    assert "<div" not in out
    assert "$2500 \\sim 3800$" in out
    assert "```" not in out


def test_formula_renders_after_unwrap():
    md = '<div class="mineru-algorithm">约束 $d \\in [1,50]$ 设置。</div>'
    out = fix(md)
    assert "$d \\in [1,50]$" in out and "<div" not in out


def test_normal_text_without_div_unchanged():
    assert fix("plain text") == "plain text"


def test_detect_reports_div():
    problems = detect('<div class="mineru-algorithm">Algorithm 1</div>')
    assert any("algorithm" in p.message.lower() for p in problems)


def test_detect_clean_without_div():
    assert detect("no div here") == []
