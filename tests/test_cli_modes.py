import json

from scripts.postprocess import main


def test_dry_run_writes_nothing(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("<table><tr><td>SiO2</td></tr></table>", encoding="utf-8")
    code = main([str(md), "--dry-run"])
    assert not (tmp_path / "p_fixed.md").exists()
    assert md.read_text(encoding="utf-8").startswith("<table>")
    assert code in (0, 2)


def test_issues_json_written(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("![f](images/gone.png)", encoding="utf-8")
    out = tmp_path / "issues.json"
    main([str(md), "--issues-json", str(out)])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert any("gone.png" in item["message"] for item in data)
    assert all(
        "fixer" in item and "line" in item and "message" in item for item in data
    )


def test_default_run_excludes_chem_formula(tmp_path):
    # v2:默认集不含 chem_formula,SiO2 保持原样
    md = tmp_path / "p.md"
    md.write_text("催化剂 SiO2 反应", encoding="utf-8")
    assert main([str(md)]) == 0
    content = (tmp_path / "p_fixed.md").read_text(encoding="utf-8")
    assert "$" not in content


def test_explicit_chem_formula_selected(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("催化剂 SiO2 反应", encoding="utf-8")
    assert main([str(md), "--fixers", "chem_formula"]) == 0
    content = (tmp_path / "p_fixed.md").read_text(encoding="utf-8")
    assert "$SiO_{2}$" in content


def test_skip_chem_formula_is_harmless_noop(tmp_path):
    # --skip chem_formula 不再有意义但必须不报错,结果与默认相同
    md = tmp_path / "p.md"
    md.write_text("催化剂 SiO2 反应", encoding="utf-8")
    assert main([str(md), "--skip", "chem_formula"]) == 0
    content = (tmp_path / "p_fixed.md").read_text(encoding="utf-8")
    assert "$" not in content
