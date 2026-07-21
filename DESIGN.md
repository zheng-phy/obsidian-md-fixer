# pdf-to-obsidian 设计文档

## 1. 项目概述

### 1.1 目标

创建一个平台无关的 AI Agent skill，实现：
- 调用 MinerU Standard API 将 PDF 转换为 Markdown
- 或修复已有 Markdown 文件的渲染问题
- 自动后处理：HTML 表格 → Markdown 表格、化学式转 LaTeX、图片路径整理
- 产出物：一份 `.md` 文档 + 一个与 `.md` 同级的 `images/` 文件夹
- 不硬编码任何 API 密钥或用户隐私路径

### 1.2 适用场景

- 用户在 Obsidian 中阅读、管理学术论文
- 用户使用 MinerU 或其他工具转换 PDF 后，遇到表格/公式/图片渲染问题
- 用户希望自动化 PDF → Obsidian 工作流

### 1.3 不适用场景

- 纯文本提取
- 转换为 Word/LaTeX/其他格式
- 扫描文档 OCR
- 编辑原始 PDF
- Markdown 中非表格 LaTeX 公式渲染问题（Obsidian/MathJax 问题）
- .tex 文件编译错误（LaTeX 编译器问题）
- 软件开发方法论（如 TDD）咨询

## 2. 架构设计

### 2.1 目录结构

```
pdf-to-obsidian/
├── SKILL.md                 # skill 入口文档（平台无关）
├── README.md                # 用户文档
├── requirements.txt         # Python 依赖
├── scripts/
│   ├── __init__.py
│   ├── mineru_runner.py     # MinerU API 调用封装
│   ├── table_converter.py   # HTML 表格 → Markdown 表格
│   ├── latex_fixer.py       # 化学式/公式修复（含保护区）
│   ├── image_organizer.py   # 图片路径整理
│   ├── verifier.py          # 渲染问题启发式检查
│   └── postprocess.py       # 主入口，串联各模块
├── tests/
│   ├── __init__.py
│   ├── test_table_converter.py
│   ├── test_latex_fixer.py
│   ├── test_image_organizer.py
│   ├── test_verifier.py
│   └── fixtures/
│       ├── sample_table.html
│       ├── sample_table_expected.md
│       ├── sample_latex.md
│       └── sample_latex_expected.md
├── .gitignore
├── .gitattributes
└── LICENSE
```

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
|------|------|------|------|
| `mineru_runner.py` | 调用 MinerU API（异步流程，见下） | PDF 路径、输出目录 | MinerU 输出目录路径 |
| `table_converter.py` | HTML `<table>` → Markdown 表格 | Markdown 内容 | 转换后的 Markdown 内容 |
| `latex_fixer.py` | 化学式、`eq` 标签修复（先跳过保护区） | Markdown 内容 | 修复后的 Markdown 内容 |
| `image_organizer.py` | 图片复制到同级、路径修复 | .md 文件路径、源 images 目录 | 无（直接操作文件） |
| `verifier.py` | 启发式检查表格、公式、图片问题 | .md 文件路径 | 问题列表（空列表表示通过） |
| `postprocess.py` | 主入口，按扩展名分流，串联各模块 | 命令行参数 | 退出码（0 成功，1 失败，2 有警告） |

**MinerU API 异步流程**（mineru_runner 实现要点）：

1. 上传 PDF，获得 task_id
2. 轮询任务状态直到完成
3. 下载结果 zip 并解压
4. zip 的目录结构决定 image_organizer 的输入布局，实现时以实际返回结构为准

**latex_fixer 保护区**（实现要点）：

修复前必须先识别并跳过以下内容，防止误污染（如图片文件名 `fig_c4.jpg` 被改成 `$C_4$`）：
- 图片语法：`![](...)`、`![[...]]`
- 行内代码 `` `...` `` 与代码块
- URL（http/https 链接）
- HTML 标签属性内的文本

化学式匹配（如 `C4`、`SiO2`）只允许出现在正文文本中，且前后需为词边界，避免误匹配参考文献编号、图表标签、DOI 等。

