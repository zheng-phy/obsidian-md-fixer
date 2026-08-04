# obsidian-md-fixer 设计文档

> 本文档是当前版本的唯一权威设计说明，随迭代更新，不分版本章节。
> 原项目名 pdf-to-obsidian，v2 起改为纯修复向并更名 obsidian-md-fixer。

## 1. 项目概述

### 1.1 目标

一个平台无关的 AI Agent skill：修复**已转换**的 Markdown（来自 MinerU、pandoc、Marker 等任意转换器）在 Obsidian 中的渲染问题。v2.0.0 起**默认面向 CS/AI/数学/物理论文深度优化**；化学式下标降为可选修复器（opt-in）。

- 用确定性的 Python 修复器（fixer）完成机械修复
- 把语义级问题（上下标、断句、OCR 误判、图序）交给 Agent 按行号清单处理
- 产出：一份修复后的 `.md` + 同级 `images/` 文件夹
- 不硬编码任何密钥或用户路径；纯本地处理，不访问网络

### 1.2 适用场景

- 转换后的 Markdown 表格渲染为原始 `<table>` HTML
- `\(...` 定界符断裂导致 Obsidian ParseError；行内公式被降级成文本（`X\~B(`、`0<p<1`）
- 图片路径错乱、图片缺失、图与图注分离、图序错乱、图包含未引用图
- 代码段被降级为普通文本（缺 ``` 围栏）；围栏被误标语言/碎片化；algorithm 块（`<div class="mineru-algorithm">`）未被转换
- 确定性 OCR 噪音（`\mathrm` 字母空格、`f^{\backslash…*}`、数字拆散、HTML 实体、U+FFFD、ff 连字丢失、URL 断行）
- （可选）化学式（SiO2、C6H12O6）无下标显示——需显式 `--fixers chem_formula`

### 1.3 不适用场景

- 把 PDF/Word **转换为** Markdown 本身——先用 MinerU / mineru skill 完成（两者是流水线上下游）
- 纯文本提取
- 转换为 Word/LaTeX/其他格式
- 扫描文档 OCR
- Markdown 中非表格 LaTeX 渲染问题（Obsidian/MathJax 问题）
- .tex 编译错误（LaTeX 编译器问题）
- 未适配领域的专门适配（如生物：构造上安全但无样本，YAGNI——见 §14 D5）

## 2. 架构

### 2.1 目录结构

```
obsidian-md-fixer/
├── SKILL.md                 # skill 入口文档(平台无关)
├── README.md                # 用户文档
├── DESIGN.md                # 本文件
├── requirements.txt         # Python 依赖(仅 pytest,修复器全标准库)
├── .claude-plugin/
│   ├── plugin.json          # plugin 清单(名称/版本/作者)
│   └── marketplace.json     # marketplace 清单(使仓库可被 /plugin 安装)
├── scripts/
│   ├── __init__.py
│   ├── postprocess.py       # 编排器/CLI 入口,驱动注册表
│   ├── textio.py            # 换行符保留读写(CRLF/LF 逐字节还原)
│   ├── verifier.py          # 聚合各 fixer 的 detect,输出带行号 Issue 清单
│   └── fixers/
│       ├── __init__.py      # 注册表:register / all_fixers / select / default_order
│       ├── base.py          # Issue / Fixer 协议 + split_zones 共享保护区
│       ├── fffd_restore.py  # U+FFFD 从 MinerU content_list JSON 骨架唯一还原(file_based)
│       ├── table.py         # HTML 表格 → Markdown 表格
│       ├── table_flatten.py # 合并单元格表展平(opt-in 草稿 + 标记)
│       ├── chem_formula.py  # 化学式下标(opt-in,周期表校验)
│       ├── math_delim.py    # <eq>/\(...\)/\[...\]/$ 定界符 + \tag 缺陷 + 降级/乱码 detect
│       ├── ocr_cleanup.py   # 确定性 OCR 噪音(A 类)+ 连字词典 + 错形小词典 + U+FFFD/控制字符
│       ├── algorithm.py     # mineru-algorithm div 转换(含数学 run 转正文)
│       ├── code_fence.py    # 未包代码块的代码识别包块(围栏感知)+ 结构/ipynb 碎片 detect
│       ├── url_join.py      # 同行断 URL 接合(跨行只报)
│       └── images.py        # 图片复制与引用重写 + 图-图注配对/图包审计/占位符
├── tests/                   # pytest 单元测试(镜像 scripts 结构)
├── .gitignore
├── .gitattributes
└── LICENSE                  # MIT
```

### 2.2 修复器（fixer）协议与注册表

每个修复器是 `scripts/fixers/` 下的一个模块，实现统一协议：

- `run`:修复函数。文本类签名为 `(text) -> text`;文件系统类（`file_based=True`，如 images）签名为 `(md_path, source_dir, out_dir_name="images") -> None`
- `detect`:体检函数，返回 `list[Issue]`(`Issue(fixer, line, message)`，行号供 Agent 定位）
- `default_on`（默认 `True`）:`False` 表示 opt-in 修复器——默认流水线不跑，仅 `--fixers` 显式选中时执行（v2 起 chem_formula 为 opt-in）

注册表（`fixers/__init__.py`）:
- `register(fixer)`:新修复器 = 新文件 + 一行注册
- `default_order()`:固定执行序 `["table", "chem_formula", "math_delim", "ocr_cleanup", "algorithm", "code_fence", "url_join", "images"]`，新修复器显式选位，不搞拓扑排序
- `select(ids)`:按 `default_order` 过滤出选中修复器（供 `--fixers`/`--skip`)
- 每个修复器可独立调用：`python -m scripts.fixers.<name> <file.md>`

### 2.3 共享保护区（zones)

`fixers/base.py` 的 `split_zones(text) -> list[(kind, segment)]` 是唯一词法切分器，所有文本修复器复用。保护区（绝不修改）:code_block、inline_code、math(`$...$`/`$$...$$`)、eq、image、link、url、html。修复器只在 `text` 段（及各自指定的段，如 math_delim 处理 eq 段）操作。

### 2.4 数据流

```
用户输入 (任意来源的 .md)
    ↓
python -m scripts.postprocess xx.md [--fixers a,b] [--skip c] [--images-dir PATH] [--images-out-dir NAME] [--in-place] [--verify] [--dry-run] [--issues-json FILE]
    ↓
