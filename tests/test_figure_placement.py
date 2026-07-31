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
