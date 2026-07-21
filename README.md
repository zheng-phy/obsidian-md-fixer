# obsidian-md-fixer

> Fix Markdown already converted from PDF/Word (by MinerU, pandoc, Marker, any converter) so tables, formulas, and images render correctly in Obsidian. 修复已转换 Markdown 在 Obsidian 中的表格、公式、图片渲染问题。

一个平台无关的 AI Agent skill：用确定性的 Python 修复器（fixer）修复转换后 Markdown 的三类常见渲染问题，并把语义级问题（上下标、断句）留给 Agent 按行号清单处理。

## 它解决什么问题

用 MinerU 等工具把 PDF/Word 转成 Markdown 后，在 Obsidian 里常见三类渲染问题：

1. 表格仍是 HTML `<table>` 源码，不渲染
2. `SiO2`、`C4` 这类化学式没有下标，显示异常；或 `\(...` 定界符断裂导致 ParseError
3. 图片路径错乱或图片缺失，笔记里看不到图

本 skill **只修复已转换的 Markdown，不做格式转换**。转换请先用 MinerU / mineru skill 完成——两者是流水线上下游：mineru 把 PDF/Word 转成 md，本 skill 把 md 修到能在 Obsidian 正常渲染。

## 依赖

- **Python 3.10+**，依赖见 `requirements.txt`（仅 `pytest`，修复器全部基于标准库）
- **无需任何 API token / 网络**——本 skill 不调用外部服务
- **Obsidian**：最终的笔记展示平台

## 安装与更新

### 方式一：Claude Code plugin（推荐，一键安装/更新）

通过 plugin marketplace，无需 clone 仓库：

```
# 一次性:把本仓库加为 marketplace
/plugin marketplace add zheng-phy/obsidian-md-fixer

# 安装
/plugin install obsidian-md-fixer@zheng-phy

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

## 使用

### 方式一：作为 Agent skill（推荐）

放入 skills 目录后，直接对 agent 说：

> 帮我修复这个 Markdown 的表格和公式渲染：paper.md
> MinerU 转的这个笔记在 Obsidian 里图片显示不出来：notes/paper.md

### 方式二：命令行直接调用

在 skill 根目录下运行（必须用 `-m` 方式）：

```bash
# 修复 Markdown(默认输出 paper_fixed.md,不覆盖原文件)
python -m scripts.postprocess paper.md

# 只跑部分修复器(如源是物理/建模文档,跳过化学式下标避免误伤 Sv^2)
python -m scripts.postprocess paper.md --skip chem_formula

# 只跑指定修复器
python -m scripts.postprocess paper.md --fixers table,images

# 图片在别处(如 MinerU 的图包),指定图源目录
python -m scripts.postprocess paper.md --images-dir "D:/mineru输出/images"

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
| `table` | HTML `<table>` → Markdown 表格，单元格内 LaTeX 公式保留 |
| `chem_formula` | `SiO2` → `$SiO_2$`、`C6H12O6` → `$C_6H_12O_6$`；图片路径、行内代码、URL 等保护区不受影响 |
| `math_delim` | `<eq>` 标签 → `$...$`；成对 `\(...\)` → `$...$`；断裂 `\(...` 降级为纯文本（杜绝 ParseError) |
| `images` | 图片**复制**（非移动）到 `.md` 同级 `images/`，并修复引用路径 |

**机械修复 vs 语义修复**：修复器只做"机械可判"的修复。上下标语义（`Sv2` 是 `Sv²` 还是 `Sv₂`)、断句这类需要理解上下文的问题，由 verifier 以带行号的清单报出，交给 Agent 阅读后修复——不碰确定性工具不敢判断的部分。

## 开发与测试

```bash
python -m pytest tests/ -v
```

52 个单元测试覆盖全部修复器、注册表、编排器与边界（含中文/空格路径）。设计文档见 [DESIGN.md](DESIGN.md)。

## 隐私说明

- 本 skill 不读取任何密钥、不访问网络，纯本地文本处理
- PDF/测试文档不进入本仓库（见 `.gitignore`)

## 数据安全

本 skill 会改写 Markdown 文件。默认行为：输出 `<name>_fixed.md`，**不覆盖原文件**；仅当显式传 `--in-place` 时才原地修改，且会先创建 `.bak` 备份。机械修复由确定性脚本完成，但任何自动化工具都可能误判，重要文档建议先备份或在 git 跟踪的文件上使用。

## License

[MIT](LICENSE)
