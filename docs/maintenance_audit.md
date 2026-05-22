# 维护审计报告

本文档记录当前项目结构体检结果和低风险整理路线。当前阶段只做诊断和文档整理，不改变功能代码。

## 总体判断

项目已经能支撑语料检索、投稿审核、音频播放、对话句法检索和跨句图谱，但代码结构正在接近单体文件维护上限。

主要风险集中在：

- `app.py` 过大，路由、服务逻辑、数据库查询、渲染辅助函数混在一起。
- `corpus_repository.py` 过大，承担 repository、service、schema 初始化、派生表构建和算法逻辑。
- `templates/results.html` 中存在较长内联 JavaScript。
- `static/style.css` 和 `static/resonance.js` 还没有按页面或功能拆分。
- 大量数据文件、CSV、缓存、备份和脚本混在项目根目录或 `talkdata/` 下。

## 高风险文件

| 文件 | 当前作用 | 风险原因 | 建议 |
|---|---|---|---|
| `app.py` | Flask 入口和全部路由 | 约 1822 行，包含页面路由、API、投稿、后台、转写、搜索、共鸣、跨句图谱、音频响应辅助逻辑 | 后续按 Blueprint 和 service 渐进拆分 |
| `corpus_repository.py` | 数据访问和业务逻辑 | 约 2255 行，混合搜索 SQL、schema 初始化、投稿记录、派生表、共鸣算法 | 先按 search、submission、resonance、diagraph 分出 service/repository |
| `talkdata/` | 数据和脚本集合 | 目录体积大，原始语料、导入 CSV、脚本、缓存、审核导出混杂 | 大文件默认忽略，脚本后续迁到 `scripts/` |

## 中风险文件

| 文件 | 当前作用 | 风险原因 | 建议 |
|---|---|---|---|
| `templates/results.html` | 检索结果页 | 模板较长，包含弹窗、音频播放和搜索模式切换内联 JS | 优先把 JS 抽到 `static/results.js` |
| `static/style.css` | 全站样式 | 约 1458 行，已有模块注释但存在重复 selector | 先补分区和整理重复，不改变视觉 |
| `static/resonance.js` | 共鸣页交互 | 约 430 行，包含请求、分页、上下文、跨句图谱渲染 | 先加分区注释，再按功能拆分 |
| `storage_utils.py` | 文件存储和音频响应 | 本地/S3/R2 上传下载和音频响应混在一起 | 后续拆成 storage service 和 audio service |
| `render.yaml`、`Procfile` | 部署入口 | 当前简洁，但拆 `app.py` 时必须保持 `app` 导出 | 拆分前先确保 `gunicorn app:app` 不变 |

## 低风险文件

| 文件 | 当前作用 | 备注 |
|---|---|---|
| `database.py` | 数据库连接封装 | 结构较清晰，但 PostgreSQL 仍不是完整运行时替换 |
| `db_utils.py` | 小工具 | 可暂时不动 |
| `requirements.txt` | 依赖声明 | 可随功能需求小步更新 |
| `templates/home.html`、`templates/submit.html` | 首页和投稿页 | 可后续抽公共布局 |

## 发现的问题

1. `app.py` 中存在一批与 `corpus_repository.py` 重名的旧函数，后面又通过赋值绑定到 repository 实现。这说明历史代码没有完全清理，后续重构时要先确认引用关系。
2. `app.py` 中有少量明显乱码或私用区字符，主要出现在错误提示、启动诊断、投稿/转写提示附近。
3. `results.html` 仍使用 `onclick='openModal(...)'` 和内联脚本，页面逻辑较重。
4. `style.css` 存在重复 selector，例如 `.admin-toolbar`、`.diagraph-action-button`、`.bcc-search-box` 等。
5. `talkdata/import_ready/` 中有大量 CSV。当前 `.gitignore` 已补充忽略该目录，但已被 Git 跟踪的文件不会自动取消跟踪。
6. 根目录存在误生成的 `python`、`set` 0 字节文件，已加入忽略规则，但未删除。
7. `.transcription_tmp/` 当前属于临时目录，已忽略，不应提交。

## 暂时不要动的部分

- `corpus.db`
- `corpus.db-wal`、`corpus.db-shm`、`*.db-journal`
- `dialogue_turns`
- `dialogue_pairs`
- `corpus_entries_fts`
- 音频路由和 R2/S3 对象 key 规则
- 投稿审核写入流程
- Render 部署入口
- 大规模 CSS 视觉改动
- 大规模移动 `app.py` 或 `corpus_repository.py`

## 下一步整理路线

### 第 0 步：只清理和文档

已执行或建议执行：

- 更新 `.gitignore`。
- 新增结构说明、维护审计和部署环境文档。
- 标注不应提交的大文件和临时文件。
- 不删除、不移动、不修改数据库。

### 第 1 步：拆分 `app.py`

建议目标结构：

- `routes/search_routes.py`
- `routes/admin_routes.py`
- `routes/submission_routes.py`
- `routes/resonance_routes.py`
- `routes/audio_routes.py`
- `services/transcription_service.py`
- `services/diagraph_service.py`
- `services/resonance_service.py`
- `services/audio_service.py`
- `repositories/corpus_repository.py`
- `repositories/submission_repository.py`

第一刀建议从低耦合部分开始：

