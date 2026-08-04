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


# --- \[...\] 显示公式(本地增量入库:T1 24 处 / T2 回归 fixture)---

def test_display_bracket_converted():
    assert "$$x=1$$" in fix("\\[\nx=1\n\\]")


def test_display_bracket_multiple_blocks():
    out = fix("\\[\na=1\n\\]\n正文\n\\[\nb=2\n\\]")
    assert out.count("$$") == 4 and "\\[" not in out


def test_display_bracket_inline_converted():
    assert "$$x=1$$" in fix("\\[x=1\\]")


def test_display_bracket_in_code_untouched():
    text = "```\n\\[x\\]\n```"
    assert fix(text) == text


def test_display_bracket_inside_math_untouched():
    text = "$\\[x\\]$"
    assert fix(text) == text


def test_display_bracket_inline_math_untouched():
    text = "正文 $x$ 与 $\\[y\\]$"
    assert fix(text) == text


def test_detect_residual_display_bracket():
    problems = detect("开头 \\[\n未闭合\n")
    hits = [p for p in problems if "\\[" in p.message]
    assert len(hits) == 1


def test_detect_no_residual_after_conversion():
    problems = detect("\\[\na=1\n\\]")
    assert not any("\\[" in p.message or "\\]" in p.message for p in problems)


# --- garbled 误报:剔除下标/上标花括号内的 = (MoE稀疏门控 6 条误报)---

def test_garbled_ignores_equals_in_subscripts():
    # MoE稀疏门控 6 条误报:\sum_{i = 1}^{n} = x 曾数出 4 个 "="
    problems = detect("$\\sum_{i = 1}^{n} = x$ 正常")
    assert not any("garbled" in p.message for p in problems)


def test_garbled_ignores_equals_in_superscripts():
    problems = detect("$x^{a = b} + y = z$ 正常")
    assert not any("garbled" in p.message for p in problems)


def test_garbled_still_reported_for_true_garbled():
    # K3 真乱码 = 1 = 1 1 仍报
    problems = detect("$= 1 = 1 1$ 异常")
    hits = [p for p in problems if "garbled" in p.message]
    assert len(hits) == 1


def test_garbled_ignores_spaced_subsup_braces():
    # MinerU 原始输出是 _ { i = 1 }(^/_ 与 { 之间有空格),直接 --verify 未规范化
    # 文件时也应豁免下标内的 "="——检测不依赖 ocr_cleanup 先跑。
    problems = detect("$$\ny _ { H } = \\sum _ { i = 1 } ^ { n } G ( x )\n$$")
    assert not any("garbled" in p.message for p in problems)


# --- 数字区间 \~ -> ~(2021B:36%\~41% 实样)---

def test_tilde_number_range_percent_fixed():
    assert fix("选择性在 36%\\~41% 之间") == "选择性在 36%~41% 之间"


def test_tilde_between_digits_fixed():
    assert fix("零件1\\~8 规格") == "零件1~8 规格"


def test_tilde_letter_context_untouched():
    # 字母语境 X\~B(n,p) 是降级数学,不动,detect 照报
    text = "模型 X\\~B(n,p) 分布"
    assert fix(text) == text
    problems = detect(text)
    assert any("downgraded" in p.message for p in problems)


def test_tilde_fixed_range_not_reported():
    assert not any("downgraded" in p.message for p in detect("选择性在 36%~41% 之间"))


def test_tilde_inside_lparen_math_untouched():
    # \(...\) 转成 $...$ 后,数字区间 \~ 已先转成 ~(MathJax 中 \~ 非法,~ 为间隔)
    assert fix("\\(1\\~8\\)") == "$1~8$"
    # 字母语境不受影响
    assert fix("\\(X\\~B(n,p)\\)") == "$X\\~B(n,p)$"
