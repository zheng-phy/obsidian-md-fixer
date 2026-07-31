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
    md.write_text("![f](https://x.com/a.png)\nFigure 1: 外部图\n", encoding="utf-8")
    assert detect(md) == []


def _write_with_images(tmp_path, name, text, imgs=("a.png",)):
    md = tmp_path / name
    md.write_text(text, encoding="utf-8")
    d = tmp_path / "images"
    d.mkdir(exist_ok=True)
    for img in imgs:
        (d / img).write_bytes(b"x")
    return md


def test_image_without_caption_within_window(tmp_path):
    # K3 首页形态:图 line 1,图注远在 line 19 → ①报
    body = "![f](images/a.png)\n" + "\n".join(f"line{i}" for i in range(1, 18)) + "\nFigure 19: 架构图\n"
    md = _write_with_images(tmp_path, "p.md", body)
    problems = detect(md)
    assert any("no caption" in p.message for p in problems)


def test_caption_image_pairing_ok(tmp_path):
    md = _write_with_images(
        tmp_path, "p.md",
        "# Title\n\n![f](images/a.png)\nFigure 1: 结果\n\n![g](images/b.png)\nFig. 2 流程\n",
        imgs=("a.png", "b.png"),
    )
    problems = detect(md)
    assert not any("no caption" in p.message or "no image" in p.message for p in problems)


def test_caption_mention_with_period_not_caption(tmp_path):
    # "图 5 给出了……。"以句号结尾,不是图注(正文提及)→ 图报孤儿,但不误报图注
    md = _write_with_images(tmp_path, "p.md", "# Title\n![f](images/a.png)\n图 5 给出了详细的对比结果。\n")
    problems = detect(md)
    orphans = [p for p in problems if "no caption" in p.message]
    assert len(orphans) == 1
    assert not any("orphan caption" in p.message for p in problems)


def test_out_of_order_captions(tmp_path):
    md = _write_with_images(
        tmp_path, "p.md",
        "# Title\n![a](images/a.png)\nFigure 1: A\n\n![b](images/b.png)\nFigure 3: B\n\n![c](images/c.png)\nFigure 2: C\n",
        imgs=("a.png", "b.png", "c.png"),
    )
    problems = detect(md)
    assert any("order anomaly" in p.message for p in problems)


def test_unreferenced_images_reported(tmp_path):
    md = _write_with_images(
        tmp_path, "p.md",
        "# T\n![f](images/a.png)\nFigure 1: x\n",
        imgs=("a.png", "b.png", "c.png"),
    )
    problems = detect(md)
    unreferenced = [p for p in problems if "unreferenced" in p.message]
    assert len(unreferenced) == 2
    names = {p.message.split(": ")[-1] for p in unreferenced}
    assert names == {"b.png", "c.png"}


def test_all_referenced_no_unreferenced(tmp_path):
    md = _write_with_images(tmp_path, "p.md", "# T\n![f](images/a.png)\nFigure 1: x\n", imgs=("a.png",))
    problems = detect(md)
    assert not any("unreferenced" in p.message for p in problems)


def test_no_images_dir_silent(tmp_path):
    md = tmp_path / "p.md"
    md.write_text("# T\n![f](images/a.png)\nFigure 1: x\n", encoding="utf-8")
    problems = detect(md)  # images/ 不存在,静默跳过
    assert not any("unreferenced" in p.message for p in problems)
