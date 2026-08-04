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
    md.write_text("![f](images/a.png)\nFigure 1: ok\n", encoding="utf-8")
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


def test_content_list_restores_before_text_fixers(tmp_path):
    # fffd_restore 必须先于文本修复器(ocr_cleanup 合并空格会破坏对齐)
    import json

    md = tmp_path / "p.md"
    md.write_text("contains \ufffd=128 tokens", encoding="utf-8")
    cl = tmp_path / "cl.json"
    cl.write_text(
        json.dumps([{"type": "paragraph", "content": {"paragraph_content": [
            {"type": "text", "content": "contains "},
            {"type": "equation_inline", "content": "$N$"},
            {"type": "text", "content": "=128 tokens"},
        ]}}]),
        encoding="utf-8",
    )
    code = main([str(md), "--content-list", str(cl)])
    assert code == 0
    content = (tmp_path / "p_fixed.md").read_text(encoding="utf-8")
    assert "\ufffd" not in content
    assert "contains $N$=128 tokens" in content


def test_content_list_unresolvable_reported_as_residual(tmp_path):
    import json

    md = tmp_path / "p.md"
    md.write_text("不可还原的 \ufffd 内容", encoding="utf-8")
    cl = tmp_path / "cl.json"
    cl.write_text(
        json.dumps([{"type": "paragraph", "content": {"paragraph_content": [
            {"type": "text", "content": "无关内容"}]}}]),
        encoding="utf-8",
    )
    code = main([str(md), "--content-list", str(cl)])
    assert code == 2  # 有残留 → 警告
    content = (tmp_path / "p_fixed.md").read_text(encoding="utf-8")
    assert "\ufffd" in content  # 绝不臆造:保留
    problems = (tmp_path / "p_fixed.md").read_text(encoding="utf-8")
    assert "\ufffd" in problems


def test_default_run_no_content_list_is_noop_for_fffd(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("有 \ufffd 但没给 JSON", encoding="utf-8")
    code = main([str(md)])
    assert code == 2  # detect 提示需要 --content-list
    content = (tmp_path / "p_fixed.md").read_text(encoding="utf-8")
    assert "\ufffd" in content  # 文件本身未被改写
