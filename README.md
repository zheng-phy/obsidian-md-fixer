# obsidian-md-fixer

> Fix Markdown already converted from PDF/Word (by MinerU, pandoc, Marker, any converter) so tables, formulas, code, and images render correctly in Obsidian. 修复已转换 Markdown 在 Obsidian 中的表格、公式、代码、图片渲染问题。

一个平台无关的 AI Agent skill：用确定性的 Python 修复器（fixer）修复转换后 Markdown 的常见渲染问题，并把语义级问题（上下标、断句、图序）留给 Agent 按行号清单处理。**默认面向 CS/AI/数学/物理论文深度优化**；化学式下标为可选修复器，仅化学/材料文档需要显式开启。

## 它解决什么问题

用 MinerU 等工具把 PDF/Word 转成 Markdown 后，在 Obsidian 里常见的渲染问题：

1. 表格仍是 HTML `<table>` 源码，不渲染
2. `\(...` 定界符断裂导致 ParseError；行内公式被降级成文本（`X\~B(`、`0<p<1`）
3. 代码段缺 ``` 围栏、围栏语言误标、围栏碎片化
4. 图片路径错乱、图片缺失、图与图注分离、图序错乱、图包含未引用图
5. OCR 痕迹：`�`（U+FFFD）、ff 连字丢失（dificulty）、URL 断行、乱码公式
6. （可选）`SiO2`、`C6H12O6` 这类化学式没有下标——需显式 `--fixers chem_formula`

本 skill **只修复已转换的 Markdown，不做格式转换**。转换请先用 MinerU / mineru skill 完成——两者是流水线上下游：mineru 把 PDF/Word 转成 md，本 skill 把 md 修到能在 Obsidian 正常渲染。

## 依赖

- **Python 3.10+**，依赖见 `requirements.txt`（仅 `pytest`，修复器全部基于标准库）
- **无需任何 API token / 网络**——本 skill 不调用外部服务
- **Obsidian**：最终的笔记展示平台

## 安装与更新

> **选哪种？** 只用 Claude Code 一个 agent → 方式一（plugin，一键安装/更新）。同时用 Codex / opencode / Gemini 等多个 agent → 方式三（CC-Switch，一处管理、同步到多个 agent)。方式二是手动操作（方式三的底层原理）。

### 方式一：Claude Code plugin（推荐，一键安装/更新）

通过 plugin marketplace，无需 clone 仓库：

```
# 一次性:把本仓库加为 marketplace
/plugin marketplace add zheng-phy/obsidian-md-fixer

# 安装(@ 后是 marketplace 名,即 marketplace.json 的 name,不是 GitHub 用户名)
/plugin install obsidian-md-fixer@obsidian-md-fixer

# 以后有新版本,在 skills 管理中点"更新"即可
```

发布历史与每次迭代的变更说明见本仓库的 [Releases](https://github.com/zheng-phy/obsidian-md-fixer/releases) 页。

### 方式二：手动放入 skills 目录（其他 Agent 平台)

```bash
# 1. 克隆到你所用 Agent 平台的 skills 目录（以 Claude Code 为例）
git clone https://github.com/zheng-phy/obsidian-md-fixer.git
# 然后将整个文件夹放入 skills 目录，如 ~/.claude/skills/obsidian-md-fixer/

# 2. 更新:进入该目录拉取最新代码
cd ~/.claude/skills/obsidian-md-fixer && git pull

# 3. (可选)安装 Python 依赖——仅跑测试需要;运行修复器零依赖
pip install -r requirements.txt
```

### 方式三：CC-Switch（多 agent 统一管理）

如果你同时用 Claude Code、Codex、opencode、Gemini 等多个 AI CLI,推荐用 [CC-Switch](https://github.com/farion1231/cc-switch) 统一管理 skills——在它的 skill 管理里**添加本仓库链接**，即可一键安装并同步到各 agent 的 skills 目录（`~/.claude/skills`、`~/.codex/skills`、`~/.opencode/…` 等），更新也在一处完成。

> 注意：方式一（plugin marketplace）装进的是 Claude Code 的 plugin 目录，**不在** CC-Switch 读取的 `~/.claude/skills` 里，所以 plugin 安装的 skill 不会出现在 CC-Switch 的 skill 管理中——多 agent 用户请走方式三，别两种方式混用（会产生两份同名 skill)。

## 使用

### 方式一：作为 Agent skill（推荐）

放入 skills 目录后，直接对 agent 说：

> 帮我修复这个 Markdown 的表格和公式渲染：paper.md
> MinerU 转的这个笔记在 Obsidian 里图片显示不出来：notes/paper.md

### 方式二：命令行直接调用

在 skill 根目录下运行（必须用 `-m` 方式）：

```bash
# 修复 Markdown(默认输出 paper_fixed.md,不覆盖原文件;打印每 fixer 变更摘要)
python -m scripts.postprocess paper.md

