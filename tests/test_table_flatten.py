"""table_flatten tests — fixtures from 2021国赛B题论文 (flash实测), NOT from the
skill copy: B007 表8 (rowspan=2 colspan=2 表头组 + y1/y2 各 rowspan=6 组标签) and
B026 表11 (colspan=6 双组表头,各 12 数据列)。期望输出为执行时人工核对后写死。"""

from scripts.fixers.table_flatten import fix, detect

# B007.md line 274 (2021国赛B题 表8:回归系数分析表)
B007_TABLE8 = (
    '<table><tr><td rowspan="2" colspan="2">模型</td><td colspan="2">未标准化系数</td>'
    "<td>标准化系数</td><td rowspan=\"2\">t</td><td rowspan=\"2\">显著性</td></tr>"
    "<tr><td>B</td><td>标准误差</td><td>Beta</td></tr>"
    '<tr><td rowspan="6"> $y_1$ </td><td>(常量)</td><td>-80.509</td><td>7.231</td>'
    "<td></td><td>-11.134</td><td>.000</td></tr>"
    "<tr><td> $x_1$ </td><td>-.034</td><td>.071</td><td>-.104</td><td>-.476</td><td>.635</td></tr>"
    "<tr><td> $x_2$ </td><td>.134</td><td>.898</td><td>.007</td><td>.149</td><td>.882</td></tr>"
    "<tr><td> $x_3$ </td><td>.141</td><td>.069</td><td>.448</td><td>2.045</td><td>.043</td></tr>"
    "<tr><td> $x_4$ </td><td>-8.765</td><td>2.065</td><td>-.199</td><td>-4.244</td><td>.000</td></tr>"
    "<tr><td> $x_5$ </td><td>.333</td><td>.019</td><td>.763</td><td>17.530</td><td>.000</td></tr>"
    '<tr><td rowspan="6"> $y_2$ </td><td>(常量)</td><td>-48.732</td><td>5.112</td>'
    "<td></td><td>-9.532</td><td>.000</td></tr>"
    "<tr><td> $x_1$ </td><td>.003</td><td>.050</td><td>.015</td><td>.059</td><td>.953</td></tr>"
    "<tr><td> $x_2$ </td><td>-3.164</td><td>.635</td><td>-.271</td><td>-4.983</td><td>.000</td></tr>"
    "<tr><td> $x_3$ </td><td>.086</td><td>.049</td><td>.462</td><td>1.769</td><td>.080</td></tr>"
    "<tr><td> $x_4$ </td><td>2.673</td><td>1.460</td><td>.102</td><td>1.831</td><td>.070</td></tr>"
    "<tr><td> $x_5$ </td><td>.181</td><td>.013</td><td>.701</td><td>13.489</td><td>.000</td></tr></table>"
)

# B026.md line 448 (2021国赛B题 表11:乙醇转化率/C4烯烃选择性 排序表,双 colspan=6 组)
B026_TABLE11 = (
    '<table><tr><td colspan="6">乙醇转化率</td><td colspan="6">C4烯烃选择性</td></tr>'
    "<tr><td>排序</td><td>组别</td><td>均值差之和</td><td>排序</td><td>组别</td><td>均值差之和</td>"
    "<td>排序</td><td>组别</td><td>均值差之和</td><td>排序</td><td>组别</td><td>均值差之和</td></tr>"
    "<tr><td>1</td><td>A7</td><td>506.81</td><td>12</td><td>A12</td><td>-157.09</td>"
    "<td>1</td><td>A1</td><td>531.83</td><td>12</td><td>A5</td><td>-33.91</td></tr>"
    "<tr><td>2</td><td>A2</td><td>478.59</td><td>13</td><td>B1</td><td>-166.01</td>"
    "<td>2</td><td>A2</td><td>369.56</td><td>13</td><td>B6</td><td>-39.28</td></tr>"
    "<tr><td>11</td><td>A14</td><td>-71.14</td><td>/</td><td>/</td><td>/</td>"
    "<td>11</td><td>A13</td><td>-14.70</td><td>/</td><td>/</td><td>/</td></tr></table>"
)


def test_flatten_b007_table8_header():
    out = fix(B007_TABLE8)
    assert "| 模型 | 模型 |" not in out  # 无简单重复
    assert "| 模型 | 模型 (2) |" in out  # 跨 2 列的 rowspan 表头,重名列加序号
    assert "未标准化系数 B" in out and "标准化系数 Beta" in out  # 复合列名
    assert "<!-- auto-flattened" in out
    assert "<table>" not in out


def test_flatten_rowspan_group_label_filled_down():
    out = fix(B007_TABLE8)
    lines = out.splitlines()
    y1_rows = [ln for ln in lines if ln.startswith("| $y_1$ |")]
    assert len(y1_rows) == 6  # y1 在 6 个数据行的首列都出现
    assert any("$x_5$" in ln and "17.530" in ln for ln in y1_rows)


def test_flatten_b026_table11_compound_headers():
    out = fix(B026_TABLE11)
    assert "乙醇转化率 排序" in out
    assert "C4烯烃选择性 均值差之和" in out
    assert "乙醇转化率 排序 (2)" in out  # 重名列加序号
    assert "| 1 | A7 | 506.81 | 12 | A12 | -157.09 |" in out


def test_flatten_marks_every_table():
    out = fix(B007_TABLE8 + "\n正文\n" + B026_TABLE11)
    assert out.count("<!-- auto-flattened") == 2


def test_detect_reports_draft_issue():
    problems = detect(B007_TABLE8)
    assert len(problems) == 1
    assert "flattened merged-cell table (draft)" in problems[0].message
    assert "verify against PDF" in problems[0].message


def test_detect_clean_after_flatten():
    assert detect(fix(B007_TABLE8)) == []
