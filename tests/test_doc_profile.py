from scripts.verifier import _chem_opportunity


def test_chem_doc_triggers_hint():
    # 3 个不同 formula-like token → 机会提示出现
    text = "催化剂 SiO2 和 Al2O3 反应,另见 TiO2 数据"
    issue = _chem_opportunity(text)
    assert issue is not None
    assert "--fixers chem_formula" in issue.message


def test_chem_context_words_upgrade_wording():
    # 命中化学上下文词(材料)时措辞升级
    text = "材料中 SiO2、TiO2、Al2O3 均出现"
    issue = _chem_opportunity(text)
    assert issue is not None
    assert "likely a chemistry document" in issue.message


def test_neutral_wording_without_context_words():
    # 无数字的 NaCl 不进统计(数字必需);用带数字的 token 凑 3 个
    text = "Run A with SiO2, run B with TiO2, run C with Al2O3"
    issue = _chem_opportunity(text)
    assert issue is not None
    assert "if this is a chemistry/materials document" in issue.message


def test_llm_text_no_hint():
    # GSM8K / GPT2 / MoE / LoRA / V3.2 全被周期表拒绝,命中 <3 → 无提示
    text = "GSM8K 与 GPT2 对比,MoE 和 LoRA 微调,DeepSeek-V3.2 表现"
    assert _chem_opportunity(text) is None


def test_under_threshold_no_hint():
    assert _chem_opportunity("只有一个 SiO2") is None


def test_plain_prose_no_hint():
    assert _chem_opportunity("普通文本,没有公式") is None