**verifier 检查项**（启发式规则，非真实渲染）：

- 残留未转换的 HTML `<table>` 标签
- `$...$` / `$$...$$` 定界符未配对
- Markdown 中引用的图片文件不存在
- 正文中疑似未修复的化学式（如 `SiO2` 裸露出现）

### 2.3 数据流

```
用户输入 (.pdf 或 .md)
    ↓
postprocess.py 按扩展名判断输入类型
    ↓
.pdf → mineru_runner.py → MinerU 输出目录
.md  → 直接使用该文件
    ↓
table_converter.py 转换 HTML 表格
    ↓
latex_fixer.py 修复化学式和公式（跳过保护区）
    ↓
image_organizer.py 复制图片到同级、修复路径
    ↓
verifier.py 启发式检查
    ↓
输出：修复后的 .md + images/
```

## 3. SKILL.md 设计

### 3.1 Frontmatter

```yaml
---
name: pdf-to-obsidian
description: Use when importing an academic PDF (paper) into Obsidian and converting it with MinerU, or when a Markdown file converted from a PDF shows tables as raw HTML, chemical formulas like SiO2 unrendered, or images not displaying in Obsidian.
---
```

### 3.2 触发机制说明（SDO 规则）

标准 SKILL.md 格式没有独立的 keywords 字段——skill 是否被触发完全由 `description` 决定。description 必须遵守以下规则（来源：superpowers writing-skills 的 Skill Discovery Optimization）：

- 以 "Use when..." 开头，只写触发条件（症状、场景），第三人称
- **绝不写功能或流程摘要**——实测表明 description 里写了工作流程，agent 会只按 description 行动而不读正文
- 尽量控制在 500 字符以内（frontmatter 总上限 1024 字符）
- 关键词用 agent 会搜索的词：症状（broken、not rendering、raw HTML）、工具名（MinerU、Obsidian）、文件类型（PDF、Markdown）

### 3.3 排除条件（写入正文 "When NOT to use" 一节）

- Plain text extraction only
- Converting to Word/LaTeX/other formats
- Scanned documents requiring OCR-first tools
- Editing the original PDF
- LaTeX formula in Markdown (not in a table) not rendering — Obsidian/MathJax issue
- .tex file compilation errors — LaTeX compiler issue
- User wants to apply TDD or software development methodology

### 3.4 正文（body）结构

按 writing-skills 的标准模板组织，全文控制在 500 词以内（token 效率要求；重型内容放 scripts/ 等独立文件）：

1. **Overview**：1-2 句核心定位（用 MinerU 将学术 PDF 转为 Obsidian 可用的 Markdown，或修复已转换 Markdown 的表格/公式/图片渲染问题）
2. **When to Use / When NOT to Use**：症状列表 + §3.3 排除条件
3. **Quick Reference**：两种模式的命令速查表

   | 模式 | 命令 |
   |------|------|
   | PDF 转换 | `python -m scripts.postprocess <pdf路径> --output <输出目录>` |
   | 修复 Markdown | `python -m scripts.postprocess <md路径>` |

   （必须 `-m` 方式调用，保证包导入可用）

4. **Workflow**（agent 实际执行的指令）：
   - 模式判断：输入 `.pdf` → 转换模式；输入 `.md` → 修复模式
   - 转换模式：确认 `MINERU_TOKEN` 环境变量已设置（未设置则提示用户配置并停止）→ 运行脚本 → 按退出码处理：0 → 报告产物位置；1 → 报告错误信息；2 → 报告产物位置并列出 verifier 警告
   - 修复模式：运行脚本（默认输出 `<原名>_fixed.md`，不覆盖原文件）→ 退出码处理同上
   - 结果汇报：告知用户 `.md` 与 `images/` 的位置，提醒在 Obsidian 中打开检查渲染效果
5. **Common Mistakes**：如未设置 `MINERU_TOKEN` 就运行、直接覆盖用户原文件、手动改 HTML 表格而不用脚本

### 3.5 平台无关性

SKILL.md 不绑定特定 Agent 平台（Claude Code、CodeX、opencode、copilot 等），只要平台支持 skill 加载机制即可使用。正文中不引用任何平台特有功能或其他 skill。

