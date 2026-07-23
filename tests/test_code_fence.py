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
