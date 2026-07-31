from scripts.fixers.images import organize as organize_images


def test_copies_images_and_fixes_paths(tmp_path):
    src_images = tmp_path / "mineru_out" / "images"
    src_images.mkdir(parents=True)
    (src_images / "fig1.png").write_bytes(b"fake-png")
    md = tmp_path / "paper.md"
    md.write_text("![fig](mineru_out/images/fig1.png)", encoding="utf-8")

    organize_images(md, src_images)

    assert (tmp_path / "images" / "fig1.png").exists()  # copied next to .md
    assert (src_images / "fig1.png").exists()  # copy, not move: source intact
    assert md.read_text(encoding="utf-8") == "![fig](images/fig1.png)"


def test_missing_source_dir_is_noop(tmp_path):
    md = tmp_path / "paper.md"
    md.write_text("![fig](images/fig1.png)", encoding="utf-8")

    organize_images(md, tmp_path / "nonexistent")  # must not raise

    assert md.read_text(encoding="utf-8") == "![fig](images/fig1.png)"


def test_external_urls_untouched(tmp_path):
    md = tmp_path / "paper.md"
    md.write_text("![web](https://example.com/a.png)", encoding="utf-8")

    organize_images(md, tmp_path / "nonexistent")

    assert md.read_text(encoding="utf-8") == "![web](https://example.com/a.png)"


def test_out_dir_name_respected(tmp_path):
    # K3 解析需要 Image/(而非 images/)
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.png").write_bytes(b"x")
    md = tmp_path / "paper.md"
    md.write_text("![fig](old/a.png)", encoding="utf-8")

    organize_images(md, src, "Image")

    assert (tmp_path / "Image" / "a.png").exists()
    assert md.read_text(encoding="utf-8") == "![fig](Image/a.png)"