注意区分两层：superpowers 子技能（test-driven-development、writing-skills、verification-before-completion）只约束**本项目的开发流程**（见 §6），不进入 SKILL.md 的运行时内容——skill 在使用者的平台上运行时，不依赖 superpowers 是否存在。

## 4. README.md 设计

### 4.1 适用工具组合

- **Obsidian**：最终笔记展示平台
- **MinerU**：PDF 解析引擎（需自行配置 API Token）
- **Python 3.8+**：运行后处理脚本

### 4.2 面向用户

- 需要在 Obsidian 中阅读、管理学术论文的研究者
- 使用 MinerU 转换 PDF 后遇到表格/公式/图片渲染问题的人
- 希望自动化 PDF → Obsidian 工作流的人

### 4.3 依赖说明

- `MINERU_TOKEN`：MinerU API 密钥（仅 PDF 模式需要，通过环境变量读取）
- 安装依赖：`pip install -r requirements.txt`
  - `requests`：HTTP 请求库
  - `pytest`：单元测试（开发时需要）

### 4.4 安装方式

将整个文件夹放入所用 Agent 平台的 skills 目录（如 Claude Code 为 `~/.claude/skills/`），或按各平台的 skill 加载规范放置。

## 5. 使用方式

### 5.1 从 PDF 转换

```bash
python -m scripts.postprocess paper.pdf --output ./output
```

流程：
1. 调用 MinerU API 转换 PDF
2. 后处理生成的 Markdown
3. 复制图片到 .md 同级目录并修复路径
4. 启发式检查并输出结果

### 5.2 修复已有 Markdown

```bash
python -m scripts.postprocess paper.md
```

流程：
1. 直接读取已有 Markdown
2. 执行后处理（表格转换、LaTeX 修复，跳过保护区）
3. 复制图片并修复路径
4. 启发式检查并输出结果

默认输出到同目录的 `paper_fixed.md`，**不覆盖原文件**。如需原地修改，显式传入 `--in-place`（会先创建 `paper.md.bak` 备份）。

## 6. 测试与开发流程

本项目开发遵循 superpowers 方法论，核心三条铁律：

1. **脚本开发 = TDD**（test-driven-development）：先写失败测试（RED），看着它失败，再写最小实现（GREEN），然后重构（REFACTOR）。没有失败测试就不写实现代码。
2. **SKILL.md 开发 = 文档版 TDD**（writing-skills）：先在无 skill 的情况下跑基线场景（RED），记录 agent 的自然行为与错误，再写 SKILL.md（GREEN），然后堵漏（REFACTOR）。
3. **完成声明前必须验证**（verification-before-completion）：任何"完成/通过"的声明，都必须有当次运行的命令输出作证据。

### 6.1 单元测试（pytest，对脚本做 TDD）

| 测试文件 | 测试内容 |
|----------|----------|
| `test_table_converter.py` | HTML 表格 → Markdown 表格，公式保留 |
| `test_latex_fixer.py` | C4 → $C_4$，SiO2 → $SiO_2$，`<eq>` → `$...$`；保护区不被污染（图片路径、代码、URL） |
| `test_image_organizer.py` | 图片复制、路径修复 |
| `test_verifier.py` | 检测未转换表格、未修复化学式、缺失图片 |

### 6.2 SKILL.md 基线测试（对文档做 TDD）

SKILL.md 属于"技术+工具"型 skill，按 writing-skills 的方法测试：

1. **RED（基线）**：不加载 skill，给 agent 应用场景（如"把这个 MinerU 转换的 Markdown 修到能在 Obsidian 正常显示"），记录其自然行为：错在哪、漏了哪步、用了什么借口
2. **GREEN**：针对基线暴露的问题写 SKILL.md，再跑同场景验证 agent 行为符合预期
3. **REFACTOR**：发现新的绕过方式就补充对策，重新验证

测试场景类型：
- 应用场景：agent 能否正确执行两种模式
- 变体场景：缺 `MINERU_TOKEN`、图片目录缺失等边界情况
- 信息缺失测试：正文指令是否有歧义或漏洞

