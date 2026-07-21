from scripts.postprocess import main


def test_chinese_and_space_path(tmp_path):
    d = tmp_path / "科创 项目"
    d.mkdir()
    md = d / "论文 笔记.md"
    md.write_text("<table><tr><td>SiO2</td></tr></table>", encoding="utf-8")
    code = main([str(md)])
    assert code == 0
    content = (d / "论文 笔记_fixed.md").read_text(encoding="utf-8")
    assert "$SiO_2$" in content
