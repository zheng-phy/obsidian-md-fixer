from scripts.fixers.images import detect


def test_image_before_first_heading_flagged(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("![f](images/a.png)\n# Title\ntext", encoding="utf-8")
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.png").write_bytes(b"x")
    problems = detect(md)
    assert any(
        "before" in problem.message.lower()
        or "placement" in problem.message.lower()
        or "position" in problem.message.lower()
        for problem in problems
    )


def test_image_after_heading_not_flagged(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("# Title\n\n![f](images/a.png)\n", encoding="utf-8")
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.png").write_bytes(b"x")
    problems = detect(md)
    assert not any("before" in problem.message.lower() for problem in problems)


def test_axis_label_mis_tagged_as_heading(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("## 利润值/元\ntext\n", encoding="utf-8")
    (tmp_path / "images").mkdir()
    problems = detect(md)
    assert any("axis label" in p.message for p in problems)


def test_normal_heading_not_flagged_as_axis_label(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("## 利润分析\ntext\n", encoding="utf-8")
    (tmp_path / "images").mkdir()
    assert not any("axis label" in p.message for p in detect(md))
