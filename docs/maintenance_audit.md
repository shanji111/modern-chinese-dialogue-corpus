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

## 音频服务整理记录

### 第 1 刀：抽出 corpus audio 展示链路

已新增 `services/audio_service.py`，用于承接原本分散在 `app.py` 和 `storage_utils.py` 中的语料音频展示辅助逻辑。当前搬出的函数包括：

- `safe_child_path`
- `find_local_corpus_audio`
- `normalize_corpus_audio_object_key`
- `corpus_audio_exists_locally`
- `is_remote_url`
- `get_corpus_audio_response`
- `build_corpus_audio_url`

这一刀只覆盖 corpus audio 展示链路，不处理投稿附件上传、附件下载或删除逻辑。`storage_utils.py` 中的 `LocalStorageBackend`、`S3StorageBackend`、`save_submission_file`、`get_submission_download_response`、`delete_submission_file` 仍保留原位。

### app.py 当前仍保留的职责

`app.py` 中音频相关部分目前仍保留以下职责：

- 在普通检索结果中为 `audio_file` 注入 `audio_url`。
- 在共鸣检索结果中为 `audio_file` 注入 `audio_url`。
- 暴露 `/audio/<path:filename>` 路由。
- 暴露 `/corpus/audio/<path:filename>` 路由。
- 保留后台投稿附件下载路由 `/admin/submissions/<id>/download`。

也就是说，语料音频展示链路已经服务化，但 Flask 路由入口和后台附件下载链路仍在 `app.py`。

### 未改动范围

本次音频服务第 1 刀没有修改：

- 数据库结构或数据内容。
- 路由 URL。
- 模板文件。
- `static/` 前端资源。
- `corpus_repository.py`。
- 投稿附件上传、下载、删除链路。
- S3/R2 投稿文件存储逻辑。
- 错误文案和返回结构。

### 验证记录

已使用以下方式验证：

- `compile(app.py)` 通过。
- `compile(services/audio_service.py)` 通过。
- `python -B -c "import services.audio_service"` 通过。
- 本地 SQLite 环境下，音频链路手动测试通过。

手动测试已确认本地模式下的 corpus audio 展示链路没有明显回归。

### 后续建议

1. 先把本次 `audio_service.py` 第 1 刀与前面的转写服务整理作为一组稳定成果保存。
2. 下一步优先做 `storage_utils.py` 的只读职责拆分分析，不急着继续移动投稿附件链路。
3. 在未单独验证 S3/R2 音频访问前，不要继续改 `get_submission_download_response` 或 `S3StorageBackend` 的附件响应逻辑。

## 投稿附件存储服务整理记录

### 第 1 刀：新增 `services/submission_storage_service.py`

已新增 `services/submission_storage_service.py`，先将 `app.py` 直接依赖的投稿附件接口层收口到 service 中。当前新增的薄包装函数包括：

- `allowed_submission_file`
- `save_submission_upload`
- `build_submission_download_response`
- `delete_submission_upload`

这 4 个函数当前仍然直接调用 `storage_utils.py` 中的既有实现，不改变上传、下载、删除的底层行为，也不改本地存储和 S3/R2 存储分发逻辑。

### app.py 当前已变薄的部分

`app.py` 中与投稿附件相关的 3 个直接调用点已经改为走 `services/submission_storage_service.py`：

- 投稿页上传文件时，调用 `save_submission_upload(upload)`。
- 管理员后台下载投稿附件时，调用 `build_submission_download_response(...)`。
- 管理员后台删除未审核投稿附件时，调用 `delete_submission_upload(...)`。

也就是说，`app.py` 目前已经不再直接调用 `storage_utils.save_submission_file()`、`storage_utils.get_submission_download_response()` 和 `storage_utils.delete_submission_file()`，而是通过 service 做一层明确转发。

### 仍保留在 app.py 的职责

本轮整理后，`app.py` 仍保留以下职责：

- 处理投稿表单和管理员后台的 Flask 路由入口。
- 负责请求参数读取、权限判断和页面响应。
- 继续保留数据库写入、审核状态变更和 `render_template(...)` 返回逻辑。

