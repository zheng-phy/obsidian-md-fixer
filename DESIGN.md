# obsidian-md-fixer 设计文档

> 本文档是当前版本的唯一权威设计说明，随迭代更新，不分版本章节。
> 原项目名 pdf-to-obsidian，v2 起改为纯修复向并更名 obsidian-md-fixer。

## 1. 项目概述

### 1.1 目标

一个平台无关的 AI Agent skill：修复**已转换**的 Markdown（来自 MinerU、pandoc、Marker 等任意转换器）在 Obsidian 中的渲染问题。

- 用确定性的 Python 修复器（fixer）完成机械修复
- 把语义级问题（上下标、断句、OCR 误判）交给 Agent 按行号清单处理
- 产出：一份修复后的 `.md` + 同级 `images/` 文件夹
- 不硬编码任何密钥或用户路径；纯本地处理，不访问网络

### 1.2 适用场景

- 转换后的 Markdown 表格渲染为原始 `<table>` HTML
- 化学式（SiO2、C4、C6H12O6）无下标显示
- `\(...` 定界符断裂导致 Obsidian ParseError
- 图片路径错乱或图片缺失
- MinerU 的 algorithm 块（`<div class="mineru-algorithm">`）未被转换
- 确定性 OCR 噪音（`\mathrm` 字母空格、`f^{\backslash *}`、数字拆散、HTML 实体）

### 1.3 不适用场景

- 把 PDF/Word **转换为** Markdown 本身——先用 MinerU / mineru skill 完成（两者是流水线上下游）
- 纯文本提取
- 转换为 Word/LaTeX/其他格式
- 扫描文档 OCR
- Markdown 中非表格 LaTeX 渲染问题（Obsidian/MathJax 问题）
- .tex 编译错误（LaTeX 编译器问题）

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
│   ├── verifier.py          # 聚合各 fixer 的 detect,输出带行号 Issue 清单
│   └── fixers/
│       ├── __init__.py      # 注册表:register / all_fixers / select / default_order
│       ├── base.py          # Issue / Fixer 协议 + split_zones 共享保护区
│       ├── table.py         # HTML 表格 → Markdown 表格
│       ├── chem_formula.py  # 化学式下标
│       ├── math_delim.py    # <eq>/\(...\)/$ 定界符 + \tag 缺陷
│       ├── ocr_cleanup.py   # 确定性 OCR 噪音(A 类)
│       ├── algorithm.py     # mineru-algorithm div 转换
│       ├── code_fence.py    # 未包代码块的代码识别包块(高置信,模糊上报)
│       └── images.py        # 图片复制与引用重写
├── tests/                   # pytest 单元测试(镜像 scripts 结构)
├── .gitignore
├── .gitattributes
└── LICENSE                  # MIT
```

### 2.2 修复器（fixer）协议与注册表

每个修复器是 `scripts/fixers/` 下的一个模块，实现统一协议：

- `run`:修复函数。文本类签名为 `(text) -> text`;文件系统类（`file_based=True`，如 images）签名为 `(md_path, source_dir) -> None`
- `detect`:体检函数，返回 `list[Issue]`(`Issue(fixer, line, message)`，行号供 Agent 定位）

注册表（`fixers/__init__.py`）:
- `register(fixer)`:新修复器 = 新文件 + 一行注册
- `default_order()`:固定执行序 `["table", "chem_formula", "math_delim", "ocr_cleanup", "algorithm", "code_fence", "images"]`，新修复器显式选位，不搞拓扑排序
- `select(ids)`:按 `default_order` 过滤出选中修复器（供 `--fixers`/`--skip`)
- 每个修复器可独立调用：`python -m scripts.fixers.<name> <file.md>`

### 2.3 共享保护区（zones)

`fixers/base.py` 的 `split_zones(text) -> list[(kind, segment)]` 是唯一词法切分器，所有文本修复器复用。保护区（绝不修改）:code_block、inline_code、math(`$...$`/`$$...$$`)、eq、image、link、url、html。修复器只在 `text` 段（及各自指定的段，如 math_delim 处理 eq 段）操作。

### 2.4 数据流

```
用户输入 (任意来源的 .md)
    ↓
