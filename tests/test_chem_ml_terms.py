from scripts.fixers.chem_formula import detect


def test_ml_terms_flagged_for_review():
    problems = detect("模型用 MoE 和 LoRA 微调")
    assert any("review" in p.message.lower() or "ML" in p.message for p in problems)


def test_ml_term_with_trailing_digit_flagged_for_review():
    problems = detect("使用 GPT2 训练")
    assert any("review" in p.message.lower() or "ML" in p.message for p in problems)


def test_real_chemical_not_flagged_as_ml():
    problems = detect("催化剂 SiO2 反应")
    assert not any("review" in p.message.lower() for p in problems)
