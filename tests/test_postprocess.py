from scripts.postprocess import main


def test_fix_mode_writes_fixed_copy_and_keeps_original(tmp_path):
    md = tmp_path / "paper.md"
    md.write_text("<table><tr><td>SiO2</td></tr></table>\n", encoding="utf-8")

    code = main([str(md)])

    assert code == 0
    fixed = tmp_path / "paper_fixed.md"
    content = fixed.read_text(encoding="utf-8")
    assert "<table>" not in content
    assert "$" not in content  # v2 默认集不含 chem_formula,SiO2 不再自动 wrap
    assert md.read_text(encoding="utf-8").startswith("<table>")  # original untouched


def test_in_place_creates_backup(tmp_path):
    md = tmp_path / "paper.md"
    md.write_text("SiO2", encoding="utf-8")

    code = main([str(md), "--in-place"])

    assert code == 0
    assert (tmp_path / "paper.md.bak").exists()
    assert md.read_text(encoding="utf-8") == "SiO2"  # 默认集不动化学式


def test_missing_input_returns_1(tmp_path):
    assert main([str(tmp_path / "nope.md")]) == 1


def test_verification_warnings_return_2_but_output_exists(tmp_path):
    md = tmp_path / "bad.md"
    md.write_text("![f](images/gone.png)", encoding="utf-8")  # missing image -> warning

    code = main([str(md)])

    assert code == 2
    assert (tmp_path / "bad_fixed.md").exists()


def test_non_md_extensions_return_1(tmp_path):
    for name in ("x.txt", "paper.pdf", "paper.docx"):
        f = tmp_path / name
        f.write_text("hi", encoding="utf-8")
        assert main([str(f)]) == 1


def test_skip_chem_formula_leaves_sv2(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("force Sv2 term", encoding="utf-8")
    main([str(md), "--skip", "chem_formula"])
    content = (tmp_path / "p_fixed.md").read_text(encoding="utf-8")
    assert "$Sv_2$" not in content


def test_fixers_only_table(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("<table><tr><td>SiO2</td></tr></table>", encoding="utf-8")
    main([str(md), "--fixers", "table"])
    content = (tmp_path / "p_fixed.md").read_text(encoding="utf-8")
    assert "<table>" not in content and "$SiO_{2}$" not in content


def test_images_dir_used(tmp_path):
    src = tmp_path / "ext"
    src.mkdir()
    (src / "a.png").write_bytes(b"x")
    md = tmp_path / "p.md"
    md.write_text("![f](images/a.png)", encoding="utf-8")
    code = main([str(md), "--images-dir", str(src)])
    assert (tmp_path / "images" / "a.png").exists()
    assert code == 0


def test_verify_mode_clean_returns_0_and_writes_nothing(tmp_path):
    md = tmp_path / "ok.md"
    md.write_text("clean text $x^2$", encoding="utf-8")
    code = main([str(md), "--verify"])
    assert code == 0
    assert not (tmp_path / "ok_fixed.md").exists()  # 不产出 _fixed
    assert md.read_text(encoding="utf-8") == "clean text $x^2$"  # 原文件不动


def test_verify_mode_with_issues_returns_2(tmp_path):
    md = tmp_path / "bad.md"
    md.write_text("![f](images/gone.png)", encoding="utf-8")  # missing image
    code = main([str(md), "--verify"])
    assert code == 2
    assert not (tmp_path / "bad_fixed.md").exists()  # 不产出 _fixed


def test_verify_mode_missing_input_returns_1(tmp_path):
    assert main([str(tmp_path / "nope.md"), "--verify"]) == 1


def test_rerun_hint_printed(tmp_path, capsys):
    md = tmp_path / "p.md"
    md.write_text("text", encoding="utf-8")
    main([str(md), "--skip", "chem_formula"])
    out = capsys.readouterr().out
    assert "--skip chem_formula" in out