python -m scripts.postprocess xx.md [--fixers a,b] [--skip c] [--images-dir PATH] [--in-place] [--verify]
    ↓
按 default_order 跑选中的文本修复器(text→text,写回)
    ↓
跑文件系统修复器(images,复制+重写引用)
    ↓
verifier 聚合各 fixer.detect → 带行号 Issue 清单(洪峰折叠)
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

### 4.2 chem_formula

化学式加下标：`SiO2`→`$SiO_2$`、`C6H12O6`→`$C_6H_12O_6$`。判定是**排版模式匹配**（两个元素符号单元，或单元素+数字，词边界锚定），全大写缩写（XRD/SEM）排除。只在 `text` 段操作。

- **适用**：化学/材料类论文。**不适用**：物理/数模文档（`Sv2` 实为 `$Sv^2$`，加下标即误伤）。
- **文档画像（detect 增强）**:verify 报告开头加画像提示——若 `$$`/`\tag` 密度高且无化学式特征，提示"疑似数学/数模文档，建议 `--skip chem_formula`"。**只提示，不自动 skip**（半自动）。
- 已知局限（沿袭，未改）：多位数下标 `H12` → `$C_6H_12O_6$`(`_` 只对下一字符生效）。

### 4.3 math_delim

定界符统一为 Obsidian 认的 `$...$`:
- `<eq>...</eq>` → `$...$`
- 成对 `\(...\)` → `$...$`
- 断裂 `\(...`（无配对 `\)`)→ 降级为纯文本（杜绝 ParseError)
- `\tag` 缺陷 detect:`\tag{...}` 内括号不配平、混入游离括号、裸 `~`（数学模式下渲染为空格，公式编号区间误拼）

只在 `text`/`eq` 段操作，不触碰已有 `$...$` 数学内容。

### 4.4 ocr_cleanup(A 类确定性 OCR 噪音）

只修"模式唯一、绝不误伤"的 OCR 噪音：

| 模式 | 规则 | 位置约束 |
|---|---|---|
| 白名单命令内字母空格 | `\mathrm { d r a f t }`→`\mathrm{draft}` | 白名单命令花括号内：`\mathrm \text \operatorname \mathbf \mathit \mathsf \textbf \textit` 及 `^{}` `_{}` |
| `f^{\backslash *}` → `f^{*}` | 固定替换 | math zone |
| 数字拆散（`0. 2 0`→`0.20`) | 删数字间空格 | **仅** ①`$...$` ②`$$...$$` ③白名单命令花括号内 |
| HTML 实体（`&gt; &lt; &amp; &quot;`) | 固定映射 | 非 code zone |

**B 类（语义级）只做 detect 不改**：希腊字母 `??` 占位符 → 报"疑似 OCR 字符映射错误"。

### 4.5 algorithm(mineru-algorithm div 转换）

MinerU 把算法/伪代码（及误圈的说明段落）打进 `<div class="mineru-algorithm">`。该 div 是 HTML 块，Obsidian 不渲染其内 Markdown/LaTeX，导致块内 `$...$` 公式也被关死。

处理：
- 拆掉 div 标签
- **锚点行**（`Algorithm N`/`算法 N` 标题、`Input:`/`Output:`/`输入:`/`输出:`、区块内编号步骤 `^\d+\.\s`、控制关键字 `for/while/if/return/repeat/until`)→ 代码块
- **其余行** → 回正文（`$...$` 恢复渲染）
- **拿不准的行** → 回正文 + detect 报"algorithm div @行N：第 X 行难以归类"（交 Agent 核对）

实证依据：algorithm div 内**无真代码**(def/class/import 零命中），只有伪代码与说明文字；真代码 MinerU 走 ` ```python ` 代码块，归 zones 保护区，不经本 fixer。

### 4.6 code_fence（未包代码块的代码）

MinerU 偶尔把代码段降级为普通文本（缺 ``` 围栏，如 `import numpy`/`def f(` 直接成正文行）。与三线表不同：代码文本本身完整，只是缺围栏，"认出代码行并包块"是机械可判的。

**守"不确定就上报"原则，不试图囊括所有情况：**

- **高置信才包块**：连续 ≥2 个完整锚点行（行首 `import`/`from..import`/`def (`/`class `/`print(`/`return `/`#include`/`plt.`/`for .. in .. :`)，且行内无 `$`、无中文句子）→ 包成 ` ```python `（默认 python；含 `#include`/`std::` 则 cpp，不做更多语言猜测）。
- **以下任一情况只 detect 上报、不包块**：锚点行混入 `$...$`（公式与代码纠缠）；锚点行混入中文句子（可能是正文提及代码）；孤立单锚点行；语言/边界不明确。
- 上报格式：`[code_fence] line N: suspected code block (needs agent review)` + 首行摘录，交 Agent 判断。

