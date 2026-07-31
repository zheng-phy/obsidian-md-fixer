from scripts.fixers.chem_formula import fix, detect, find_unfixed_formulas


def test_sio2_subscript():
    assert fix("The support is SiO2.") == "The support is $SiO_2$."


def test_organic_internal_subscripts():
    # 既有行为:每个数字串前加 _ 。多位数下标(H12)的 _ 只对下一字符生效,
    # 渲染为 H₁₂ 而非 H₁₂ 整体下标——这是 latex_fixer 沿袭至今的局限,本次重构不改行为。
    assert fix("glucose C6H12O6 here") == "glucose $C_6H_12O_6$ here"


def test_acronym_not_converted():
    assert fix("XRD and SEM results") == "XRD and SEM results"


def test_existing_math_not_double_wrapped():
    assert fix("$SiO_2$ already fine") == "$SiO_2$ already fine"


def test_image_path_not_polluted():
    assert fix("![x](images/fig_c4.jpg) and SiO2") == "![x](images/fig_c4.jpg) and $SiO_2$"


def test_inline_code_not_polluted():
    assert fix("`SiO2` but SiO2") == "`SiO2` but $SiO_2$"


def test_url_not_polluted():
    assert fix("see https://example.com/SiO2-page and SiO2") == "see https://example.com/SiO2-page and $SiO_2$"


def test_word_boundary_respected():
    assert fix("Fig. 1C4 shows") == "Fig. 1C4 shows"


def test_detect_reports_line():
    problems = detect("line one\nThe support is SiO2.")
    assert any(p.fixer == "chem_formula" and p.line == 2 and "SiO2" in p.message for p in problems)


def test_find_unfixed_formulas():
    assert "SiO2" in find_unfixed_formulas("The support is SiO2.")


def test_detect_skips_fenced_code():
    # fenced 代码内 M1/M2 不再报(B157 误报根因)
    text = "```python\nM1 = M2\nprint(M1)\n```\n正文 SiO2"
    problems = detect(text)
    assert not any("M1" in p.message or "M2" in p.message for p in problems)
    assert any("SiO2" in p.message for p in problems)


def test_detect_line_number_across_zones():
    # 行号按各段在原文中的偏移换算,跨 math 段仍准确
    text = "line1\n$$x=1$$\nline3 SiO2"
    problems = detect(text)
    assert any(p.line == 3 for p in problems)


def test_detect_ml_term_hint_in_text():
    problems = detect("GPT2 is a model.")
    assert any("ML/AI" in p.message for p in problems)