1. 抽 `services/transcription_service.py`，只搬函数，不改逻辑。
2. 抽 `routes/audio_routes.py` 和 `services/audio_service.py`，保持 URL 不变。
3. 再处理投稿和后台。
4. 搜索、共鸣、跨句图谱最后拆，因为牵涉查询性能和模板变量。

### 第 2 步：整理前端

- 把 `templates/results.html` 中的内联 JS 拆到 `static/results.js`。
- 保持 HTML data 属性稳定。
- 给 `static/resonance.js` 加功能分区注释。
- `static/style.css` 先整理分区和重复 selector，不改变视觉。

### 第 3 步：整理脚本

建议新增：

- `scripts/import/`
- `scripts/migrate/`
- `scripts/rebuild/`
- `scripts/diagnose/`
- `scripts/one_off/`

移动脚本前先全文搜索旧路径引用，并更新 README。

### 第 4 步：部署和数据安全

- 完善部署环境变量文档。
- 确认生产环境不依赖默认 `SECRET_KEY`。
- 正式部署建议 PostgreSQL + 对象存储。
- 大数据库、上传文件、大 CSV、缓存和备份默认不提交。

## 建议优先处理的问题

1. 清理 `app.py` 中明显乱码提示文本。
2. 把 `results.html` 内联 JS 抽到 `static/results.js`。
3. 对 `app.py` 中重复的旧查询函数做引用确认，确认无用后再删除。
4. 将 `talkdata/import_ready/` 的提交策略写清楚，避免误提交大 CSV。
5. 为重建 `dialogue_turns`、`dialogue_pairs`、FTS5 索引写标准操作文档。


## 转写服务整理记录

### 第 1 刀：抽出转写辅助函数

已新增 `services/transcription_service.py`，用于承接原本混在 `app.py` 中的音视频转写辅助逻辑。第 1 刀搬出的函数包括：

- `get_file_extension`
- `is_transcribable_submission`
- `is_video_submission_file`
- `safe_upload_file_path`
- `local_submission_file_path`
- `copy_submission_file_to_temp`
- `extract_audio_from_video`
- `transcribe_media_file`
- `cleanup_transcription_temp_files`

这一刀的目标是降低 `app.py` 体积，同时保持现有调用方式、错误文案、异常类型和业务流程不变。`TRANSCRIPTION_TEMP_DIR` 仍保留在 `app.py`，由路由传入 service，避免 service 反向依赖 Flask app。

### 第 2 刀：新增服务级编排函数

已在 `services/transcription_service.py` 中新增：

```python
transcribe_submission_media(submission, temp_dir, model_name) -> str
```

该函数封装了单次转写所需的文件处理流程：

1. 调用 `copy_submission_file_to_temp(submission, temp_dir)`，将本地或 S3/R2 投稿文件复制/下载到临时目录。
2. 调用 `is_video_submission_file(media_path, submission)` 判断是否为视频文件。
3. 如为视频，调用 `extract_audio_from_video(media_path, temp_dir)` 使用 `ffmpeg` 抽取音频。
4. 调用 `transcribe_media_file(target_media_path, model_name)` 执行 OpenAI 音频转写。
5. 使用 `finally` 调用 `cleanup_transcription_temp_files(temp_paths)`，确保成功或失败都清理本次产生的临时文件。

### app.py 当前仍保留的职责

`app.py` 中 `/admin/submissions/<id>/transcribe` 路由目前仍保留以下职责：

- 查询投稿：`corpus_repository.get_submission_by_id(submission_id)`
- 判断投稿是否存在。
- 调用 `is_transcribable_submission(submission)` 判断是否可转写。
- 读取 `TRANSCRIBE_MODEL`。
- 预检查 `OPENAI_API_KEY`。
- 创建 `TRANSCRIPTION_TEMP_DIR`。
- 调用 `transcribe_submission_media(submission, TRANSCRIPTION_TEMP_DIR, model_name)`。
- 判断转写结果是否为空，并保留原有 `RuntimeError` 文案。
- 调用 `corpus_repository.update_submission_text_content(submission_id, transcript)` 写回数据库。
- 保留所有 `render_template(...)` 成功、失败返回结构。

也就是说，数据库写入逻辑和 Flask 响应逻辑仍在 `app.py`，service 只负责文件准备、视频抽音频、调用转写和临时文件清理。

### 未改动范围

本次两刀整理没有修改：

- 数据库结构或数据内容。
- 路由 URL。
- 模板文件。
- `static/` 前端资源。
- `corpus_repository.py`。
- S3/R2 或本地文件复制逻辑。
- `ffmpeg` 抽音频参数。
- `OPENAI_API_KEY` / `TRANSCRIBE_MODEL` 检查行为。
- 错误文案、异常类型和返回结构。

### 验证记录

已使用以下方式验证：

- `compile(app.py)` 通过。
- `compile(services/transcription_service.py)` 通过。
- `python -B -c "import services.transcription_service"` 通过。

标准 `python -m py_compile app.py` / `python -m py_compile services/transcription_service.py` 在当前 Windows 环境中曾因 `__pycache__` 写入或 `.pyc` rename 权限问题失败，错误为 `[WinError 5] 拒绝访问`。这属于缓存文件写入权限问题，不是代码语法问题。

### 后续建议

1. 先手动测试管理员后台投稿转写功能，至少覆盖音频、视频、缺少 `OPENAI_API_KEY`、不可转写文件四类情况。
2. 确认转写成功后，再继续做音频路由的只读分析。
3. 暂时不要继续移动数据库写入逻辑，避免 service 层过早承担 repository 职责。
