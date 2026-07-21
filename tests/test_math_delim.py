from scripts.fixers.math_delim import fix, detect


def test_eq_tag_becomes_inline_math():
    assert fix("<eq>a+b=c</eq>") == "$a+b=c$"


def test_broken_lparen_degraded_to_text():
    # \( ... 无配对 \) 的 OMML 碎片 → 去定界符,降级为纯文本,杜绝 ParseError
    assert fix("v为风速\\(m/s)和F=0.625×Sv2") == "v为风速(m/s)和F=0.625×Sv2"


def test_paired_lparen_converted_to_dollar():
    assert fix("公式 \\(E=mc^2\\) 完") == "公式 $E=mc^2$ 完"


def test_dollar_math_untouched():
    assert fix("keep $x^2$ as is") == "keep $x^2$ as is"


def test_detect_reports_broken_lparen():
    problems = detect("v为风速\\(m/s)")
    assert any(p.fixer == "math_delim" and "\\(" in p.message for p in problems)


def test_detect_reports_eq_tag():
    problems = detect("<eq>a+b</eq>")
    assert any(p.fixer == "math_delim" and "eq" in p.message.lower() for p in problems)
