from scripts.verifier import verify


def test_clean_file_passes(tmp_path):
    images = tmp_path / "images"
    images.mkdir()
    (images / "a.png").write_bytes(b"x")
    md = tmp_path / "ok.md"
    md.write_text("text $SiO_2$ and $$E=mc^2$$\n\n![f](images/a.png)", encoding="utf-8")

    assert verify(md) == []


def test_detects_unconverted_table(tmp_path):
    md = tmp_path / "t.md"
    md.write_text("<table><tr><td>x</td></tr></table>", encoding="utf-8")

    assert any("table" in p.lower() for p in verify(md))


def test_detects_unpaired_dollar(tmp_path):
    md = tmp_path / "d.md"
    md.write_text("broken $SiO_2 here", encoding="utf-8")

    assert any("$" in p for p in verify(md))


def test_detects_missing_image(tmp_path):
    md = tmp_path / "m.md"
    md.write_text("![f](images/gone.png)", encoding="utf-8")

    assert any("gone.png" in p for p in verify(md))


def test_detects_unfixed_formula(tmp_path):
    md = tmp_path / "f.md"
    md.write_text("The support is SiO2.", encoding="utf-8")

    assert any("SiO2" in p for p in verify(md))
