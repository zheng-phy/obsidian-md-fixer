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


def test_mkdir_parents_creates_deep_path(tmp_path):
    # 谷歌MoE WinError 3:深层目标目录不会自动建
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.png").write_bytes(b"x")
    md = tmp_path / "paper.md"
    md.write_text("![f](old/a.png)", encoding="utf-8")

    organize_images(md, src, "deep/sub/images")

    assert (tmp_path / "deep" / "sub" / "images" / "a.png").exists()
    assert md.read_text(encoding="utf-8") == "![f](deep/sub/images/a.png)"


def test_reference_always_relative_even_with_abs_outdir(tmp_path):
    # out_dir 传绝对路径,引用仍写为相对 md 的 POSIX 路径
    src = tmp_path / "src"
    src.mkdir()
    (src / "fig.jpg").write_bytes(b"x")
    md = tmp_path / "p.md"
    md.write_text("![](fig.jpg)", encoding="utf-8")
    out = tmp_path / "assets" / "img"

    organize_images(md, src, str(out))

    assert (out / "fig.jpg").exists()
    text = md.read_text(encoding="utf-8")
    assert "C:" not in text  # 绝对路径根除
    assert text == "![](assets/img/fig.jpg)"


def test_ref_not_rewritten_when_source_missing(tmp_path):
    # training-04:图本就在 md 旁、图源目录不存在时,引用不被改断
    md = tmp_path / "p.md"
    md.write_text("![](fig.png)", encoding="utf-8")

    organize_images(md, tmp_path / "nonexistent")

    assert md.read_text(encoding="utf-8") == "![](fig.png)"


def test_ref_not_rewritten_when_file_not_in_source(tmp_path):
    # 只重写实际复制成功的文件:未复制的引用原样保留
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.png").write_bytes(b"x")
    md = tmp_path / "p.md"
    md.write_text("![near](fig.png) ![copied](a.png)", encoding="utf-8")

    organize_images(md, src)

    text = md.read_text(encoding="utf-8")
    assert "![near](fig.png)" in text
    assert "![copied](images/a.png)" in text


def test_organize_rewrites_paren_path_to_relative(tmp_path):
    # 谷歌MoE:绝对引用(路径含括号)必须重写为相对 POSIX 引用
    src = tmp_path / "谷歌MoE(flash实测)" / "Image"
    src.mkdir(parents=True)
    (src / "fig1.jpg").write_bytes(b"x")
    md = tmp_path / "p.md"
    md.write_text("![](C:/proj/谷歌MoE(flash实测)/Image/fig1.jpg)", encoding="utf-8")

    organize_images(md, src, "Image")

    assert md.read_text(encoding="utf-8") == "![](Image/fig1.jpg)"
