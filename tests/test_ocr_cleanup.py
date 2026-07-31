from scripts.fixers.ocr_cleanup import fix, detect


def test_mathrm_letter_spaces_removed():
    assert fix("$\\mathrm { d r a f t }$") == "$\\mathrm{draft}$"


def test_whitelist_commands_only():
    assert fix("$\\text { v e r i f y }$") == "$\\text{verify}$"
    # 非白名单命令(\frac)不动
    assert fix("$\\frac { 1 } { 2 }$") == "$\\frac { 1 } { 2 }$"


def test_f_backslash_star_fixed():
    assert fix("$f^{\\backslash *}$") == "$f^{*}$"


def test_digit_split_in_math():
    assert fix("$0. 2 0$ and $1. 3 \\times 1 0 ^{- 4}$") == "$0.20$ and $1.3 \\times 10^{-4}$"


def test_digit_split_not_in_prose():
    assert fix("第 2 章共 3 节") == "第 2 章共 3 节"


def test_html_entity_decoded():
    assert fix("a &gt; b and &lt;tag&gt; &amp; &quot;x&quot;") == "a > b and <tag> & \"x\""


def test_code_block_untouched():
    assert fix("`0. 2 0` code") == "`0. 2 0` code"


def test_detect_greek_placeholder():
    problems = detect("期望接受长度 $\\tau$ 变成 ?? 占位")
    assert any("??" in p.message or "OCR" in p.message for p in problems)


def test_detect_clean_when_no_issue():
    assert detect("clean $0.20$ text") == []


def test_html_entity_decoded_in_math():
    # B157:$\tilde{\nu} &gt; 3300$
    assert fix("$\\tilde{\\nu} &gt; 3300$") == "$\\tilde{\\nu} > 3300$"
    assert fix("$a &lt; b$") == "$a < b$"


def test_html_entity_in_text_still_works():
    # text 段既有实体替换行为保持
    assert fix("a &gt; b") == "a > b"


def test_fstar_variants_all_fixed():
    assert fix("$f^{\\backslash *}$") == "$f^{*}$"
    assert fix("$f^{\\backslash^ {*}}$") == "$f^{*}$"


def test_fstar_backslash_a_not_touched():
    # f^{\backslash a} 不是 f-star 形态,不误伤
    assert fix("$f^{\\backslash a}$") == "$f^{\\backslash a}$"


def test_tuple_subscript_left_alone():
    # B196:X_{1 16} 是两个完整整数并列(可能元组),不静默合并
    assert fix("$X_{1 16}$") == "$X_{1 16}$"


def test_sign_digit_subscript_still_merged():
    assert fix("$10^{- 4}$") == "$10^{-4}$"


def test_decimal_digit_split_still_merged():
    assert fix("$0. 2 0$") == "$0.20$"


def test_detect_tuple_subscript():
    problems = detect("$X_{1 16}$ 与 $Y_{5 6}$")
    hits = [p for p in problems if "space-separated numbers" in p.message]
    assert len(hits) == 2
    assert all(p.line == 1 for p in hits)


def test_detect_no_tuple_on_single_digit():
    problems = detect("$X_{1 16}$ 正常 $Z_{1}$")
    hits = [p for p in problems if "space-separated numbers" in p.message]
    assert len(hits) == 1  # 只有 X_{1 16} 报


def test_letter_run_5_merged_in_math():
    # B196:a l l o w e d -> allowed
    assert fix("$a l l o w e d$") == "$allowed$"


def test_letter_run_2_left_alone():
    # x y 变量对常见,2 字母并跑不动
    assert fix("$x y$") == "$x y$"


def test_letter_run_3_4_reported_not_fixed():
    text = "$a b c$"
    assert fix(text) == text
    problems = detect(text)
    assert any("letter-run" in p.message for p in problems)


def test_letter_run_detect_skips_five_plus():
    # 5+ 由 fix 合并,detect 不报(3-4 才报)
    assert not any("letter-run" in p.message for p in detect("$a b c d e$"))
