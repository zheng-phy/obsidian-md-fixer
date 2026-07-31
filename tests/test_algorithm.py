from scripts.fixers.algorithm import fix, detect


def test_div_removed_and_anchors_to_code_block():
    # Input 含数学($x$):整个 run 转正文,公式恢复渲染(v2 行为)
    md = '<div class="mineru-algorithm" style="white-space: pre-wrap;">\nAlgorithm 1 反演\nInput: $x$\n1. step one\n</div>'
    out = fix(md)
    assert "<div" not in out and "</div>" not in out
    assert "```" not in out
    assert "$x$" in out


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


def test_math_mixed_anchor_run_stays_prose():
    # 含 $ 的锚点 run:不进围栏,原样正文(B157 公式恢复渲染)
    md = '<div class="mineru-algorithm">\nAlgorithm 1 反演\nInput: $d_0$\n1. step one\n</div>'
    out = fix(md)
    assert "```" not in out
    assert "$d_0$" in out


def test_pure_pseudocode_run_goes_to_single_fence():
    md = '<div class="mineru-algorithm">\nAlgorithm 1 合成\nInput: x\n1. step one\n2. step two\n</div>'
    out = fix(md)
    assert out.count("```") == 2  # 单块围栏


def test_foreach_and_continue_keep_run_connected():
    # Agent World 三段式:foreach/continue/end 行都是锚点,run 不断块
    md = (
        '<div class="mineru-algorithm">\nAlgorithm 1 训练\n'
        "for each epoch:\n    continue when converged\n"
        "end\n</div>"
    )
    out = fix(md)
    assert out.count("```") == 2  # 连续锚点 run 合成单块
    fenced = out.split("```")[1]
    for line in ("Algorithm 1 训练", "for each epoch:", "continue when converged", "end"):
        assert line in fenced


def test_new_anchor_keywords_recognized():
    # define/synthesize/require/ensure/else 均为锚点:进围栏,不落回正文
    md = (
        '<div class="mineru-algorithm">\nAlgorithm 2 生成\n'
        "define F(x):\n    synthesize output\n"
        "require x > 0\nensure output valid\n"
        "if a:\n    do A\nelse:\n    do B\n"
        "</div>"
    )
    out = fix(md)
    # do A/do B 是非锚点正文行,把 run 断成 2 块(主体 + else 单行块)
    assert out.count("```") == 4
    first_fence = out.split("```")[1]
    for line in ("Algorithm 2 生成", "define F(x):", "    synthesize output",
                 "require x > 0", "ensure output valid", "if a:"):
        assert line in first_fence
    assert "else:" in out.split("```")[3]
    assert "do A" not in first_fence
