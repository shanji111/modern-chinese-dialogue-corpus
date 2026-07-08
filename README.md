# 现代汉语对话语料库

> 从“语言资源库”走向“互动知识库”的汉语对话平台

本项目是一个围绕**汉语真实互动材料**建设与检索的语料平台，既服务于语料库语言学、互动语言学、语用学、对话句法等研究，也面向生成式人工智能时代的对话建模与知识组织需求。项目强调“对话转向（Dialogic Turn）”视角，不把语料仅仅当作静态文本资源，而是尽量保留话轮、上下文、说话人关系、相邻回应和多模态线索。

目前仓库主要包含两部分：

1. 一个基于 **Flask** 的在线检索与浏览网站；
2. 一组围绕语料导入、全文索引、话轮重建、相邻话轮分析和文本对话整理的维护脚本。

## 项目理念

根据项目摘要，本库的核心目标不是单纯“收集中文句子”，而是建设一个以**自然互动**为核心的汉语对话知识平台：

- 覆盖日常对话、影视对白、网络互动、访谈、课堂交流、多模态材料，以及古代/近古汉语对话；
- 强调话轮结构、对话过程、相邻回应、立场与互动功能；
- 支持在语料建设中引入大语言模型，辅助转写、候选抽取、审核和质检；
- 让语料从“可保存、可检索”进一步走向“可分析、可比较、可解释”的互动知识基础设施。

## 当前功能

### 1. 多来源语料检索与浏览

前台目前围绕以下板块组织语料：

- 日常对话
- 影视对白
- 古代汉语
- 文本对话
- 网络回帖
- 访谈语料
- 课堂互动
- 多模态语料

用户可以按来源、类别、数据集、年份、标题、说话人等维度筛选和浏览。

### 2. 多种检索方式

项目目前提供几种互补的检索入口：

- **普通检索**：适合查固定词语、短语和高频表达；
- **正则检索**：适合查形式变体、边界限制、间隔模式；
- **高级检索**：支持来源、标题、年份、说话人、正文长度、是否带音频等字段限制；
- **对话句法 / 共鸣检索**：基于相邻话轮关系，观察承接、重复、否定、问答、修复等互动模式。

### 3. 两种结果视图

检索结果页不是只给一条“命中句子”，而是尽量保留互动语境：

- **居中检索视图**：以前序话轮 / 命中话轮 / 后续话轮展示局部上下文；
- **完整对话视图**：展示命中所在的完整对话或更大的对话片段；
- 支持展示来源、作品、章节、说话人、对话 ID、音频入口等元信息。

### 4. 投稿、审核与转写

站点内置了一套轻量的投稿与后台审核流程：

- 用户可提交文本、TXT、音频、视频等材料；
- 管理员可在后台审核、下载、删除和批准投稿；
- 对音频 / 视频投稿，可通过 OpenAI 转写接口进行自动转写；
- 已审核内容可以写入主库或多模态表。

### 5. 文本对话整理流水线

仓库中的 `talkdata/` 目录承担文本对话子库的工程化整理工作。当前 README 只记录**已进入 Git 的脚本接口和工作思路**；大量原始语料、LLM 缓存、审核导出文件和中间结果默认不进入仓库。

已跟踪的本地脚本主要用于：

- 导入整理后的文本对话 CSV；
- 检查线上 / 本地文本对话状态；
- 将滑动窗口式对话单元合并为更大的完整对话；
- 生成访谈类样本或其他专项导入材料。

## 技术栈

- **后端**：Flask
- **模板层**：Jinja2
- **前端**：原生 JavaScript + CSS
- **默认数据库**：SQLite
- **可选数据库后端**：PostgreSQL（已具备迁移与部分运行支持）
- **全文检索**：SQLite FTS5
- **部署**：Render + `gunicorn`
- **对象存储**：本地文件系统或兼容 S3 / R2 的对象存储
- **可选 AI 能力**：OpenAI 转写；本地语料建设阶段也试验过外部 LLM 审核/抽取流程