### 6.3 集成测试

使用测试 PDF 端到端测试：
1. 运行完整转换流程
2. 在 Obsidian 中打开生成的 .md
3. 人工确认表格、公式、图片渲染正常

**注意**：集成测试用 PDF 不得使用有版权的已发表论文。使用自造测试文档或 CC 协议/开放获取论文，且 PDF 一律不提交进 git 仓库（见 .gitignore），仅在本地测试使用。

## 7. 隐私与安全

### 7.1 禁止硬编码

- API 密钥（`MINERU_TOKEN` 必须通过环境变量读取）
- 用户个人路径（`C:\Users\...`、`/home/...` 等）
- 真实姓名、邮箱、内网地址
- git 提交身份使用 GitHub noreply 邮箱，避免真实邮箱进入 commit 历史

### 7.2 默认路径

- 输出目录默认 `./output` 或用户传入参数
- 图片目录始终与 .md 同级
- 修复模式默认输出新文件，不破坏原始文件

## 8. 错误处理

| 场景 | 处理 |
|------|------|
| MinerU API 失败 | 打印错误信息，退出码 1 |
| 输入文件不存在 | 打印提示，退出码 1 |
| 无生成 Markdown | 打印提示，退出码 1 |
| 图片目录缺失 | 跳过图片整理，警告提示 |
| 验证发现问题 | 打印问题列表，退出码 2（产物已生成，属警告而非失败） |

退出码约定：0 = 成功；1 = 处理失败（无产物）；2 = 处理成功但验证有警告（产物已生成）。

## 9. 发布到 GitHub

### 9.1 发布前检查清单

**Skill 格式（依据 writing-skills）：**

- [ ] `name` 只用字母、数字、连字符
- [ ] description 以 "Use when" 开头、第三人称、无流程摘要、500 字符以内
- [ ] SKILL.md 正文 ≤500 词，重型内容（100+ 行）放独立文件
- [ ] SKILL.md 基线测试（§6.2）已完成，agent 行为验证通过

**质量与隐私：**

- [ ] 所有单元测试通过（以当次运行输出为证，不凭"应该能过"）
- [ ] 隐私审查通过（无硬编码密钥/路径/个人信息；git 提交身份为 noreply 邮箱）
- [ ] 确认无有版权的论文 PDF 被提交（测试用论文一律不入库）
- [ ] README 完整（安装、使用、示例）
- [ ] requirements.txt 与代码实际依赖一致
- [ ] .gitignore 与 .gitattributes 已配置
- [ ] LICENSE 添加（建议 MIT）

### 9.2 仓库名建议

`pdf-to-obsidian` 或 `mineru-obsidian-skill`

## 10. 后续优化方向

- 支持批量处理整个文件夹的 PDF
- 支持自定义化学式映射表
- 支持保留 HTML 表格但添加 Obsidian 兼容属性（备用方案）
- 与 Obsidian 插件联动，转换后自动打开笔记

---

# v2 演进设计（2026-07-21)

> 本章记录 2026-07-21 代码审查后的重新设计。§1-§10 为 v1 历史记录，保留不删；
> 凡本章与 v1 冲突之处，以本章为准（被取代的 v1 条目在各节注明）。

## 11. 审查结论与 Important 修复决议

2026-07-21 对仓库做了两维审查（隐私/公开就绪 + skill 质量/与 mineru 冲突）,无 Critical,
Important 决议如下:

| 编号 | 问题 | 决议 |
|---|---|---|
| I1 | README/DESIGN 声称 Python 3.8+,实际 PEP 604 语法需 3.10+ | 文档统一改为 **3.10+**(不改代码) |
| I2 | postprocess.py docstring 演示了 SKILL.md 禁止的 `python scripts/postprocess.py` | docstring 改为 `-m` 调用形式 |
| I3 | mineru_runner 零重试 | **随 convert 删除而废止**(§12) |
| I4 | "导入 Obsidian" 到 ./output 戛然而止,缺 vault 落位指引 | SKILL.md 补落位指引(§16) |
| I5 | convert 把 MINERU_TOKEN 当硬前提 | **随 convert 删除而废止**(§12) |
| 消歧 | 与 mineru skill 在 "PDF→Obsidian" 象限触发重叠 | **纯修复向定位,彻底消歧**(§12) |

