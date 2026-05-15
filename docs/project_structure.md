# 项目结构说明

本文档记录当前 Flask 语料库网站的主要目录、核心文件职责，以及继续开发时需要保护的数据库和数据资产。

## 项目定位

项目名称：现代汉语对话语料库

技术栈：

- 后端：Flask
- 当前主数据库：SQLite，文件为项目根目录下的 `corpus.db`
- 预留数据库：PostgreSQL，通过 `DATABASE_BACKEND=postgres` 和 `DATABASE_URL` 配置
- 前端：Jinja2 模板、普通 CSS、原生 JavaScript
- 部署：Render + gunicorn
- 文件存储：本地目录或 S3/R2 兼容对象存储

核心用途：

- 检索现代汉语对话语料。
- 展示关键词上下文、来源、年份、类别、音频片段。
- 接收用户投稿文本、TXT、音频、视频等材料。
- 管理员审核投稿并写入语料库。
- 支持对话句法检索、共鸣检索和跨句图谱。

## 根目录主要文件

| 路径 | 作用 | 备注 |
|---|---|---|
| `app.py` | Flask 主入口，注册路由，处理页面渲染、投稿、后台、搜索、共鸣检索、音频路由 | 当前文件较大，后续适合拆分为 routes 和 services |
| `corpus_repository.py` | 语料库数据访问、搜索、派生表构建、共鸣检索、投稿记录操作 | 当前承担 repository、service、schema 初始化等多重职责 |
| `database.py` | 数据库连接封装，支持 SQLite 和初步 PostgreSQL 后端 | PostgreSQL 还不是完整运行时替换 |
| `storage_utils.py` | 本地上传、S3/R2 文件上传下载、语料音频响应 | 音频路由依赖此文件 |
| `db_utils.py` | 内容哈希和 UTC 时间等小工具 | 低风险 |
| `requirements.txt` | Python 依赖 | Render build 会使用 |
| `Procfile` | gunicorn 启动命令 | 当前为 `web: gunicorn app:app` |
| `render.yaml` | Render 服务配置 | 当前配置了 `CORPUS_SEARCH_BACKEND=fts` |
| `schema_postgres.sql` | PostgreSQL schema 参考 | 迁移 PostgreSQL 时使用 |
| `README.md` | 本地运行和部署说明 | 需要持续更新 |

## 页面模板

| 路径 | 作用 |
|---|---|
| `templates/home.html` | 首页和普通检索入口 |
| `templates/results.html` | 普通检索和高级检索结果页，含结果弹窗和音频播放逻辑 |
| `templates/resonance.html` | 对话句法检索页面 |
| `templates/_resonance_results.html` | 共鸣检索结果局部模板 |
| `templates/submit.html` | 用户投稿页面 |
| `templates/data_sources.html` | 数据来源和许可说明 |
| `templates/admin_login.html` | 管理员登录 |
| `templates/admin.html` | 管理员手动录入 |
| `templates/admin_list.html` | 管理员查看已有数据 |
| `templates/admin_submissions.html` | 投稿审核列表 |
| `templates/admin_submission_detail.html` | 投稿详情、转写、审核、下载 |

## 静态资源

| 路径 | 作用 |
|---|---|
| `static/style.css` | 全站样式，覆盖首页、结果页、弹窗、后台、共鸣检索、跨句图谱 |
| `static/resonance.js` | 共鸣检索异步加载、分页、上下文加载、跨句图谱渲染和导出 |
| `static/audio_imports/` | 示例或导入音频，本地运行时可能使用，不应提交大音频 |

## 数据库和数据目录

| 路径 | 作用 | Git 处理 |
|---|---|---|
| `corpus.db` | 当前主 SQLite 数据库 | 不提交 |
| `corpus.db-wal`、`corpus.db-shm`、`*.db-journal` | SQLite 运行时临时文件 | 不提交 |
| `db_backup/` | 本地数据库备份 | 不提交 |
| `data/sample_corpus.json` | 小型样例数据 | 可提交 |
| `talkdata/raw_chat_corpus/` | 原始大语料 | 不提交 |
| `talkdata/import_ready/` | 待导入或已导出的 CSV | 默认不提交，个别小样例如需提交要单独确认 |
| `talkdata/audio_raw/` | 原始音频 | 不提交 |
| `talkdata/review_exports/` | LLM 或人工审核导出 | 默认不提交 |
| `uploads/submissions/` | 用户投稿上传文件 | 只保留 `.gitkeep`，不提交实际上传文件 |

## 导入、迁移、重建和诊断脚本

当前脚本仍放在根目录和 `talkdata/` 中，后续建议移动到 `scripts/` 分组。

| 类型 | 当前文件示例 |
|---|---|
| 初始化 | `init_db.py` |
| CSV 导入 | `import_bulk_csv.py`、`import_preview_csv.py` |
| FTS 构建 | `prepare_corpus_fts5.py` |
| SQLite/Postgres 迁移 | `migrate_db.py`、`migrate_sqlite_to_postgres.py`、`schema_postgres.sql` |
| 音频迁移 | `migrate_audio_db.py`、`migrate_audio_files_to_s3.py` |
| 对话派生表 | `migrate_dialogue_turns.py`、`rebuild_dialogue_pairs.py`、`check_dialogue_indexes.py` |
| 诊断 | `diagnose_audio_routes.py`、`diagnose_db_connection.py`、`diagnose_postgres_search.py`、`diagnose_r2_storage.py` |
| 数据准备 | `talkdata/prepare_*.py`、`talkdata/convert_*.py`、`talkdata/run_*.py` |

## 不能轻易动的部分

以下部分牵涉数据一致性、线上访问或部署行为，不应在没有备份和验证的情况下修改：

- `corpus.db`
- `corpus_entries` 主语料表
- `dialogue_turns` 派生话轮表
- `dialogue_pairs` 派生相邻话轮表
- `corpus_entries_fts` 及其 FTS5 内部表
- `/audio/<path:filename>` 和 `/corpus/audio/<path:filename>` 音频路由
- 投稿审核流程：`corpus_submissions` 到 `corpus_entries` 或 `multimodal_entries`
- Render 启动入口：`gunicorn app:app`
- S3/R2 相关对象 key 和公开访问规则

## 数据库安全注意事项

1. 修改 schema、重建 FTS、重建 `dialogue_turns` 或 `dialogue_pairs` 前，必须备份 `corpus.db`。
2. 不要直接在生产库上试验导入脚本。
3. `dialogue_turns` 和 `dialogue_pairs` 是派生表，更新拆分逻辑或语料内容后需要重新构建。
4. `corpus_entries_fts` 必须和 `corpus_entries` 保持同步，否则普通检索可能返回旧结果或漏结果。
5. Render 免费环境文件系统不是长期持久存储，正式部署应使用 PostgreSQL 和对象存储。
6. 上传文件、音频文件和大 CSV 不应进入 Git。