## 数据结构概览

项目的核心数据不止一张 `corpus_entries` 主表，而是围绕“对话”构建了几层派生结构：

### 主表

- `corpus_entries`：主语料表，保存标题、正文、来源、年份、类别、数据集名、说话人、对话片段等信息。

### 检索派生表

- `corpus_entries_fts`：SQLite FTS5 全文索引表，用于普通检索、部分高级检索与正则筛选配合。

### 对话结构派生表

- `dialogue_turns`：从主表内容中拆出的**话轮级**数据，服务于相邻话轮分析；
- `dialogue_pairs`：从 `dialogue_turns` 派生出的**相邻话轮对**，服务于“对话句法 / 共鸣检索”。

### 投稿相关表

- `corpus_submissions`：用户投稿与审核状态；
- `multimodal_entries`：与投稿、多模态条目相关的存储表。

## 仓库结构

下面这张表只概括当前 Git 仓库里最重要的部分：

| 路径 | 说明 |
| --- | --- |
| `app.py` | Flask 主入口，包含前台检索、浏览、投稿、后台、音频与共鸣检索路由 |
| `corpus_repository.py` | 主要的数据访问层与对话派生逻辑 |
| `database.py` | SQLite / PostgreSQL 连接封装 |
| `services/` | 已拆出的服务层（音频、浏览、投稿存储、转写等） |
| `templates/` | 前端页面模板 |
| `static/` | 全站样式、结果页与共鸣检索前端脚本、帮助页图片 |
| `init_db.py` | 用示例 JSON 初始化一个最小 SQLite 数据库 |
| `import_bulk_csv.py` | 将标准化 CSV 批量导入数据库 |
| `prepare_corpus_fts5.py` | 构建 / 重建 FTS5 索引及触发器 |
| `migrate_dialogue_turns.py` | 构建 `dialogue_turns` 派生表 |
| `rebuild_dialogue_pairs.py` | 构建 `dialogue_pairs` 派生表 |
| `migrate_sqlite_to_postgres.py` | 将 SQLite 数据迁移到 PostgreSQL |
| `schema_postgres.sql` | PostgreSQL schema 参考 |
| `talkdata/` | 文本对话子库的本地整理区（脚本、导入清单、检查脚本等） |
| `docs/` | 项目结构、环境变量、维护审计、公开音频来源等补充文档 |

## 本地运行

### 1. 安装依赖

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 初始化一个最小示例库

仓库默认**不附带完整 `corpus.db`**。如果你只是想把网站跑起来看结构，可以先用示例数据初始化：

```bash
python init_db.py
python prepare_corpus_fts5.py
```

这会使用 `data/sample_corpus.json` 生成一个最小可运行的 `corpus.db`。

### 3. 启动网站

```bash
python app.py
```

默认情况下：

- 数据库路径是项目根目录下的 `corpus.db`
- 上传目录是 `uploads/submissions/`
- 检索后端默认使用 SQLite FTS5

## 导入你自己的语料

如果你已经有标准化 CSV，可以使用批量导入脚本：

```bash
python import_bulk_csv.py path/to/your.csv --batch my_import_batch
python prepare_corpus_fts5.py
```

`import_bulk_csv.py` 面向统一格式的语料 CSV；导入完成后建议立即重建 FTS 索引，保证检索结果与主表同步。

## 维护对话派生表

如果你更新了对话型语料，尤其是需要使用“对话句法 / 共鸣检索”时，通常还要同步维护下面两张派生表：

```bash
python migrate_dialogue_turns.py --batch-size 1000
python rebuild_dialogue_pairs.py --batch-size 5000
```

如果是 PostgreSQL 环境下的中断恢复或增量补建，可参考脚本参数：

- `migrate_dialogue_turns.py --resume`
- `migrate_dialogue_turns.py --status`
- `rebuild_dialogue_pairs.py --append-new`

