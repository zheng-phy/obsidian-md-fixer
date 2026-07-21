from scripts.fixers.base import split_zones


def test_code_block_isolated():
    kinds = [k for k, _ in split_zones("```\nSiO2\n``` rest")]
    assert kinds[0] == "code_block" and kinds[-1] == "text"


def test_image_isolated():
    segs = split_zones("![x](images/fig_c4.jpg) and SiO2")
    assert segs[0][0] == "image" and segs[-1][0] == "text"


def test_math_isolated():
    segs = split_zones("already $SiO_2$ done")
    assert any(k == "math" for k, _ in segs)


def test_url_isolated():
    segs = split_zones("see https://example.com/SiO2-page end")
    assert segs[1][0] == "url"


def test_plain_text_passthrough():
    assert split_zones("plain SiO2 text") == [("text", "plain SiO2 text")]