### 4.7 images(file_based=True)

图片**复制**（非移动）到 `.md` 同级 `images/`，并把本地引用重写为 `images/<文件名>`。外部 URL(http/https）不动。

- 图源目录是参数（`organize(md_path, source_images_dir)`)，可用 `--images-dir` 指定（如 MinerU 图包位置）。
- **边界**：只能修"引用路径"，不能恢复图片本体缺失。图片缺失时 verifier 报告并引导用户用能导图的转换器（如 MinerU Standard API）重转。
- detect：报缺失图片（带行号）。

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

## 6. SKILL.md 设计

### 6.1 Frontmatter

```yaml
---
name: obsidian-md-fixer
description: Use when a Markdown file converted from a PDF or Word document (especially by MinerU, but also pandoc/Marker/any converter) shows tables as raw HTML, chemical formulas like SiO2 unrendered, broken \( ... \) math delimiters causing ParseError, or images not displaying in Obsidian.
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
   - 选 fixer：源为物理/数模文档时 `--skip chem_formula`（或按 detect 画像提示）
   - 跑命令（默认 `<name>_fixed.md`，不覆盖原文件；`--in-place` 先建 `.bak`)
   - 退出码处理：0 报告产物；1 报告错误；2 报告产物并逐条列 verifier issue
   - 图片缺失：询问用户图包位置 → `--images-dir` 重跑；无图包则引导重转
   - 语义 issue(Agent 修）:detect 标记的上下标、OCR 误判、三线表
   - 汇报产物路径，提醒在 Obsidian 打开确认；产物在 vault 外则建议移入
5. **可选：公式语义审查**（三条硬规则：显式触发、模式级目标、只报告不改）
6. **Common Mistakes**：直接跑 `python scripts/x.py`、覆盖原文件、手改 HTML 表格、让 chem_formula 碰数模文档、在此转换 PDF/Word

## 7. README 设计

- 简介段：修复已转换 Markdown;"零依赖零 token、适用任何 md、不访问网络"
- 依赖：Python 3.10+;pytest 仅测试需要
- 安装与更新：**方式一 plugin marketplace**(`/plugin marketplace add` → `/plugin install`，或 skills 管理点更新，无需 clone);**方式二手动 clone + `git pull`**
- 使用：全部 CLI flag 示例；退出码说明
- 修复器做了什么：四个修复器表格 + 机械 vs 语义边界
- 数据安全：默认不覆盖原文件、`--in-place` 先建 `.bak`、重要文档建议备份

## 8. 使用方式

```bash
# 修复 Markdown(默认输出 <name>_fixed.md,不覆盖原文件)
python -m scripts.postprocess paper.md

# 只跑部分修复器(数模文档跳过化学式,避免误伤 Sv^2)
python -m scripts.postprocess paper.md --skip chem_formula

# 只跑指定修复器
python -m scripts.postprocess paper.md --fixers table,images

# 图片在别处(如 MinerU 图包),指定图源目录
python -m scripts.postprocess paper.md --images-dir "D:/mineru输出/images"

# 原地修复(自动创建 .bak 备份)
python -m scripts.postprocess paper.md --in-place

# 只校验不修改(语义修复后验证;0=干净,2=仍有 issue,不写文件)
python -m scripts.postprocess paper.md --verify

# 单独跑一个修复器
python -m scripts.fixers.table paper.md
```

**退出码**:`0` 成功；`1` 失败（无产物）;`2` 成功但验证有警告（产物已生成，带行号 issue 打印到 stderr，洪峰折叠，末尾打印 re-run 提示）。

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