Minor 修复(一并做):错误信息改走 stderr;`--in-place` 对 PDF 输入的静默忽略(随 convert 删除而废止);image_organizer 无条件重写引用的问题由 `--images-dir` 机制重新界定(§15.4)。

## 12. 定位转向：删除 convert,纯修复向

### 12.1 决策

**删除 convert 模式（mineru_runner.py 整个移除，进 git 历史）,skill 纯修复向。**
本 skill 不再调用 MinerU API、不再需要 MINERU_TOKEN、不再处理 .pdf/.docx 输入,
只接受**任何来源的 .md** 并修复其在 Obsidian 中的渲染问题。

### 12.2 理由

- 目标用户定为"已有 MinerU token 的用户",其转换能力由 mineru skill（同一 Standard API、
  同一 200 页上限）或 MinerU 官方网页/CLI 提供,本 skill 的 convert 无差异化价值
- 真正无人覆盖的价值是**转换之后的修复**:MinerU 转完表格仍是 HTML、化学式裸露、
  docx 的 `\(...\)` 断裂——这些 MinerU 与 mineru skill 都不修
- 砍掉 convert 后与 mineru skill 从"转换象限正面重叠"变为"流水线上下游":转换归 mineru
  （或任意转换器）,修复归本 skill,触发彻底消歧
- SKILL.md 的 description 改为纯修复向,不提转换

### 12.3 命名与改名

- skill 名：`pdf-to-obsidian` → **`obsidian-md-fixer`**(name 字段同步)
- 弃选 `mineru-output-fixer`:fix 模式接受任何来源的 md(pandoc/Marker/手写),钉死 mineru
  会误导触发；且绑定第三方品牌是长期负债
- 锚定问题域(Obsidian 中 md 渲染坏）而非上游工具；description 里写
  "especially MinerU-converted Markdown" 承接真实触发场景
- 连锁改动：仓库目录名、SKILL.md name、README、git 远程仓库名（公开时）

## 13. 架构：元工具注册表（方案 B)

### 13.1 混合式分层定位（地基）

| 层 | 承担者 | 职责 |
|---|---|---|
| 机械修复（90%） | 确定性 Python 修复器 | 表格、图片路径、定界符换壳——量大、无歧义、保护区敏感 |
| 语义修复（10%）| Agent | 上下标语义、断句、MinerU 系统性识别错误——由 detect 报告驱动 |
| 接口 | verifier + 退出码 2 | 聚合各修复器的 detect,输出带行号的 Issue 清单给 Agent |

### 13.2 Fixer 协议与注册表

```
scripts/fixers/
├── __init__.py       # 注册表:register / all_fixers / select(--fixers/--skip)
├── base.py           # Issue(fixer,line,message)、Fixer 协议、共享 zones
├── table.py          # 现 table_converter 平移 + detect
├── chem_formula.py   # 现 latex_fixer 的化学式规则
├── math_delim.py     # 现 latex_fixer 的 <eq>+$ 配对 + 新增 \(...\) 断裂修复
└── images.py         # 现 image_organizer 平移(file_based=True)
```

- 新修复器 = 新文件 + 一行 `register(...)`;verifier 自动聚合其 detect
- `file_based` 标志区分纯文本修复器（text→text）与文件系统修复器（如 images)
- 执行顺序保持写死（table → chem_formula/math_delim → images → verify),
  序由注册表模块的固定列表定义,新修复器插位时显式选位置——不搞拓扑排序
- 每个修复器可独立调用：`python -m scripts.fixers.<name> xx.md`

### 13.3 detect 语义与行号

- **先全部 fix 完，最后统一跑一次全量 detect**——Issue 行号对最终产物准确,
  Agent 语义修复基于最终文件
- detect 报的是"修完后仍存在的问题",这正是要给 Agent 的清单
- detect 带行号要求 zones 切块时记录每块起始行（detect 比 fix 略复杂,已接受)

