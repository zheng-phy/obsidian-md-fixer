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


# --- \tag 缺陷(真实样本:2016国赛A题优秀论文,MinerU 公式编号区间误拼)---

def test_detect_tag_unbalanced_braces():
    # 真实缺陷:\tag{7)~(10} —— { 与 } 不配平
    problems = detect("\\tag{7)~(10}")
    assert any(p.fixer == "math_delim" and "tag" in p.message.lower() for p in problems)


def test_detect_tag_stray_paren():
    # 真实缺陷:\tag{3) \(\sim (6)\} —— \tag 花括号内混入游离 )
    problems = detect("\\tag{3) \\(3\\) x}")
    assert any("tag" in p.message.lower() for p in problems)


def test_detect_tag_bare_tilde():
    # 数学模式下裸 ~ 渲染为空格,公式编号区间断裂
    problems = detect("\\tag{7)~(10}")
    assert any("~" in p.message or "tilde" in p.message.lower() for p in problems)


def test_detect_tag_normal_ok():
    # 正常 \tag{N} 不报
    assert detect("\\tag{1}") == []
    assert detect("\\tag{26}") == []


def test_detect_downgraded_tilde():
    problems = detect("模型 X\\~B(n,p) 分布")
    hits = [p for p in problems if "downgraded" in p.message]
    assert len(hits) == 1


def test_detect_tilde_number_range_not_reported():
    # 1\~8 是中文区间,数字之间的 \~ 不报
    problems = detect("零件1\\~8 规格")
    assert not any("downgraded" in p.message for p in problems)


def test_detect_downgraded_inequality():
    problems = detect("满足 0<p<1 条件")
    hits = [p for p in problems if "downgraded" in p.message]
    assert len(hits) == 1


def test_detect_garbled_math_body():
    # K3 AttnRes 案:= 1 = 1 1(定界符配平但内容损坏)
    problems = detect("$= 1 = 1 1$ 异常")
    hits = [p for p in problems if "garbled" in p.message]
    assert len(hits) == 1


def test_detect_clean_math_not_reported():
    problems = detect("$x = y + 1$ 正常")
    assert not any("garbled" in p.message or "downgraded" in p.message for p in problems)
