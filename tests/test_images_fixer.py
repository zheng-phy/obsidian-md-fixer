from scripts.fixers.images import organize, detect


def test_organize_copies_and_rewrites(tmp_path):
    src = tmp_path / "src_imgs"
    src.mkdir()
    (src / "a.png").write_bytes(b"x")
    md = tmp_path / "paper.md"
    md.write_text("![f](old/a.png)", encoding="utf-8")
    organize(md, src)
    assert (tmp_path / "images" / "a.png").exists()
    assert "![f](images/a.png)" in md.read_text(encoding="utf-8")


def test_detect_missing_image_with_line(tmp_path):
    md = tmp_path / "m.md"
    md.write_text("line1\n![f](images/gone.png)", encoding="utf-8")
    problems = detect(md)
    assert any(p.fixer == "images" and p.line == 2 and "gone.png" in p.message for p in problems)


def test_detect_external_url_ok(tmp_path):
    md = tmp_path / "m.md"
    md.write_text("![f](https://x.com/a.png)", encoding="utf-8")
    assert detect(md) == []