### 13.4 latex_fixer 拆分（对应遗留争议点 ③)

latex_fixer 实际干两类活：
- **(a) 化学式下标**（对 MinerU 漏判公式的语义兜底）→ 拆为 `chem_formula`
- **(b) `<eq>`/定界符清理**(MinerU 输出的机械残渣）→ 拆为 `math_delim`

拆分理由（实证）:docx 场景要关的是 (a) 不是 (b)——chem-formula 会把物理/建模文档的
`Sv2`（实为 $Sv^2$）误修为下标 $Sv_2$,而 (b) 对 docx 仍必须（`\(...\)` 断裂）。
粒度恰好按场景切分。**注意**:fix 模式输入是 .md,无法自动判断源格式,因此"跳过 chem-formula"
不能自动触发——由 SKILL.md 指引 Agent:当用户说明 md 来自 Word/物理/建模类文档(或 detect 报告显示
chem-formula 高误伤)时,显式传 `--skip chem-formula`。

## 14. 缺陷画像（实证）与修复器映射

综合一份材料类论文（pdf）与 CUMCM2016-A(docx，系泊系统题）两个真实产物:

| MinerU 输出形态 | 来源 | Obsidian 渲染 | 归谁修 |
|---|---|---|---|
| `$...$` / `$$...$$` 完整 | pdf+docx | ✅ | 不用修 |
| 表格内公式（HTML 表格里 `$...$`) | pdf+docx | ✅ 表格转 MD 后自然渲染 | 不用修（表格转换顺带） |
| 漏判公式裸文本（C4、SiO2) | pdf 化学类 | ❌ 无下标 | `chem_formula` |
| `<eq>...</eq>` 标签 | pdf | ❌ | `math_delim` |
| OMML 碎片 `\(...\)` 定界符不配对 | docx | ❌ ParseError | `math_delim` |
| 上下标信息丢失（Sv2→$Sv^2$、m3→m³) | docx | ⚠️ 语义错 | **Agent**(detect 驱动） |
| `$` 计数不配对（碎片） | 偶发 | ❌ | detect 报告,Agent |

**边界（钉死）**:fixer 只修"机械可判"的；语义重建（上下标、公式正确性）永远划给 Agent,
不进 fixer——防止未来往 fixer 里塞语义规则、重踩误伤的坑。

### 14.1 化学式判定原理与局限

latex_fixer（未来 chem_formula）的判定是**排版模式匹配**而非语义：两个"元素符号单元"
或"单元素+数字",词边界锚定，全大写缩写（XRD/SEM）排除。
- 葡萄糖 `C6H12O6` → `$C_6H_{12}O_6$` **正确**;有机物下标内部出现无碍
- 真正局限：上下标不分（伤物理/建模文档，不伤化学）、元素符号开头的英文词（概率极低）

## 15. 关键机制设计

### 15.1 图片缺失：`--images-dir` 参数（用户提案，采纳）

image_organizer 的签名本来就是 `organize_images(md_path, source_images_dir)`——图片目录
是参数不是硬编码。CLI 暴露 `--images-dir <路径>`:

```
verifier 报 "Missing image: images/abc.jpg"
  → SKILL.md 指引 Agent 询问用户 MinerU 图包位置
  → Agent 重跑:python -m scripts.postprocess paper.md --images-dir "<用户告知的路径>"
```

这是**传参**而非改脚本——无"软调整"、无状态残留、不影响下次判断。
SKILL.md 增加"图片缺失处置流程"一节。

### 15.2 公式语义审查（可选阶段，用户提案，三条边界钉死）

主流程修完后,由 SKILL.md 引导 Agent 询问用户"要不要做公式语义审查",**用户显式同意才跑**。
三条边界（必须写入 SKILL.md 作为硬规则）:

1. **显式触发的可选阶段，绝不默认全量跑**——全量审查是本 skill 最大的单次 token 消耗,
   与"不过度消耗 token"的设计目标冲突;verifier 报告公式总数与可疑项后由用户决定
2. **审查目标是 MinerU 的系统性识别错误模式，不是数学正确性**——识别模式级问题
   (`\times` 被误识为 x、上下标错位、`\frac` 残缺、希腊字母误识),而非证明学术正确性
   （论文公式多为新推导，无"经典形式"可比；联网比对基本不可行）
3. **只报告，不改**——输出"可疑公式清单 + Agent 认为的正确形式 + 依据",
   用户逐条确认后自行修改或显式让 Agent 改（与"默认不覆盖原文件"哲学一致）

### 15.3 Sv2 类上下标修复的三层解（对应 docx 误伤）

1. 主解：源为 Word/物理/建模类文档时 `--skip chem-formula`(Agent 按 §13.4 规则显式传),Sv2 不被碰
2. 兜底：detect 仍将其列入 Issue（带行号，标注"疑似上下标残留"),Agent 读上下文语义修复
3. 归位：上下标恢复是信息已丢失后的语义重建，不进任何 fixer(§14 边界）

### 15.4 图片本体缺失的口径

fix 模式能修"图片引用路径",**修不了"图片本体缺失"**(MinerU Agent API 档只给 md 不给图,
或用户只拷了 md)。此缺口由 §15.1 的 `--images-dir` 承接大部分场景；若用户确无图包,
verifier 明确报告"图片本体缺失，需用 Standard API 重转或手动补图"——划清边界，不假装能修。

## 16. SKILL.md / README 修订点

- description：纯修复向，承接 MinerU/pandoc/任意来源 md 的 Obsidian 渲染问题
- "When NOT to Use"：删除 v1 残留的 TDD 条目；新增"转换 PDF/Word 本身——用 MinerU/mineru skill"
- 新增图片缺失处置流程（§15.1)、公式语义审查引导（§15.2)
- vault 落位指引（I4)：产物在 vault 外时,建议把 `<name>/` 文件夹（md + images/）整体移入 vault
- README：把"Fix 模式零依赖零 token、适用任何 md"提至简介段；Python 版本声明改 3.10+(I1);
  新增与 mineru skill 的推荐组合叙事（mineru 转换 → 本 skill 修复）——把"重复"叙事转为"管线"叙事

