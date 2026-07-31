from scripts.fixers.code_fence import fix, detect


def test_high_confidence_block_wrapped():
    md = "正文。\nimport numpy as np\ndef f(x):\n    return x\n后续。"
    out = fix(md)
    assert "```python" in out
    assert "import numpy as np" in out


def test_single_anchor_line_not_wrapped_but_reported():
    # 孤立单锚点行:不包块,但 detect 上报
    md = "用 print(x) 输出结果即可。"
    out = fix(md)
    assert "```" not in out


def test_anchor_with_math_not_wrapped_but_reported():
    # 锚点行混入 $...$:不包块,detect 上报(像 B311 的 def equation)
    md = 'def equation(x): return $(110 + x)$\nprint(x)'
    out = fix(md)
    assert "```" not in out
    problems = detect(md)
    assert any("code" in p.message.lower() for p in problems)


def test_anchor_with_chinese_not_wrapped():
    # 正文提及代码(中文句子)不包块
    md = "我们用 import 语句导入库,然后用 def 定义函数。"
    assert "```" not in fix(md)


def test_normal_prose_unchanged():
    md = "这只是一段普通中文说明,没有代码。"
    assert fix(md) == md


def test_detect_reports_suspected_block():
    md = "import numpy as np\nx = 1"
    problems = detect(md)
    assert any("code" in p.message.lower() for p in problems)


def test_detect_clean_on_plain_prose():
    assert detect("plain prose, nothing code-like") == []


def test_fix_does_not_touch_fenced_code():
    # B196/B157 回归:已有围栏内容必须零改动
    text = "正文\n```python\nimport os\ndef f(x):\n    return x\n```\n结尾\n"
    assert fix(text) == text


def test_fix_still_wraps_unfenced_code():
    text = "正文\nimport os\ndef f(x):\n    return x\n结尾\n"
    out = fix(text)
    assert "```python" in out and out.count("```") == 2


def test_detect_silent_on_fenced_anchors():
    # B157:277 条误报清零
    text = "```python\nimport os\ndef f(x):\n    return x\n```\n"
    assert detect(text) == []


def test_unclosed_fence_treated_as_fenced():
    # 未闭合围栏:其后所有行保守视为 fenced,不包不报
    text = "```python\nimport os\ndef f(x):\n    return x\n"
    assert fix(text) == text and detect(text) == []


def test_fence_state_resets_for_following_code():
    # 围栏之后的无围栏代码仍可被包(状态正确复位)
    text = "```python\nx = 1\n```\nimport os\ndef f(x):\n    return x\n"
    out = fix(text)
    assert out.count("```") == 4  # 原围栏 2 个 + 新包 2 个


def test_detect_line_numbers_across_fences():
    # detect 行号跨围栏仍正确
    text = "```python\nimport os\n```\n正文\ndef f(x):\n    return x\n"
    problems = detect(text)
    assert any(p.line == 5 for p in problems)


def test_detect_wrong_language_label():
    # K3 解析形态:prolog 标签 + python 内容
    text = "```prolog\nimport numpy as np\ndef f(x):\n    return x\n```\n"
    problems = detect(text)
    assert any("prolog" in p.message and "python" in p.message for p in problems)


def test_detect_fragmented_fences():
    text = "```python\nimport os\n```\n\n\n```python\nimport sys\n```\n"
    problems = detect(text)
    assert any("fragmented" in p.message for p in problems)


def test_detect_fragmented_fences_zero_gap():
    text = "```python\nimport os\n```\n```python\nimport sys\n```\n"
    problems = detect(text)
    assert any("fragmented" in p.message for p in problems)


def test_detect_no_indentation_loss():
    # 8 行内容、含 def/if/for、全部行首无缩进
    text = "```python\ndef f():\nif x:\nfor i in range(3):\nprint(i)\nx = 1\ny = 2\nz = 3\nw = 4\n```\n"
    problems = detect(text)
    assert any("no indentation" in p.message for p in problems)


def test_detect_normal_python_block_no_structure_issues():
    text = "```python\nimport os\ndef f(x):\n    return x\n```\n"
    problems = detect(text)
    assert not any(
        "labeled" in p.message or "fragmented" in p.message or "no indentation" in p.message
        for p in problems
    )