## 文本对话子库工作流

`talkdata/` 目录主要服务于“文本对话”和“古代汉语”相关子库的建设。一个典型流程通常是：

1. 在本地准备或审核文本对话 CSV；
2. 视需要将滑动窗口式单位合并为更大的完整对话；
3. 通过 `talkdata/import_review_exports_to_local.py` 整理字段并导入本地库；
4. 重建 FTS、`dialogue_turns`、`dialogue_pairs`；
5. 用 `talkdata/inspect_online_text_dialogue.py` 等脚本抽查线上 / 本地状态。

需要特别注意：

- `talkdata/raw_chat_corpus/`
- `talkdata/review_exports/`
- `talkdata/import_ready/`
- `.llm_*_cache/`

这些目录通常包含大体积原始语料、中间缓存、审核导出和本地工作文件，默认都被 `.gitignore` 排除，不会随仓库一起发布。

## 环境变量

最常用的环境变量包括：

```text
SECRET_KEY=...
ADMIN_USERNAME=...
ADMIN_PASSWORD=...
DATABASE_BACKEND=sqlite
DATABASE_PATH=./corpus.db
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME
CORPUS_SEARCH_BACKEND=fts
UPLOAD_FOLDER=./uploads/submissions
STORAGE_BACKEND=local
OPENAI_API_KEY=...
TRANSCRIBE_MODEL=whisper-1
```

如果使用对象存储，还需要配置：

```text
S3_ENDPOINT_URL=...
S3_BUCKET=...
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_PUBLIC_BASE_URL=...
S3_REGION=auto
CORPUS_AUDIO_OBJECT_PREFIX=corpus/audio
```

更完整的说明见：

- [docs/deployment_env.md](docs/deployment_env.md)

## 部署

仓库已经包含最小 Render 配置：

- `render.yaml`
- `Procfile`

当前启动命令为：

```bash
gunicorn app:app
```

Render 上最基本的配置是：

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

## 已知限制

这是一个很重要的现实说明：

1. **PostgreSQL 已经接入，但还不是对 SQLite 的完全无缝替代。**  
   当前仓库已经支持 PostgreSQL 连接、迁移与部分运行路径，但仍有若干检索和维护逻辑历史上依赖 SQLite / FTS5。

2. **完整语料和中间产物不在 Git 仓库里。**  
   GitHub 仓库主要保存代码、文档、少量示例与维护脚本；真正的大型原始语料、审核导出、缓存和数据库备份通常保留在本地或独立存储中。

3. **`app.py` 与 `corpus_repository.py` 仍然偏大。**  
   仓库中已经开始把部分逻辑拆到 `services/`，但整体仍处于“逐步服务化 / 模块化”的演进阶段。

4. **Render 免费文件系统不适合长期持久化正式数据库与上传文件。**  
   如果要长期稳定运行，建议使用 PostgreSQL + 对象存储，而不是依赖 SQLite 和本地上传目录。

## 研究与使用边界

本项目优先面向研究、教学展示、语料建设与方法实验。对于音频、视频、网络平台内容和文学文本的使用，需要分别遵守来源许可、研究伦理与平台规则。仓库中关于公开音频来源与展示边界的说明，可参考：

- [docs/public_audio_sources.md](docs/public_audio_sources.md)

## 进一步阅读

- [docs/project_structure.md](docs/project_structure.md) — 项目结构与文件职责
- [docs/deployment_env.md](docs/deployment_env.md) — 环境变量说明
- [docs/maintenance_audit.md](docs/maintenance_audit.md) — 结构风险与整理路线
- [docs/public_audio_sources.md](docs/public_audio_sources.md) — 公开音频与许可边界

---

如果你把这个项目看成一个“网站”，它已经能跑、能检索、能投稿、能展示上下文。  
如果你把它看成一个“研究基础设施”，它更重要的意义在于：把汉语对话从零散资源整理为**可检索、可回溯、可比较、可扩展**的互动知识空间。
