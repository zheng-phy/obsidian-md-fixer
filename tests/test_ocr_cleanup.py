import pytest

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


def test_detect_fffd_reported_once_per_line():
    problems = detect("第一行\n这里有�字�符\n结尾")
    hits = [p for p in problems if "U+FFFD" in p.message]
    assert len(hits) == 1 and hits[0].line == 2  # 同行多处报一条


def test_detect_fffd_once_across_zones_on_same_line():
    # 同行跨 text/math 段仍只报一条(全文行级去重)
    problems = detect("(�) 与 $x�y$ 同行")
    hits = [p for p in problems if "U+FFFD" in p.message]
    assert len(hits) == 1 and hits[0].line == 1


def test_detect_control_char_reported():
    problems = detect("第一行\n退格\x08字符\n结尾")
    hits = [p for p in problems if "control char" in p.message]
    assert len(hits) == 1 and hits[0].line == 2
    assert "U+0008" in hits[0].message


def test_detect_clean_text_no_char_issues():
    problems = detect("干净文本 $x_{1}$ 正常")
    assert not any("U+FFFD" in p.message or "control char" in p.message for p in problems)


def test_detect_fffd_skipped_in_code_fence():
    text = "```python\nx = '�'\n```\n正文 �"
    problems = detect(text)
    hits = [p for p in problems if "U+FFFD" in p.message]
    assert len(hits) == 1 and hits[0].line == 4  # 只有正文行 4,code 段内不报


@pytest.mark.parametrize(
    "bad,good",
    [
        ("dificult", "difficult"),
        ("dificulty", "difficulty"),
        ("dificulties", "difficulties"),
        ("efect", "effect"),
        ("efective", "effective"),
        ("efectively", "effectively"),
        ("efectiveness", "effectiveness"),
        ("eficiency", "efficiency"),
        ("eficient", "efficient"),
        ("ofline", "offline"),
        ("ofers", "offers"),
        ("ofer", "offer"),
        ("ofce", "office"),
        ("diferent", "different"),
        ("diference", "difference"),
        ("efort", "effort"),
        ("aect", "affect"),
        ("afected", "affected"),
        ("eect", "effect"),
        ("specication", "specification"),
        ("conguration", "configuration"),
        ("proling", "profiling"),
        ("efects", "effects"),
        ("eects", "effects"),
    ],
)
def test_ligature_dict_entries(bad, good):
    assert fix(f"the {bad} here") == f"the {good} here"


def test_ligature_capitalized_fixed():
    # 大写变体:Dificult/Eficient 首字母大写同样修复,保留大写
    assert fix("Eficient method") == "Efficient method"
    assert fix("Dificult to say") == "Difficult to say"


def test_ligature_ofer_capitalized_untouched():
    # 专名风险条目豁免大写:人名 Ofer 不得改,小写 ofer 照常修
    assert fix("Ofer and Smith") == "Ofer and Smith"
    assert fix("ofer help") == "offer help"


def test_ligature_correct_word_untouched():
    assert fix("very effective offline profiling") == "very effective offline profiling"


def test_ligature_capitalized_untouched_when_unknown():
    # 词典外的大写形式(DificulT 之类)不碰
    assert fix("DificulT to say") == "DificulT to say"


def test_ligature_not_in_code_fence():
    assert fix("```\ndificult\n```") == "```\ndificult\n```"


def test_ligature_not_in_math():
    assert fix("$dificult$") == "$dificult$"


def test_ligature_word_boundary_respected():
    # efecitve 的变体不在词典内;"effect" 内嵌 "eect"?无。词界保证不误伤子串
    assert fix("an effect of x") == "an effect of x"


# --- array 列说明符豁免(MoE稀疏门控:r l r 误报/误合并)---

def test_array_decl_format_string_untouched_by_fix():
    # 5 列格式串本会被 5+ letter-run 合并成 "r l r l r" -> "rlrlr",现在豁免
    text = "$\\begin{array}{r l r l r}$"
    assert fix(text) == text


