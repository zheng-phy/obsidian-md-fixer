from scripts.verifier import doc_profile_hint


def test_math_dense_no_chem_suggests_skip():
    text = "\n".join(f"$$E=mc^2 {i}$$\n\\tag{{{i}}}" for i in range(15))
    hint = doc_profile_hint(text)
    assert hint is not None and "--skip chem_formula" in hint


def test_chem_present_no_hint():
    text = "$$x$$ 催化剂 SiO2 和 Al2O3 反应 " * 5
    assert doc_profile_hint(text) is None


def test_plain_text_no_hint():
    assert doc_profile_hint("just some prose without math or chem") is None


def test_math_dense_with_real_chem_no_hint():
    # 数学密集但有真化学式(SiC):不建议 skip,chem_formula 可能该跑。
    # 画像只在"明确无化学式"时才建议;拿不准就不建议(交给 Agent)。
    text = "\n".join(f"$$E=mc^2 {i}$$ 碳化硅 SiC 外延" for i in range(15))
    assert doc_profile_hint(text) is None