## 17. v2 数据流

```
用户输入 (任意来源的 .md)
    ↓
python -m scripts.postprocess xx.md [--fixers a,b | --skip c] [--images-dir <路径>]
    ↓
fixers/table.py         HTML 表格 → MD 表格
fixers/chem_formula.py  化学式下标(源为 Word/物理类时 Agent 显式 --skip,§13.4)
fixers/math_delim.py    <eq>/\(...\)/$ 定界符统一换壳
fixers/images.py        图片复制 + 引用重写(--images-dir 指定图源)
    ↓
verifier 聚合各 fixer.detect → 带行号 Issue 清单
    ↓
退出码 0/1/2;2 时 Agent 按清单做语义修复(上下标、断句)
    ↓
(可选,用户显式同意)公式语义审查:模式级,只报告不改(§15.2)
    ↓
输出:修复后 .md + images/;引导移入 Obsidian vault
```

## 18. v2 测试计划

- 现有 28 测试平移到 fixers 各模块（table/chem_formula/math_delim/images/verifier)
- 新增：共享 zones 单测；各 fixer 的 detect 单测（带行号);`--fixers/--skip` 选择逻辑；
  `--images-dir` 缺/存在两态；docx 真实样本（CUMCM2016-A）的 `\(...\)` 断裂 fixture
- 中文/空格路径回归用例（本 skill 自身活在中文路径下）
- SKILL.md 基线测试（§6.2 方法不变）：应用场景改为"修 MinerU 转出的坏 md",
  变体场景含图片缺失询问流程、公式审查触发/不触发两态

## 19. 仓库与过程产物

- 设计文档 DESIGN.md、plans 之外的**过程性产物**（superpowers plans/specs、本地会话状态）
  不入库：`.gitignore` 增加 `docs/superpowers/`
- 改名后公开仓库时用 `obsidian-md-fixer`;v1 的 §9.2 仓库名建议作废
