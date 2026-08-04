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


def test_image_ref_with_parens_in_path():
    # 谷歌MoE 样本:目录名"(flash实测)"曾把路径在 ) 处截断
    text = r"![](C:/proj/谷歌MoE(flash实测)/Image/fig1.jpg)"
    kinds = [k for k, _ in split_zones(text)]
    assert kinds == ["image"]  # 整条一个 image zone,不截断


def test_link_with_parens_in_url():
    # wikipedia 式带括号 URL:link zone 同样要容忍一层嵌套括号
    text = "[ref](https://en.wikipedia.org/wiki/Foo_(bar))"
    kinds = [k for k, _ in split_zones(text)]
    assert kinds == ["link"]


def test_stray_lt_does_not_swallow_spans():
    # training-04 案发现场:0<\theta 与远处 r>0 曾被拼成跨行 html zone,
    # 吞掉 5 段公式;现在不得产出任何 html zone
    text = "若 0<\\theta<1 且 $r>0$ 时\n\n跨行内容 $x=1$\n"
    kinds = [k for k, _ in split_zones(text)]
    assert "html" not in kinds  # 无 html zone,文本与 math 各自完整


def test_same_line_stray_lt_not_swallowed():
    # 同行 0<\theta<1 and r>0:即便距离近,反斜杠开头的也不是 tag
    text = "0<\\theta<1 and r>0"
    kinds = [k for k, _ in split_zones(text)]
    assert "html" not in kinds


def test_real_html_and_comment_still_zoned():
    assert [k for k, _ in split_zones("<!-- image -->")][0] == "html"
    assert "html" in [k for k, _ in split_zones('<div class="x">')]
    assert "html" in [k for k, _ in split_zones("</table>")]