def test_array_decl_no_detect_issue():
    problems = detect("$\\begin{array}{r l r}$")
    assert not any("letter-run" in p.message for p in problems)


def test_array_decl_other_runs_still_handled():
    # 豁免只覆盖格式串;公式其余部分的 letter-run 照常合并
    assert fix("$\\begin{array}{c} a l l o w e d \\end{array}$") == "$\\begin{array}{c} allowed \\end{array}$"


def test_array_decl_other_runs_still_detected():
    problems = detect("$\\begin{array}{c} a b c \\end{array}$")
    assert any("letter-run" in p.message for p in problems)


# --- C0 控制字符自动清除(B026 U+000B 来自 \vdots 转义损坏)---

def test_control_char_removed_in_text():
    assert fix("退格\x08字符") == "退格字符"
    assert fix("垂直制表\x0b符") == "垂直制表符"


def test_control_char_removed_in_math():
    assert fix("$a\x0bb$") == "$ab$"


def test_control_char_kept_in_code_fence():
    text = "```\na\x0bb\n```"
    assert fix(text) == text


def test_control_char_kept_in_inline_code():
    text = "`a\x0bb`"
    assert fix(text) == text


def test_detect_still_reports_control_in_code_fence():
    # 修不到 code 区,detect 兜底照报
    problems = detect("```\n\x0b\n```")
    hits = [p for p in problems if "control char" in p.message]
    assert len(hits) == 1


def test_detect_clean_after_fix():
    problems = detect(fix("正文\x0b字符 $a\x08b$"))
    assert not any("control char" in p.message for p in problems)


# --- 正文错形小词典(detect-only,MoE稀疏门控 实证)---

@pytest.mark.parametrize(
    "bad,good",
    [
        ("sof tmax", "softmax"),
        ("wtih", "with"),
        ("drouput", "dropout"),
        ("dropP rob", "DropProb"),
        ("trillionparameter", "trillion parameter"),
        ("multiply-andadds", "multiply-and-adds"),
    ],
)
def test_detect_suspicious_word_forms(bad, good):
    problems = detect(f"a {bad} b")
    hits = [p for p in problems if "suspicious word form" in p.message]
    assert len(hits) == 1, (bad, problems)
    assert f"maybe '{good}'" in hits[0].message


def test_detect_word_form_not_in_math():
    problems = detect("$wtih$")
    assert not any("suspicious word form" in p.message for p in problems)


def test_detect_word_form_does_not_fix():
    # detect-only:只报不改
    assert fix("models wtih no MoE") == "models wtih no MoE"


def test_detect_word_form_clean():
    assert not any("suspicious word form" in p.message for p in detect("the softmax with dropout"))


# --- 相邻 letter-run 聚合提示(MoE: k t h \_ excluding 是同一标识符)---

def test_detect_identifier_split_hint():
    problems = detect("$k t h \\_ excluding (H)$")
    hits = [p for p in problems if "possible same identifier" in p.message]
    assert len(hits) == 1
    assert "'k t h' + 'excluding'" in hits[0].message


def test_detect_identifier_split_spaced_long_ident():
    # 长标识符仍是字母+空格形态(e x c l u d i n g)也命中,展示时去空格
    problems = detect("$k t h \\_ e x c l u d i n g$")
    hits = [p for p in problems if "possible same identifier" in p.message]
    assert len(hits) == 1
    assert "'k t h' + 'excluding'" in hits[0].message


def test_detect_identifier_split_underscore_separator():
    problems = detect("$k t h _ excluding$")
    assert any("possible same identifier" in p.message for p in problems)


def test_detect_identifier_split_far_apart_not_reported():
    # 中间隔着别的 token:不算相邻
    problems = detect("$k t h = f ( x ) + excluding$")
    assert not any("possible same identifier" in p.message for p in problems)