按 default_order 跑选中的文本修复器(text→text,写回,逐 fixer 打印 applied/no change 摘要)
    ↓
跑文件系统修复器(images,复制+重写引用到 --images-out-dir)
    ↓
verifier 聚合各 fixer.detect → 带行号 Issue 清单(洪峰折叠;化学机会提示)
    ↓
退出码 0/1/2;2 时 Agent 按清单做语义修复
    ↓
(可选,用户显式同意)公式语义审查:模式级,只报告不改
    ↓
输出:修复后 .md + images/;引导移入 Obsidian vault
```

## 3. 混合式分层定位（地基）

| 层 | 承担者 | 职责 |
|---|---|---|
| 机械修复（约 90%) | 确定性 Python 修复器 | 表格、图片路径、定界符、确定性 OCR 噪音——量大、无歧义、保护区敏感 |
| 语义修复（约 10%) | Agent | 上下标语义、断句、OCR 误判（希腊字母、文本/数学判定、代码内错误） |
| 接口 | verifier + 退出码 2 | 聚合各修复器的 detect，输出带行号 Issue 清单给 Agent |

**钉死的边界**:fixer 只修"机械可判"的（词法位置可判定、规则唯一、绝不误伤）；语义重建永远归 Agent，不进 fixer——防止未来往 fixer 里塞语义规则、重踩误伤的坑。

## 4. 各修复器设计

### 4.1 table

HTML `<table>` → Markdown 管道表格（stdlib HTMLParser，首行作表头）。单元格内 `$...$` 公式原样保留。detect：逐行报残留 `<table>`。

**合并单元格（rowspan/colspan)——不静默误改**：Markdown 表格不支持合并单元格。`_TableParser` 检测到任一 `<td>/<th>` 带 `rowspan` 或 `colspan` 时，**不转换该表**，保留原 HTML 并报 detect 警告（带行号；v2.1.0 起文案补充"HTML 表内 `$...$` 在 Obsidian 不渲染"——HTML 表是保护区，其内公式 MathJax 看不到）。告警后由 Agent 按"三档框架"修复（见 §6.3 Workflow):
1. **展平表头**（首选）：多级表头合并为单行复合列名，跨行单元格向下复制填充——信息无损时优先
2. **拆成多个表**：按主表头拆成几个独立单层表——展平后列名过冗时用
3. **保留 HTML + 注明**（兜底）：无法无损转换时留 HTML，上方注明"本表含合并单元格，建议查看原 PDF"
Agent 在框架内按文义选档，不发明其他转法。

### 4.1.1 table_flatten（合并单元格表展平，v2.1.0 起 opt-in）

**默认不启用**（`default_on=False`，经 `--flatten-merged-tables` 开启）：MinerU 的 rowspan/colspan 数据本身可能错位（MoE稀疏门控 实测警告），展平产物是**草稿**而非成品。启用后，`table` 保留为 HTML 的 span 表全部经本 fixer 展开为 Markdown 管道表：

- **span 网格展开**：每单元格解析 (text, rowspan, colspan)；rowspan 文本向下填充、colspan 向右填充，构建完整矩形网格（表内公式 `$...$` 原样保留——这正是保留 HTML 的痛点：公式在 Obsidian 不渲染）。
- **表头重建**：表头行数 = 第 0 行任一格的 span 覆盖到的最大行（无则 1）；colspan-only 组表头（B026 表11 形态：组标签行 + 列标签行）识别为 2 行。多行表头按列纵向拼接非空文本（空格连接）为复合列名（`未标准化系数 B`）；同名列加序号（`乙醇转化率 排序 (2)`）；空列名补 `列N`。
- **草稿标记**：每个展平表上方加 `<!-- auto-flattened from merged-cell table — verify against PDF -->`，detect 逐表报 `flattened merged-cell table (draft) — verify against PDF`——**必须对账**（B007 表8 回归系数表、B026 表11 排序表两个真实 fixture 有测试与人工核对版）。
- **平衡**：MoE稀疏门控 要求保守（span 数据错位风险）vs 2021B 要求半成品可用（三线表多）——opt-in + 标记 + 对账指令是两者的交点，D8。

### 4.2 chem_formula（v2.0.0 起 opt-in）

化学式加下标：`SiO2`→`$SiO_{2}$`、`C6H12O6`→`$C_{6}H_{12}O_{6}$`。**自 v2.0.0 退出默认集合**（`default_on=False`）——默认流水线（CS/AI/数学/物理）不跑它，误伤面归零；化学/材料文档凭 verifier 的**化学机会提示**显式 `--fixers chem_formula` 开启。

**判定 = 封闭集合 + 形态（D3/D4）**：token 被包下标须同时满足
1. **周期表校验**：token 的全部字母可贪心切分为 118 元素符号（大小写敏感；单遍左到右优先 2 字母、失败回退 1 字母，不回溯——比全回溯更保守，`BRCA`=Br+Ca 类被拒）
2. **数字必需**：至少含一个数字（无数字=无下标可加；`SiC`/`SiLU`/`XRD` 全拒）
3. **连字符锚定**：前导字符不是连字符（`DeepSeek-V3` 不碰）

效果：`GSM8K`/`MATH500`/`AIME24`/`GPT2`/`MoE`/`LoRA`/`FLOPs`/`LLMs`/`APIs`/`Sv2`/`SiC`/`BRCA1`/`IL6`/`COX2` 全拒——v1 时代 `--skip chem_formula` 的两大理由（数模/LLM 误伤）从构造上消失。周期表是物理钉死的封闭集合，永不增长——这是脚本内唯一白名单（D4）。多位数下标带花括号（修 v1 局限：`C_{6}` 而非 `C_6`）。

**残余漏网 → 低置信复核网（Task 7）**：周期表也杀不掉的只有"单元素字母+纯数字下标"形（`$V_{3}$`/`$K_{3}$`/`$C_{4}$`——可能是变量下标而非化学式）。chem_formula 被选中时，verify 扫描 math 段逐条报 `low-confidence wrap`，交 Agent 对照原文判断。量小不报洪。（正则花括号可选：fixer 产出带花括号形态，手写无花括号形态同样覆盖。）

**ML/AI 术语提示保留（detect）**：`_ML_LIKE_RE` 对仍裸漏的可疑 token（如 `GPT2`）提示"possible ML/AI term (left bare by periodic-table validation)……wrap manually only if it is a real formula"——只列词上报，不自动改。

**化学机会提示（verifier 侧，替代 v1 的 doc_profile_hint）**：默认集跑完后，若正文区（text 段）通过周期表校验的**不同**公式形态 token ≥3 个，折叠成一条提示：措辞按化学上下文证据（封闭正则小表：中文词"溶液/反应/材料/化学"、短语 `mol/L`、缩写 XRD/SEM/TEM、英文词 `\bchemical\b`/`\breaction\b`；不能用裸 `"L"` 或 `"mol"` 子串——前者会被任何 LLM 文档平凡命中，后者命中 "molecular"）命中与否分两档（"likely a chemistry document" / 中性措辞）。chem_formula 被显式选中时不出此提示（已由 fixer 本体处理）。

### 4.3 math_delim

定界符统一为 Obsidian 认的 `$...$`:
- `\[...\]` 显示公式 → `$$...$$`（v2.1.0：Obsidian 按 CommonMark 剥掉 `\[` 的反斜杠，MathJax 看不到公式——T1 24 处实证；`detect` 对残留 `\[`/`\]` 报"leftover"）
- `<eq>...</eq>` → `$...$`
- 成对 `\(...\)` → `$...$`
- 断裂 `\(...`（无配对 `\))`→ 降级为纯文本（杜绝 ParseError)
- `\tag` 缺陷 detect:`\tag{...}` 内括号不配平、混入游离括号、裸 `~`（数学模式下渲染为空格，公式编号区间误拼）

只在 `text`/`eq` 段操作，不触碰已有 `$...$` 数学内容；code fence 内不动。

**garbled 乱码判定的修正（v2.1.0）**：`_bare_eq_count` 计数前先剔除 `_{...}`/`^{...}` 花括号内容——`\sum_{i = 1}^{n}` 的 `i = 1` 是下标不是乱码（MoE稀疏门控 6 条误报清零）；真乱码 `$= 1 = 1 1$` 仍报。

**数字区间 `\~`（v2.1.0）**：text 段内 `(?<=[\d%])\~(?=[\d%])` → `~`（2021B 实样 `36%\~41%`——计划原定 `(?<=\d)` 与实样不符，`%` 语境一并覆盖）；字母语境 `X\~B(` 不动，仍走降级 detect。

**`$` 配对检查（verifier 侧）的两个修正**:
- **转义美元符号 `\$` 跳过**：金额写法 `\$2.03` 不计入 `$` 配对——扫描时排除被反斜杠转义的 `\$`，不再误报"Unpaired $ delimiters"。
- **未配对告警带行号**：记录首个未配对 `$`/`$$` 的行号与上下文，以统一 Issue 格式输出（此前只报"Unpaired $ delimiters"无位置）。

### 4.4 ocr_cleanup(A 类确定性 OCR 噪音）

只修"模式唯一、绝不误伤"的 OCR 噪音：

| 模式 | 规则 | 位置约束 |
|---|---|---|
| 白名单命令内字母空格 | `\mathrm { d r a f t }`→`\mathrm{draft}` | 白名单命令花括号内：`\mathrm \text \operatorname \mathbf \mathit \mathsf \textbf \textit` 及 `^{}` `_{}` |
| `f^{\backslash…*}` 变体 → `f^{*}` | 泛化正则（覆盖 `f^{\backslash *}`、`f^{\backslash^ {*}}`；`f^{\backslash a}` 不误伤） | math zone |
| 数字拆散（`0. 2 0`→`0.20`) | 删数字间空格 | **仅** ①`$...$` ②`$$...$$` ③白名单命令花括号内 |
| HTML 实体（`&gt; &lt; &amp; &quot;`) | 固定映射 | text + math zone（v2 起 math 区也替换，B157） |
| 多位数下标元组（`X_{1 16}`) | **不静默合并**：stash 保护后原样保留 | math zone |
| array 列说明符（`\begin{array}{r l r}`) | **豁免** letter-run 处理（stash/blank，v2.1.0，MoE 误报清零） | math zone |
| 数学区字母拆散（`a l l o w e d`→`allowed`) | ≥5 个单字母并跑合并；2 个（`x y` 变量对）不动 | math zone |
| ff 连字词典（`dificulty`→`difficulty` 等 24 条） | 封闭词典，词边界；**小写 + 首字母大写**变体都修（`Eficient→Efficient`），保留匹配形态；**专名风险条目豁免大写**（`ofer` 仅小写，人名 Ofer 不碰） | text zone |
| C0 控制字符（`\x00-\x08\x0b\x0c\x0e-\x1f`) | **直接删除**（md 中绝不合法，B026 U+000B 来自 `\vdots` 转义损坏）；code 区不动 | text + math zone |

**B 类（语义级）只做 detect 不改**：希腊字母 `??` 占位符；`X_{1 16}` 元组下标（报"space-separated numbers … review"）；3-4 字母并跑（`a b c`，报"letter-run … review"）；**U+FFFD 替换符**（`�`，报"restore from PDF"，同行一条）；**C0 控制字符**（修复器删 text/math 区，code 区修不到所以 detect 照报）；**正文错形小词典**（v2.1.0，封闭小表逐条注样本出处：`wtih→with`、`drouput→dropout`、`trillionparameter→trillion parameter`、`multiply-andadds→multiply-and-adds`（MoE稀疏门控 各 3 处）、`sof tmax→softmax`、`dropP rob→DropProb`（计划指定，样本未复现）——报 `suspicious word form: 'wtih' — maybe 'with' (review)`，**只报不改**，人名/专名不收）；**相邻 letter-run 聚合**（v2.1.0，math 段 3-4 run 与相邻 ≥5 字母标识符仅隔 `\_`/`_`/空白 → `possible same identifier: 'k t h' + 'excluding' (review)`——MoE 实证 `k t h \_ e x c l u d i n g` 是同一标识符被 OCR 拆开）。U+FFFD/控制字符只在 text/math 段报（修复后只剩 code 区可报）。

### 4.5 algorithm(mineru-algorithm div 转换）

MinerU 把算法/伪代码（及误圈的说明段落）打进 `<div class="mineru-algorithm">`。该 div 是 HTML 块，Obsidian 不渲染其内 Markdown/LaTeX，导致块内 `$...$` 公式也被关死。

处理：
- 拆掉 div 标签
- **锚点行**（`Algorithm N`/`算法 N` 标题、`Input:`/`Output:`/`输入:`/`输出:`、区块内编号步骤 `^\d+\.\s`、控制关键字 `for/foreach/while/if/elif/else/return/repeat/until/end/continue/define/synthesize/complexify/require/ensure`)→ 代码块
- **整段判定（v2）**：一个连续锚点 run 内**任一行含 `$`** → 整个 run 转正文（公式恢复渲染，B157）；无 `$` → 照常进 ` ``` ` 围栏（Agent World 的 Algorithm 1 合成单块）
- **其余行** → 回正文（`$...$` 恢复渲染）

实证依据：algorithm div 内**无真代码**(def/class/import 零命中），只有伪代码与说明文字；真代码 MinerU 走 ` ```python ` 代码块，归 zones 保护区，不经本 fixer。

### 4.6 code_fence（未包代码块的代码）

MinerU 偶尔把代码段降级为普通文本（缺 ``` 围栏，如 `import numpy`/`def f(` 直接成正文行）。与三线表不同：代码文本本身完整，只是缺围栏，"认出代码行并包块"是机械可判的。

**守"不确定就上报"原则，不试图囊括所有情况：**

- **围栏感知（v2 P0 修复）**：`_split_fence_runs` 把文本按 ` ``` ` 围栏切成 (in_fence, run) 段——已有围栏内容 **fix/detect 全部透传/跳过**（修 v1 数据破坏 bug：往已有围栏内插围栏）；未闭合围栏其后所有行保守视为 fenced。行号按段偏移换算。
- **高置信才包块（仅 fence 外 run）**：连续 ≥2 个完整锚点行（行首 `import`/`from..import`/`def (`/`class `/`print(`/`return `/`#include`/`plt.`/`for .. in .. :`)，且行内无 `$`、无中文句子）→ 包成 ` ```python `（默认 python；含 `#include`/`std::` 则 cpp，不做更多语言猜测）。
- **以下任一情况只 detect 上报、不包块**：锚点行混入 `$...$`（公式与代码纠缠）；锚点行混入中文句子（可能是正文提及代码）；孤立单锚点行；语言/边界不明确。
- 上报格式：`[code_fence] line N: suspected code block (needs agent review)` + 首行摘录，交 Agent 判断。
- **代码结构三检测（v2，detect-only）**：①围栏开标签 ∈ `{prolog,txt,makefile,lua}` 且块内 ≥2 行命中锚点正则 → "fence labeled 'X' but content looks like python"（K3 形态）；②闭围栏后 ≤3 行（仅空行/短行间隔）又现开围栏 → "adjacent fragmented fences (possible pagination split)"；③围栏块 ≥8 行、含 `def |for |if ` 且所有行首无缩进 → "code block has no indentation (possible indent loss)"。全部带行号、只上报。
- **ipynb 碎片检测（v2.1.0，detect-only）**：围栏外 ≥2 行命中 `"cell_type"`/`"source":`/`^\s*"n",?$` → "suspected Jupyter notebook fragments — rebuild from original ipynb (converter-layer task)"——转换器把原始 ipynb JSON 行倾倒进 md，逐行重建是转换层的事，不包块。

### 4.7 images(file_based=True)

图片**复制**（非移动）到 `.md` 同级目录，并把本地引用重写。外部 URL(http/https）不动。

- 图源目录是参数（`organize(md_path, source_images_dir, out_dir_name="images")`)，可用 `--images-dir` 指定（如 MinerU 图包位置）；**输出目录名**用 `--images-out-dir NAME` 指定（默认 `images`，K3 解析需要 `Image/`），引用重写同步用该名。
- **organize 三连修（v2.1.0）**：①`mkdir(parents=True, exist_ok=True)`（谷歌MoE 深层目录 WinError 3）；②引用一律重写为**相对 md 的 POSIX 路径**（`os.path.relpath` + 正斜杠 + `/name`，绝对引用根除——`--images-out-dir` 传绝对路径也产出可移植引用）；③**只重写实际复制成功的文件的引用**（training-04：图本就在 md 旁、无图源目录时引用被改断；未复制的引用原样保留，missing-image detect 兜底）。
- **引用正则容忍一层嵌套括号（v2.1.0，三连环根因）**：`_MD_IMAGE_RE` 与 zone 正则的路径部分从 `[^)]*` 改为 `(?:[^()]|\([^()]*\))*`——目录名含 `(flash实测)` 曾致路径截断 → missing-image 误报 21 条 + 图包审计目录被污染（19 张孤儿代码截图漏报）；link zone 同修（wikipedia 式 URL）。
- **边界**：只能修"引用路径"，不能恢复图片本体缺失。图片缺失时 verifier 报告并引导用户用能导图的转换器（如 MinerU Standard API）重转。
- detect：
  - 报缺失图片（带行号）
  - **图文分离 detect**：图片引用出现在第一个 `#` 标题**之前** → 上报 Agent（不自动挪位）
  - **图-图注配对（v2，K=3；v2.1.0 加簇收敛）**：`_CAPTION_WINDOW=3`（覆盖空行变体、防跨图串扰，detect-only 宁紧）。**图片簇**：相邻图片行（行距 ≤2）构成一簇；簇内任一图片 ±3 内有图注 → 整簇算配对（ZEDA：图→图→caption 共享、图→标签行→caption）。未配对时每张图报 "image has no caption … possible orphan/misplaced figure"，**附最近图注距离**（"nearest caption is N lines away"）；②图注行 ±3 内无图 → "caption has no image … possible orphan caption"；③配对确认的图注编号序列非单调 → "possible figure order anomaly … verify visually"（整条一次）。图注识别：英文 `Figure N:`/`Fig. N`/`Fig N`；中文 `图 N` 且行长 ≤40 且不以 `。` 结尾（排除"图 5 给出了……。"正文提及）
  - **图包未引用图审计（v2）**：读 `<md_dir>/images/`（不存在则静默跳过），集合差 `图包文件名 - 被引用 basename`，每个未引用文件一条"unreferenced image in bundle (possible missing figure or formula fragment)"；>15 条由 `_format_issues` 自然折叠。只读不写
  - **轴标签误标（v2）**：`^#{1,6}\s*\S{1,12}/(元|秒|米|千克|个|件|%|kg|cm|mm|m|s)$` → "possible axis label mis-tagged as heading"（B196 `## 利润值/元`）
  - **image 占位符（v2.1.0）**：`<!--\s*image\s*-->` → "image placeholder (converter did not extract images) — extract from PDF or re-convert with an image-producing API"（MoE稀疏门控 4 处——不再被误读为"孤儿 caption"）

### 4.8 url_join（同行断 URL 接合）

MinerU 偶发把 URL 断成"URL + 空格 + 续段"（Agent World：`arxiv.org/abs/ 2601.05808`）。

- **fix（同行才接）**：`url` 段以 `/`、`.`、`-` 结尾，且紧随的 `text` 段以 ` +<tok>` 开头；`<tok>` 全为 URL 字符集（`[A-Za-z0-9._~:/?#@!$&'()*+,;=%-]`）、含 ≥1 个 `[0-9./-]`、不含 CJK → 合并为完整 URL。其余不动。
- **detect（跨行只报）**：URL 段后随 text 段以 `\n +<url-charset tok>` 开头 → "possible URL split across lines — review"（交 Agent 判断续段是否属于 URL）。
- code 区内 URL 天然不受影响（code_block 是保护区）。

### 4.9 fffd_restore（U+FFFD 从 content_list JSON 恢复，v2.1.0）

MinerU 输出目录带 `content_list_v2.json`（md 的文本源头）；md 里的 `�`（U+FFFD）有时能在 JSON 片段里找回原字符。本 fixer **file_based**、`default_on=True` 但无 `--content-list` 时 no-op（默认流水线零影响）；执行序在**最前**（§2.4：ocr_cleanup 合并空格后会破坏对齐，必须在任何文本修复器之前跑，postprocess 开头特殊处理：先重写文件再读文本继续）。

- **片段提取**：兼容平铺 list（B007）与分页 list[list]（ZEDA）两种结构；遍历各 item 的 `content.paragraph_content`/`title_content`，text 与 equation_inline 的 `content` 字段**按段落拼接**为一条片段。
- **骨架唯一对齐（绝不臆造）**：对每行含 `�` 的 md 行，生成骨架（去掉 `�`、规范化空白）；在 JSON 片段中找骨架**唯一**匹配——片段去空白后与骨架一致（整条片段必须被行耗尽），且每个 `�` 对应片段中一段**唯一**的连续非 `�` 字符（gap，≤12 字符）可回填。同一片段内多种 gap 切分或 ≥2 个片段候选 → 保留 `�`。对齐用带 memo 的 DP 计数（cap=2 提前退出；递归深度有界 = 行长度）。
- **detect**：无 `--content-list` 且 md 含 `�` → 一条提示 "N line(s) contain U+FFFD … pass --content-list PATH"；有 JSON 时由 postprocess 报残留未对齐行（"X U+FFFD line(s) could not be aligned … restore manually"）。
- **实测边界**（ZEDA，flash 实测）：md 与 JSON 的 `�` 同位丢失（JSON 是 md 源头），唯一对齐全部 no-op，机械还原率 **0/85**——反馈声称"85 处全可还原"不实（人工修复版靠 PDF 语义知识补 `$N$`/`$h$` 等）。还原率以实测为准写入回归报告；算法对"JSON 完好、md 后损"的文档仍有效（合成 fixture 全过）。

## 5. 缺陷画像（实证）与修复归属

综合多份真实产物（材料类 pdf、数模 docx、AI/ML pdf、物理论文）:

| MinerU 输出形态 | Obsidian 渲染 | 归谁修 |
|---|---|---|
| `$...$`/`$$...$$` 完整 | ✅ | 不用修 |
| 表格内公式（HTML 表格里 `$...$`) | ✅ 表格转换顺带 | 不用修 |
| 漏判化学式裸文本（C4、SiO2) | ❌ 无下标 | chem_formula |
| `<eq>...</eq>` | ❌ | math_delim |
| OMML 碎片 `\(...\)` 不配对 | ❌ ParseError | math_delim |
| `\tag{N)~(M}` 编号区间误拼 | ❌ | math_delim(detect)→ Agent |
| 确定性 OCR 噪音（§4.4 A 类） | ❌ 噪音 | ocr_cleanup |
| 希腊字母 → `??` 占位符 | ❌ | ocr_cleanup(detect)→ Agent |
| 文本误识别为数学（`"of"`→`$\Omega$`) | ❌ | Agent(detect 提示） |
| 代码块内 OCR 错（`lv`/`lw`、中文标点） | ❌ | Agent（代码块是保护区） |
| algorithm div 块 | ❌ 整块不渲染 | algorithm |
| 上下标信息丢失（Sv2→$Sv^2$) | ⚠️ 语义错 | Agent(detect 驱动） |
| 三线表未被识别为表格（输出成普通文本） | ❌ 列对不齐 | Agent（用户反馈驱动；结构信息已丢，手工重建，不做 detect/fixer) |
| 代码段降级为普通文本（缺 ``` 围栏） | ❌ 代码不渲染 | code_fence（高置信包块；模糊即上报 Agent) |
| 图片本体缺失（MinerU 未导图） | ❌ | 引导用户重转（fixer 修不了本体） |
| 已有围栏内被二次包块（v1 数据破坏） | ❌ 代码裂开 | code_fence（v2 围栏状态机，已有围栏零改动） |
| 围栏误标语言（prolog/txt/makefile 装 python） | ❌ 语法高亮错 | code_fence(detect) → Agent |
| 围栏碎片化（分页切碎） | ⚠️ | code_fence(detect) → Agent |
| 代码块缩进丢失 | ⚠️ 语义错 | code_fence(detect) → Agent |
| 行内公式降级为文本（`X\~B(`、`0<p<1`) | ❌ 公式不渲染 | math_delim(detect) → Agent 包 `$...$` |
| 乱码公式内容（`= 1 = 1`） | ❌ | math_delim(detect) → Agent 对照 PDF |
| URL 断行（`arxiv.org/abs/ 2601.05808`) | ❌ 链接断 | url_join（同行接合；跨行 detect → Agent) |
| U+FFFD 替换符 / C0 控制字符 | ❌ 字符缺失 | ocr_cleanup(detect) → Agent 对照 PDF 恢复 |
| ff 连字丢失（dificulty） | ❌ 拼写错 | ocr_cleanup（封闭词典自动修） |
| 数学区字母拆散（`a l l o w e d`) | ❌ | ocr_cleanup（≥5 自动合并；3-4 detect → Agent) |
| 多位数下标元组（`X_{1 16}`） | ⚠️ | ocr_cleanup（不合并 + detect → Agent) |
| 图与图注分离（孤儿图/孤儿图注） | ⚠️ 图注错位 | images(detect) → Agent 按文义挪位 |
| 图注编号乱序 | ⚠️ | images(detect) → Agent 视觉核对 |
| 图包含未引用图（公式碎片图） | ⚠️ | images(detect) → Agent |
| 轴标签误标为标题（`## 利润值/元`) | ⚠️ | images(detect) → Agent |
| 图片路径含括号被截断（`(flash实测)` 目录） | ❌ missing-image 误报 | images（正则容忍一层嵌套括号） |
| 跨行 `0<\theta … r>0` 被拼成 html zone 吞公式 | ❌ 公式消失 | base（html zone 须字母/`!` 开头且单行） |
| `\[...\]` 显示公式（Obsidian 剥反斜杠） | ❌ 公式不渲染 | math_delim → `$$...$$` |
| `36%\~41%` 数字区间 | ❌ `\~` 异常 | math_delim（text 段数字/百分号语境 → `~`） |
| U+FFFD 且同目录有 content_list_v2.json | ❌ 字符缺失 | fffd_restore（骨架唯一对齐；无 JSON 时 detect 提示） |
| 合并单元格表（rowspan/colspan） | ❌ HTML 不渲染（表内 `$...$` 更看不到） | table(detect) → Agent 三档；或 `--flatten-merged-tables` 草稿展平 |
| `<!-- image -->` 占位符 | ❌ 无图 | images(detect) → 引导重转 |
| 正文错形（`wtih`/`drouput`/`trillionparameter`） | ⚠️ 拼写错 | ocr_cleanup(detect，错形小词典) → Agent |
| 标识符被拆开（`k t h \_ excluding`） | ⚠️ 语义错 | ocr_cleanup(detect 聚合提示) → Agent |
| ipynb JSON 行倾倒进正文 | ❌ 内容不可读 | code_fence(detect) → 转换层重建 |

## 6. SKILL.md 设计

### 6.1 Frontmatter

v2.0.0 起 description 以 tables/math/code/figures 渲染症状为主（触发面即产品面），化学式降为可选（opt-in 修复器），保持 "Use when..." 触发式写法、≤500 字符：

```yaml
---
name: obsidian-md-fixer
description: Use when a Markdown file converted from a PDF or Word document (especially by MinerU, but also pandoc/Marker/any converter) shows tables as raw HTML, broken \( ... \) math delimiters causing ParseError, code blocks missing their ``` fences or mislabeled, images missing or misplaced with orphan/out-of-order captions, OCR artifacts like U+FFFD or split words, or unreferenced image files — in Obsidian. Chemical subscripts (SiO2) are handled by an optional fixer.
---
```

### 6.2 触发机制（SDO 规则）

skill 是否被触发完全由 `description` 决定：
- 以 "Use when..." 开头，只写触发条件（症状、场景），第三人称
- **绝不写功能或流程摘要**——写了流程，agent 会只按 description 行动而不读正文
- 控制在 500 字符内（frontmatter 总上限 1024)
- 关键词用 agent 会搜索的词：症状（raw HTML、not rendering、ParseError)、工具名（MinerU、Obsidian)、文件类型（PDF、Word、Markdown)

### 6.3 正文结构（≤500 词）

1. **Overview**:1-2 句定位（修复已转换 Markdown 的表格/公式/图片渲染）
2. **When to Use / When NOT to Use**：症状列表 + §1.3 排除条件
3. **Quick Reference**：命令速查（见 §8)，必须 `python -m`
4. **Workflow**:agent 实际执行的指令
   - 确认输入是 `.md`（其他格式提示先转换）
   - 跑命令（默认 `<name>_fixed.md`，不覆盖原文件；`--in-place` 先建 `.bak`)；默认集即 CS/AI/数学/物理安全配置，**不再需要 --skip 魔法**
   - 化学机会提示：若 verifier 报 chem-opportunity 且文档确为化学/材料 → `--fixers chem_formula` 重跑；顺带处理低置信 wrap 清单（对照原文还原变量名）
   - 退出码处理：0 报告产物；1 报告错误；2 报告产物并逐条列 verifier issue
   - 图片缺失：询问用户图包位置 → `--images-dir` 重跑；无图包则引导重转
   - **图片审计（v2）**：按 unreferenced/pairing/order-anomaly issue 处理；可 Read 图片文件视觉核对图序
   - 语义 issue(Agent 修）:detect 标记的上下标、OCR 误判、U+FFFD（对照 PDF 恢复）、URL 断行、行内公式降级（包 `$...$`，注意中文区间 `1\~8` 不误包）、三线表
   - 汇报产物路径，提醒在 Obsidian 打开确认；产物在 vault 外则建议移入
5. **可选：公式语义审查**（三条硬规则：显式触发、模式级目标、只报告不改）
6. **Common Mistakes**：直接跑 `python scripts/x.py`、覆盖原文件、手改 HTML 表格、**继续传 `--skip chem_formula`**（v2 默认已不含，无意义）、无视低置信 wrap 清单、在此转换 PDF/Word

## 7. README 设计

- 简介段：修复已转换 Markdown;"零依赖零 token、适用任何 md、不访问网络";**定位段常青**——默认面向 CS/AI/数学/物理论文深度优化、化学式下标为可选修复器（不提版本号，版本叙事归 Release notes）
- 依赖：Python 3.10+;pytest 仅测试需要
- 安装与更新：**方式一 plugin marketplace**(`/plugin marketplace add` → `/plugin install`，或 skills 管理点更新，无需 clone);**方式二手动 clone + `git pull`**
- 使用：全部 CLI flag 示例（含 `--fixers chem_formula`、`--images-out-dir`）；退出码说明
- 修复器做了什么：全部修复器表格（含 opt-in 标注与 detect 能力）+ 机械 vs 语义边界 + 换行符保留说明
- 数据安全：默认不覆盖原文件、`--in-place` 先建 `.bak`、重要文档建议备份

## 8. 使用方式

```bash
# 修复 Markdown(默认输出 <name>_fixed.md,不覆盖原文件;打印每 fixer 变更摘要)
python -m scripts.postprocess paper.md

# 化学/材料文档:显式开启化学式下标(v2 起为 opt-in)
python -m scripts.postprocess paper.md --fixers chem_formula

# 只跑部分修复器
python -m scripts.postprocess paper.md --fixers table,images

# 图片在别处(如 MinerU 图包),指定图源目录
python -m scripts.postprocess paper.md --images-dir "D:/mineru输出/images"

# 输出目录名(如 K3 解析需要 Image/;引用重写同步)
python -m scripts.postprocess paper.md --images-out-dir Image

# 原地修复(自动创建 .bak 备份)
python -m scripts.postprocess paper.md --in-place

# 只校验不修改(语义修复后验证;0=干净,2=仍有 issue,不写文件)
python -m scripts.postprocess paper.md --verify

# 预览修改量(跑修复器但不写文件,报告每个 fixer 会改几处;大文件先评估)
python -m scripts.postprocess paper.md --dry-run

# 结构化 issue 输出(修复/校验后写 issues.json,供 Agent 可靠逐条处理)
python -m scripts.postprocess paper.md --issues-json issues.json

# 单独跑一个修复器
python -m scripts.fixers.table paper.md
```

**退出码**:`0` 成功；`1` 失败（无产物）;`2` 成功但验证有警告（产物已生成，带行号 issue 打印到 stderr，洪峰折叠，末尾打印 re-run 提示）。

**`--dry-run`**：跑全部选中修复器但**不写任何文件**，报告每个修复器会改动的处数与 detect 的 issue 数；用于大文件修复前预览影响面。

**`--issues-json <路径>`**：把 verifier 的结构化 Issue 列表（`[{fixer, line, message}]`）写入指定 JSON 文件，供 Agent 逐条可靠处理（替代解析 stderr 字符串）。

## 9. 测试与开发流程

遵循 superpowers 方法论，三条铁律：
1. **脚本开发 = TDD**：先写失败测试（RED)，看它失败，再写最小实现（GREEN)，然后重构
2. **SKILL.md 开发 = 文档版 TDD**：先跑基线场景记录 agent 自然行为，再写 SKILL.md，再堵漏
3. **完成声明前必须验证**：任何"完成/通过"的声明，都必须有当次运行的命令输出作证据

### 9.1 单元测试

每个 fixer 的 fix + detect 各有测试；注册表、编排器（各 flag)、zones、中文/空格路径、真实缺陷 fixture(`\tag{3) \(\sim (6)\}`、`\tag{7)~(10}`、algorithm div、确定性 OCR 样本）。

### 9.2 集成测试

用真实转换产物端到端测试，在 Obsidian 中人工确认渲染。**测试用文档不得使用有版权的已发表论文**（自造或 CC/开放获取），且一律不入库（.gitignore)。

## 10. 隐私与安全

- 不读取任何密钥、不访问网络，纯本地文本处理
- 不硬编码用户路径、真实姓名、邮箱；git 提交身份用 GitHub noreply 邮箱
- PDF/测试文档、`output/`、`docs/superpowers/`（过程产物）不入库（.gitignore)
- 默认输出 `<name>_fixed.md`，不破坏原文件

## 11. 错误处理

| 场景 | 处理 |
|---|---|
| 输入文件不存在 | stderr 提示，退出码 1 |
| 非 .md 输入 | stderr 提示，退出码 1 |
| 图片目录缺失 | 跳过图片整理，verifier 报告 |
| 验证发现问题 | 打印带行号 issue（洪峰折叠），退出码 2（产物已生成，属警告） |

## 12. 发布与分发

### 12.1 plugin marketplace（主要分发方式）

仓库含 `.claude-plugin/plugin.json`（名称/version/作者）与 `.claude-plugin/marketplace.json`，使本仓库可被 Claude Code 作为 marketplace 安装。用户：
```
/plugin marketplace add zheng-phy/obsidian-md-fixer   # 一次性
/plugin install obsidian-md-fixer@zheng-phy           # 安装
# 之后点"更新"即可拉新版,无需 clone
```

### 12.2 版本与 Release 流程

每次迭代：
1. 改代码 + 测试
2. `.claude-plugin/plugin.json` 的 `version` 递增（minor 功能、patch 修复）
3. commit + push + 打同名 tag + push tag
4. GitHub 网页发 Release（写变更说明，作为迭代日志）

`plugin.json` 的 version ↔ git tag ↔ GitHub Release 三者对齐，用户点更新时按此识别新版。

## 13. 后续优化方向

- 图片 hash 名重命名选项（`--rename-images` → figure-1.jpg)
- 批量处理整个目录（待真实需求驱动，YAGNI)
- 自定义输出后缀（`--suffix`)
- ocr_cleanup 白名单/模式按需扩充（严守 A 类确定性边界）
- 无图注场景的图序错序视觉检测：机械信号不存在（无图注行可锚定），归 Agent 视觉核对——不设分类器（D5）；若未来样本证明图包内文件 mtime/页码可作锚点，再评估
- 连字词典扩充（严格守"词形绝不合法"准入;拿不准不收）

## 14. v2.0.0 转型决策记录

> 本节蒸馏自 `docs/superpowers/plans/2026-07-31-v2.0.0-deep-adaptation-plan.md` §2（决策讨论的完整证据与用户拍板过程见该文）。v2.0.0 定位转变：**不再用适配化学的机制修复 CS 和数理文章，转型为对 CS/AI/数学/物理论文深度适配的修复 skill**。

### D1 转型里程碑（用户拍板）

发布 v2.0.0。README 定位段常青（不提版本号）——"默认面向 CS/AI/数学/物理论文，化学式下标为可选修复器"；版本变迁叙事归 Release notes；本节为 DESIGN 内的决策记录。

### D2 chem_formula 退出默认集合（默认关闭，opt-in）

依据：用户真实语料 = LLM/CS/数学/物理（化学论文仅最初一篇）；误伤 = 静默数据损坏，漏修 = 可见可回退，**风险不对称**。默认流水线即 CS/数理安全配置，误伤面归零，无需任何"自动跳过"魔法。化学用户凭化学机会提示（D5）显式 `--fixers chem_formula` 开启。

### D3 周期表校验替代排版模式匹配

开启 chem 后，token 被包下标须同时满足：①全部字母可切分为 118 元素符号（大小写敏感，贪心切分——比全回溯更保守）②至少含一个数字 ③前导字符不是连字符。**周期表是物理钉死的封闭集合，永不增长——这是唯一白名单。** 效果：GSM8K/MATH500/GPT2/MoE/LoRA/FLOPs/LLMs 全拒；`Sv2`（`v` 非元素）、`SiC`（无数字）全拒——当年 `--skip` 的两大理由从构造上消失。残余漏网只有"单元素字母+数字"形（V3/K3/C1/F2）→ 进低置信复核清单交 Agent。顺带修 v1 局限：多位数下标 `C6H12O6` → `$C_{6}H_{12}O_{6}$`。

### D4 脚本管形态，Agent 管词汇（反臃肿总则）

LLM/CS 新名词月月增长，任何"已知 ML 名词名单"都会臃肿且永远追不上。钉死：**脚本只认形态与封闭集合**（周期表、连字词典、URL 字符集、稳定上下文词）；开放词汇判断全部归 Agent——Agent 的模型知识天然认识新模型，它就是活的名词数据库。画像扫描全部脚本化（正则计数），零 token 消耗；Agent 只读 issue 清单与被标记行。

### D5 症状驱动，不设领域分类器

"深度适配"不依赖"判断这是哪类论文"：所有新检测器都是症状驱动（U+FFFD 出现才报、URL 断行才报、图包有未引用图才报），症状不存在则输出为零；全部 detect-only，无误伤风险，全量对所有文档跑。issue 清单本身就是为该文档定制的体检报告。原"画像"瘦身为一项：**化学机会检测**（正文区通过周期表校验的公式形态 token ≥3 个 → 一行折叠提示，措辞按化学上下文词有无分两档）。生物等未适配领域拿去跑构造上天然安全（BRCA1/IL6/COX2 被拒；HIF1 型漏网进复核清单），但不为其做专门适配（无样本，YAGNI）。

### D6 图-图注配对检测，K=3

v1.3.0 的"图在第一个标题前"检测方向正确（K3 样本实测命中）但信号偏窄。泛化：①图片 ±3 行内无图注 → orphan image；②图注 ±3 行内无图 → orphan caption；③配对确认的图注编号非单调 → possible order anomaly。K=3 依据：覆盖空行变体（图/空行/图注 = 间距 2，多空行 = 3）且防跨图串扰；detect-only 宁可偏紧。写成具名常量，后续凭样本证据再调。**不做**：自动挪位、子图自动拼接（语义，归 Agent）、无图注场景的错序检测（机械信号不存在，归 Agent 视觉；见 §13）。

### D7 发布形态与工作流（用户拍板）

单版本一次发布：功能分支 `feat/v2.0.0-deep-adaptation` 上按阶段分批 commit，不碰 main、不打 tag、不推送；主对话 review 通过后合并 main、plugin.json version ↔ tag ↔ GitHub Release 三者对齐。

## 15. v2.1.0 决策记录

> 本版修复 4 份新实测反馈（3 篇 MoE/LLM 论文 + 2 份 2021 国赛扫描版）暴露的缺陷，并把本机 skills 副本上两处未经 review 的增量加固后正式入库。执行计划见 `docs/superpowers/plans/2026-08-04-v2.1.0-implementation.md`。

### D8 本地增量 review：采纳 + 加固

本机 `~/.claude/skills/obsidian-md-fixer` 被另一 agent 改过两处（无测试）：
1. **`\[...\]` 显示公式转换**（`math_delim`）：T1 样本 24 处实证 Obsidian 按 CommonMark 剥掉 `\[` 反斜杠后 MathJax 看不到公式。**采纳**，补 `detect` 残留报出与全套测试；再加固：完整配对才转、`detect` 只报 fix 处理不了的残留（完整配对不报）。
2. **html zone 单行化**（`base.py` 的 `<[^>]+>` → `<[^>\n]+>`）：方向对（防跨行误吞）但**不够**——同行 `0<\theta<1 and r>0` 仍会被拼成伪 tag。**加固入库**：`</?[a-zA-Z!][^>\n]*>`（tag 必须字母或 `!` 开头且单行），training-04 现场 5 段被吞公式重见天日。

### D9 括号路径三连环根因

`(flash实测)` 目录名致图片引用在 `)` 处截断：①zone 正则 image/link 路径部分 `[^)]*` → 容忍一层嵌套括号 `(?:[^()]|\([^()]*\))*`；②`images.py` 的 `_MD_IMAGE_RE` 同修；③organize 引用重写为相对 POSIX 路径。症状链：missing-image 误报 21 条 → 图包审计目录被污染 → 19 张孤儿代码截图漏报，一次根除。

### D10 展平 opt-in 的平衡（MoE 保守 vs 2021B 半成品）

合并单元格表（rowspan/colspan）是 Markdown 结构外的事。MoE稀疏门控 实测警告 MinerU 的 rowspan 数据本身可能错位；2021B 的三线表又多到 Agent 手修不可持续。交点：`table_flatten` **opt-in**（`--flatten-merged-tables`）+ 每个展平表上方标记行 + detect 逐表"verify against PDF"——草稿可用，绝不冒充成品。fixture 用 B007 表8 / B026 表11 真实结构，期望输出人工核对后写死入库。

### D11 U+FFFD JSON 恢复的设计边界（唯一对齐，绝不臆造）

反馈声称"ZEDA 85 处 U+FFFD 全可还原"——实测不实：md 与 content_list_v2.json 的 `�` 同位丢失（JSON 是 md 的源头），骨架唯一对齐全部 no-op，机械还原率 0/85；人工修复版靠 PDF 语义知识补 `$N$`/`$h$` 等。设计边界钉死：**只有唯一对齐才回填**（片段整体耗尽 + 每个 `�` 唯一 gap），零匹配或 ≥2 候选一律保留 `�` 并报残留。算法对"JSON 完好、md 后损"的文档（合成 fixture）有效，实测率以回归报告为准——不与反馈数字对齐，只与数据对齐。

### D12 词典扩编与豁免（连字词典大写变体）

`efects`（DESI 20 处）/`eects` 入库；词典条目允许首字母大写匹配（`Eficient→Efficient`，ZEDA 24 处）并保留匹配形态；**专名风险条目豁免大写**：`ofer` 仅小写匹配（人名 Ofer 保护）。规则：连字词典可证"原词形绝不合法"才收（D4 总则的封闭集合）；错形小词典（`wtih` 等）只 detect 不改——修复是语义判断，归 Agent。
