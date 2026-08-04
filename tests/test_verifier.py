from scripts.verifier import verify


def test_clean_file_passes(tmp_path):
    images = tmp_path / "images"
    images.mkdir()
    (images / "a.png").write_bytes(b"x")
    md = tmp_path / "ok.md"
    md.write_text("text $SiO_2$ and $$E=mc^2$$\n\n![f](images/a.png)\nFigure 1: ok\n", encoding="utf-8")

    assert verify(md) == []


def test_detects_unconverted_table(tmp_path):
    md = tmp_path / "t.md"
    md.write_text("<table><tr><td>x</td></tr></table>", encoding="utf-8")

    assert any("table" in p.lower() for p in verify(md))


def test_detects_unpaired_dollar(tmp_path):
    md = tmp_path / "d.md"
    md.write_text("broken $SiO_2 here", encoding="utf-8")

    assert any("$" in p for p in verify(md))


def test_detects_missing_image(tmp_path):
    md = tmp_path / "m.md"
    md.write_text("![f](images/gone.png)", encoding="utf-8")

    assert any("gone.png" in p for p in verify(md))


def test_detects_unfixed_formula(tmp_path):
    md = tmp_path / "f.md"
    md.write_text("The support is SiO2.", encoding="utf-8")

    assert any("SiO2" in p for p in verify(md))


def test_chem_opportunity_shown_on_default_set_but_not_when_chem_selected(tmp_path):
    from scripts.verifier import verify_issues

    md = tmp_path / "p.md"
    md.write_text("催化剂 SiO2 和 Al2O3 反应,另见 TiO2 数据", encoding="utf-8")
    # 默认集(不含 chem_formula):机会提示出现
    default_set = ["table", "math_delim", "ocr_cleanup", "algorithm", "code_fence", "images"]
    default_issues = verify_issues(md, default_set)
    assert any("formula-like" in i.message for i in default_issues)
    # 显式选中 chem_formula:提示消失(已由 fixer 本体处理)
    chem_issues = verify_issues(md, ["chem_formula"])
    assert not any("formula-like" in i.message for i in chem_issues)


def test_low_confidence_wrap_reported(tmp_path):
    from scripts.verifier import verify_issues

    md = tmp_path / "p.md"
    md.write_text("关于 $V_3$ 和 $K_3$ 的讨论", encoding="utf-8")
    issues = verify_issues(md, ["chem_formula"])
    low = [i for i in issues if "low-confidence" in i.message]
    assert len(low) == 2
    assert any("$V_3$" in i.message for i in low)
    assert any("$K_3$" in i.message for i in low)


def test_low_confidence_wrap_not_reported_for_real_formulas(tmp_path):
    from scripts.verifier import verify_issues

    md = tmp_path / "p.md"
    md.write_text("$SiO_2$ 与 $C_{6}H_{12}O_{6}$ 正常", encoding="utf-8")
    issues = verify_issues(md, ["chem_formula"])
    assert not any("low-confidence" in i.message for i in issues)


def test_low_confidence_wrap_not_run_without_chem(tmp_path):
    from scripts.verifier import verify_issues

    md = tmp_path / "p.md"
    md.write_text("关于 $V_3$ 的讨论", encoding="utf-8")
    issues = verify_issues(md, ["table"])  # chem 未选中 -> 不运行
    assert not any("low-confidence" in i.message for i in issues)


def test_low_confidence_wrap_fires_on_actual_chem_output(tmp_path):
    """端到端:fix() 产出的是带花括号的 $V_{3}$——复核网必须仍能命中。"""
    from scripts.fixers.chem_formula import fix
    from scripts.verifier import verify_issues

    md = tmp_path / "p.md"
    md.write_text(fix("模型 V3 与 C4 对比"), encoding="utf-8")
    assert "$V_{3}$" in md.read_text(encoding="utf-8")  # 花括号形态
    issues = verify_issues(md, ["chem_formula"])
    low = [i for i in issues if "low-confidence" in i.message]
    assert len(low) == 2


def test_low_confidence_wrap_clustered_by_token(tmp_path):
    """2021B 的 $C_{4}$ 洪峰(184 条)必须聚成 1 条,不同 token 各自一条。"""
    from scripts.verifier import verify_issues

    md = tmp_path / "p.md"
    md.write_text(
        "关于 $C_{4}$ 与 $C_{4}$ 和 $C_{4}$ 的讨论\n以及 $V_{3}$ 的情况",
        encoding="utf-8",
    )
    issues = verify_issues(md, ["chem_formula"])
    low = [i for i in issues if "low-confidence" in i.message]
    assert len(low) == 2
    c4 = [i for i in low if "$C_{4}$" in i.message]
    v3 = [i for i in low if "$V_{3}$" in i.message]
    assert len(c4) == 1 and "×3" in c4[0].message and "line 1" in c4[0].message
    assert len(v3) == 1 and v3[0].line == 2


def test_low_confidence_wrap_single_occurrence_no_count_suffix(tmp_path):
    from scripts.verifier import verify_issues

    md = tmp_path / "p.md"
    md.write_text("单独 $K_3$ 一次", encoding="utf-8")
    issues = verify_issues(md, ["chem_formula"])
    low = [i for i in issues if "low-confidence" in i.message]
    assert len(low) == 1 and "×" not in low[0].message


def test_chem_opportunity_neutral_wording_on_llm_doc(tmp_path):
    """LLM 文档的证据词("LLM"里就有 L!)不得把措辞升级为 likely chemistry。"""
    from scripts.verifier import verify_issues

    md = tmp_path / "p.md"
    md.write_text("LLM benchmark rubric: C1, C2, C3 and V4 labels", encoding="utf-8")
    issues = verify_issues(md, ["table"])
    hint = [i for i in issues if "formula-like" in i.message]
    assert hint, "opportunity hint should fire (4 distinct valid tokens)"
    assert "likely a chemistry" not in hint[0].message