也就是说，这一刀只收口“投稿附件接口层”，没有继续移动数据库逻辑，也没有移动 Flask 响应逻辑。

### 未改动范围

本次投稿附件存储服务第 1 刀没有修改：

- 数据库结构或数据内容。
- 路由 URL。
- 模板文件。
- `static/` 前端资源。
- `corpus_repository.py`。
- `storage_utils.py` 的底层本地/S3/R2 存储实现。
- 错误文案、异常类型和返回结构。

### 验证记录

已使用以下方式验证：

- `compile(app.py)` 通过。
- `compile(services/submission_storage_service.py)` 通过。
- `python -B -c "import services.submission_storage_service"` 通过。

后续需要继续手动验证以下场景：

1. 投稿页上传文本文件和媒体文件。
2. 管理员后台下载投稿附件。
3. 管理员后台删除未审核投稿并确认附件处理行为正常。

### 后续建议

1. 在完成人工验证前，不要继续深入改 `storage_utils.py` 的底层后端类。
2. 下一步适合继续做 `storage_utils.py` 的只读职责拆分分析，区分“投稿附件链路”和“语料音频链路”的底层实现边界。
3. 在未单独验证 S3/R2 模式的投稿附件下载和删除行为前，不要继续动 `S3StorageBackend` 的响应逻辑。

### 第 2 刀：将投稿附件底层实现内聚到 service

在第 1 刀完成接口层收口并通过人工验证后，`services/submission_storage_service.py` 已继续整理为“自带底层实现”的投稿附件服务，不再仅仅作为 `storage_utils.py` 的薄包装。

当前已经内聚到 `services/submission_storage_service.py` 的内容包括：

- 配置与扩展名判断：`STORAGE_BACKEND`、`UPLOAD_FOLDER`、`ALLOWED_SUBMISSION_EXTENSIONS`
- 通用 helper：`extract_extension`、`is_allowed_extension`、`normalized_secure_filename`
- 调试 helper：`upload_debug_info`、`print_upload_debug`
- 文件处理 helper：`sha256_file`、`decode_text_bytes`
- 本地附件后端：`LocalStorageBackend`
- S3/R2 附件后端：`S3StorageBackend`
- 服务入口：`allowed_submission_file`、`save_submission_upload`、`build_submission_download_response`、`delete_submission_upload`

这意味着：投稿附件上传、下载、删除这条链路的核心实现，已经可以在 service 层独立阅读和维护，而不必再先跳回 `storage_utils.py` 追踪逻辑。

### 人工验证结果

在该整理完成后，已手动验证以下场景，结果均正常：

1. 投稿页上传文本文件。
2. 投稿页上传媒体文件。
3. 管理员后台下载投稿附件。
4. 管理员后台删除未审核投稿。

这说明在本地 SQLite 环境下，投稿附件链路没有出现明显回归。

### storage_utils.py 当前状态

完成这一刀后，`storage_utils.py` 目前更适合作为“兼容层 + 共用存储定义”看待：

- 其中仍保留旧的投稿附件实现。
- `services/audio_service.py` 当前仍依赖其中的部分配置和 `S3StorageBackend`。
- `services/transcription_service.py` 当前仍依赖其中的 `UPLOAD_FOLDER` 和 `S3StorageBackend`。
- 诊断脚本 `diagnose_audio_routes.py` 当前仍直接引用 `storage_utils.normalize_corpus_audio_object_key(...)`。

因此，现阶段**不建议直接删除** `storage_utils.py` 中的旧实现，也不建议立即大规模收缩该文件，而应先把现有引用逐步收口，再决定是否将其降级为纯兼容层。

### 未改动范围

本次投稿附件存储服务第 2 刀没有修改：

- 数据库结构或数据内容。
- 路由 URL。
- 模板文件。
- `static/` 前端资源。
- `corpus_repository.py`。
- `app.py` 的路由、数据库写入和页面响应逻辑。
- 错误文案、异常类型和返回结构。

### 验证记录

已使用以下方式验证：

