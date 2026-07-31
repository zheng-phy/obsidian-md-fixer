import pytest

from scripts.fixers.chem_formula import _is_formula_token, _segmentable


@pytest.mark.parametrize(
    "letters",
    ["SiO", "CHO", "C", "CO", "HO", "NO", "FeO", "NaCl", "S", "K", "Ca", "SiC", "SV"],
)
def test_segmentable_element_sequences(letters):
    # SiC=Si+C, SV=S+V 均可切分(但无数字/词形不对仍被 _is_formula_token 拒绝,见下)
    assert _segmentable(letters)


@pytest.mark.parametrize(
    "letters",
    [
        "GSM", "MATH", "AIM", "GPT", "MOE", "LORA",
        "LLM", "API", "BRCA", "IL", "COX", "XRD", "SEM", "G", "L", "M", "X",
        "SITU", "SILU", "FLOP",
    ],
)
def test_non_segmentable_letter_runs(letters):
    # 贪心切分:单遍左到右优先 2 字母,失败回退 1 字母,不回看。
    # 大小写敏感:"FLOP" = F + L? (L 非元素) -> 拒(Fl 是 Flerovium,但 'FL' 不是)。
    # 例:BRCA -> B+? (BR 非元素) -> 拒;IL -> I+L (L 非元素) -> 拒;
    #     SITU -> Si + T? (TU 非元素, T 非元素) -> 拒。
    assert not _segmentable(letters)


@pytest.mark.parametrize(
    "t",
    ["SiO2", "C6H12O6", "C4", "CO2", "H2O", "NO2", "K2CO3", "NaCl2"],
)
def test_real_formula_tokens_accepted(t):
    assert _is_formula_token(t)


@pytest.mark.parametrize(
    "t",
    [
        "GSM8K", "MATH500", "AIME24", "GPT2", "MoE", "LoRA", "FLOPs",
        "SiLU", "SiTU", "LLMs", "APIs", "Sv2", "SiC", "BRCA1", "IL6", "COX2",
        "XRD", "SEM", "ASCII", "RGB", "HTTP",
    ],
)
def test_non_formula_tokens_rejected(t):
    assert not _is_formula_token(t)