# 化学/材料文档:显式开启化学式下标(默认集不含,须显式选中)
python -m scripts.postprocess paper.md --fixers chem_formula

# 只跑指定修复器
python -m scripts.postprocess paper.md --fixers table,images

# 图片在别处(如 MinerU 的图包),指定图源目录
python -m scripts.postprocess paper.md --images-dir "D:/mineru输出/images"

# 输出目录名(默认 images;如需要 Image/ 时用)
python -m scripts.postprocess paper.md --images-out-dir Image

# 合并单元格表(HTML)展平为 Markdown 草稿(opt-in;每个表带 verify against PDF 标记)
python -m scripts.postprocess paper.md --flatten-merged-tables

# 原地修复(自动创建 paper.md.bak 备份)
python -m scripts.postprocess paper.md --in-place

# 只校验不修改(语义修复后验证;0=干净,2=仍有 issue,不写文件)
python -m scripts.postprocess paper.md --verify

# 单独跑一个修复器
python -m scripts.fixers.table paper.md
```

**退出码**:`0` 成功；`1` 失败（无产物）；`2` 成功但验证有警告（产物已生成，警告列表带行号打印）。

## 修复器做了什么

| 修复器 | 说明 |
|------|------|
| `table` | HTML `<table>` → Markdown 表格，单元格内 LaTeX 公式保留；合并单元格表保留 HTML 并报 detect（表内 `$...$` 在 Obsidian 不渲染） |
| `table_flatten`（可选，opt-in） | 合并单元格表（rowspan/colspan）展平为 Markdown 草稿（复合列名、span 填充）；每个表带 `verify against PDF` 标记，`--flatten-merged-tables` 启用 |
| `chem_formula`（可选，opt-in） | `SiO2` → `$SiO_{2}$`、`C6H12O6` → `$C_{6}H_{12}O_{6}$`；118 元素周期表校验 + 数字必需，`GPT2`/`MoE`/`LoRA`/`Sv2` 等绝不误伤；仅化学/材料文档显式开启 |
| `math_delim` | `<eq>` 标签 → `$...$`；成对 `\(...\)` → `$...$`；`\[...\]` 显示公式 → `$$...$$`；断裂 `\(...` 降级为纯文本（杜绝 ParseError)；text 段数字区间 `\~` → `~`；detect 报行内公式降级（`X\~B(`、`0<p<1`）与乱码公式 |
| `ocr_cleanup` | 确定性 OCR 噪音：`\mathrm` 字母空格、`f^{\backslash…*}`、数字拆散、HTML 实体、C0 控制字符清除、ff 连字词典（dificulty→difficulty，含大写变体）；detect 报 U+FFFD、元组下标、字母并跑、正文错形（`wtih`）、标识符拆开（`k t h \_ excluding`） |
| `algorithm` | MinerU algorithm div 转换：锚点行进代码块，含数学的伪代码整段回正文（公式恢复渲染） |
| `code_fence` | 缺 ``` 围栏的高置信代码包块（已有围栏零改动）；detect 报围栏语言误标/碎片化/缩进丢失/ipynb 碎片 |
| `url_join` | 同行断 URL 接合（`arxiv.org/abs/ 2601.05808` → 完整 URL)；跨行断 URL 只报不改 |
| `images` | 图片**复制**（非移动）到 `.md` 同级目录并修复引用路径（相对 POSIX 路径、容忍括号目录名，`--images-out-dir` 可改目录名）；detect 报缺失图、图-图注分离（含簇共享图注与距离信息）、图序异常、未引用图、轴标签误标、`<!-- image -->` 占位符 |

**机械修复 vs 语义修复**：修复器只做"机械可判"的修复。上下标语义（`Sv2` 是 `Sv²` 还是 `Sv₂`)、断句、图序这类需要理解上下文的问题，由 verifier 以带行号的清单报出，交给 Agent 阅读后修复——不碰确定性工具不敢判断的部分。换行符（CRLF/LF）逐字节保留，不因修复改变。

## 开发与测试

```bash
python -m pytest tests/ -v
```

290+ 个单元测试覆盖全部修复器、注册表、编排器与边界（含中文/空格路径、换行符保留）。设计文档见 [DESIGN.md](DESIGN.md)（含 v2.0.0 转型与 v2.1.0 决策记录）。

## 隐私说明

- 本 skill 不读取任何密钥、不访问网络，纯本地文本处理
- PDF/测试文档不进入本仓库（见 `.gitignore`)

## 数据安全

本 skill 会改写 Markdown 文件。默认行为：输出 `<name>_fixed.md`，**不覆盖原文件**；仅当显式传 `--in-place` 时才原地修改，且会先创建 `.bak` 备份。机械修复由确定性脚本完成，但任何自动化工具都可能误判，重要文档建议先备份或在 git 跟踪的文件上使用。

## License

[MIT](LICENSE)
