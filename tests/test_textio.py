from scripts.postprocess import main
from scripts.textio import read_text_preserve, write_text_preserve


def test_crlf_roundtrip(tmp_path):
    p = tmp_path / "a.md"
    text = "line1\r\nline2\r\n"
    p.write_bytes(text.encode("utf-8"))
    read, nl = read_text_preserve(p)
    assert nl == "\r\n"
    write_text_preserve(p, read, nl)
    assert p.read_bytes() == text.encode("utf-8")  # 逐字节含 \r\n


def test_lf_roundtrip(tmp_path):
    p = tmp_path / "a.md"
    text = "line1\nline2\n"
    p.write_bytes(text.encode("utf-8"))
    read, nl = read_text_preserve(p)
    assert nl == "\n"
    write_text_preserve(p, read, nl)
    assert p.read_bytes() == text.encode("utf-8")  # 无 \r


def test_mixed_input_first_newline_wins(tmp_path):
    # 前 8KB 内首个 \r\n 决定目标换行
    p = tmp_path / "a.md"
    p.write_bytes(b"line1\r\nline2\nline3\n")
    read, nl = read_text_preserve(p)
    assert nl == "\r\n"


def test_write_normalizes_embedded_crlf(tmp_path):
    # 即使 fixer 输出混入 \r\n(如 split("\n") 保留的行尾 \r),写回仍统一干净
    p = tmp_path / "a.md"
    write_text_preserve(p, "a\r\nb\n", "\r\n")
    assert p.read_bytes() == b"a\r\nb\r\n"
    write_text_preserve(p, "a\r\nb\n", "\n")
    assert p.read_bytes() == b"a\nb\n"


def test_postprocess_preserves_crlf(tmp_path):
    md = tmp_path / "p.md"
    md.write_bytes(
        "正文\nimport os\ndef f(x):\n    return x\n结尾\n".replace("\n", "\r\n").encode("utf-8")
    )
    assert main([str(md), "--in-place"]) == 0
    out = md.read_bytes()
    assert b"\r\n" in out
    assert b"\n" not in out.replace(b"\r\n", b"")  # 无裸 \n
