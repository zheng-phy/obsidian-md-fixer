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