- `compile(app.py)` 通过。
- `compile(services/submission_storage_service.py)` 通过。
- `python -B -c "import services.submission_storage_service"` 通过。
- 本地 SQLite 环境下，投稿附件链路手动测试通过。

### 后续建议

1. 下一步适合继续做 `storage_utils.py` 的“兼容层引用清单”只读分析，先弄清哪些模块还依赖它的旧实现。
2. 在未单独验证 S3/R2 投稿附件下载和删除行为前，不要继续改 `S3StorageBackend` 的响应逻辑。
3. 在未先收口 `diagnose_audio_routes.py`、`services/audio_service.py`、`services/transcription_service.py` 的引用前，不要直接删除 `storage_utils.py` 中的旧 helper。

### 后续小步收口记录

在第 2 刀完成并通过人工验证后，已继续做两处低风险引用收口：

1. `services/transcription_service.py` 已改为从 `services/submission_storage_service` 导入 `S3StorageBackend` 和 `UPLOAD_FOLDER`，不再直接依赖 `storage_utils.py` 的这两个投稿附件相关定义。
2. `diagnose_audio_routes.py` 已改为从 `services/audio_service` 导入 `normalize_corpus_audio_object_key(...)`，不再直接引用 `storage_utils.py` 中对应的旧音频 helper。

这两处调整都属于“只改 import，不改逻辑”的低风险整理，目的是逐步将运行时和诊断脚本的依赖收口到新的 service 边界上。

### 兼容层依赖进一步收口

在继续整理后，已又完成两处低风险依赖收口：

1. `app.py` 已改为从 `services/submission_storage_service` 导入 `print_upload_debug(...)`，不再直接依赖 `storage_utils.py` 的上传调试函数。
2. `services/audio_service.py` 已改为直接定义自身所需的音频目录与对象 key 配置，并从 `services/submission_storage_service` 导入 `S3StorageBackend`，不再直接依赖 `storage_utils.py`。

完成这一步后，已对运行时代码做全局搜索，当前 `app.py`、`services/*.py` 和 `talkdata/*.py` 中**不再存在**对 `storage_utils.py` 的直接 import。

这意味着：

- `storage_utils.py` 当前已经不再是运行时主入口。
- 其现有内容更适合作为“兼容层候选”或“待收缩的旧实现集合”来看待。
- 后续如果继续整理，重点将转为：先确认是否仍需要保留该文件供临时脚本或外部调用使用，再决定是否收缩、注释或降级。

### storage_utils.py 兼容层落地

在运行时依赖基本收口完成后，`storage_utils.py` 已进一步整理为显式兼容层：

- 保留原有模块名和对外函数名，避免旧脚本或临时工具因 import 路径变化而失效。
- 模块内部不再保留一整套重复实现，而是转发到：
  - `services.submission_storage_service`
  - `services.audio_service`
- 兼容层目前保留的主要对外名称包括：
  - 投稿附件链路：`LocalStorageBackend`、`S3StorageBackend`、`allowed_file`、`save_submission_file`、`get_submission_download_response`、`delete_submission_file`
  - 语料音频链路：`safe_child_path`、`find_local_corpus_audio`、`normalize_corpus_audio_object_key`、`corpus_audio_exists_locally`、`is_remote_url`、`get_corpus_audio_response`
  - 共用配置与 helper：`UPLOAD_FOLDER`、`STORAGE_BACKEND`、`CORPUS_AUDIO_DIRS`、`CORPUS_AUDIO_OBJECT_PREFIX`、`print_upload_debug` 等

这样做的目标是：

1. 让新的 service 边界成为唯一维护入口。
2. 保留旧 import 面，减少外部脚本、诊断脚本和一次性工具的迁移压力。
3. 降低后续删除重复实现时的认知成本。

### 验证记录

已使用以下方式验证：

- `compile(storage_utils.py)` 通过。
- `python -B -c "import storage_utils"` 通过。
- 兼容层别名检查通过：`S3StorageBackend`、`get_corpus_audio_response`、`allowed_file('demo.mp3')` 均可正常访问。
- `python -B -c "import services.audio_service, services.submission_storage_service, services.transcription_service"` 通过。
