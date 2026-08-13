# 部署环境变量说明

本文档整理本项目在本地、Render、SQLite、PostgreSQL、本地文件存储和 S3/R2 对象存储场景下涉及的环境变量。

## Flask 和管理员账号

### `SECRET_KEY`

用途：Flask session 加密密钥。

本地开发可以不设置，此时 `app.py` 会使用开发用 fallback。生产环境必须设置足够长、随机、不可公开的值。

示例：

```text
SECRET_KEY=replace-with-a-long-random-secret
```

注意：

- 不要提交到 Git。
- 不要写入源码。
- Render 中应通过 Environment Variables 配置。

### `ADMIN_USERNAME`

用途：管理员登录用户名。

示例：

```text
ADMIN_USERNAME=admin
```

### `ADMIN_PASSWORD`

用途：管理员登录密码。

示例：

```text
ADMIN_PASSWORD=replace-with-a-strong-password
```

注意：

- 生产环境必须设置。
- 不要使用简单密码。
- 不要提交到 Git 或文档示例之外的配置文件。

### `SESSION_COOKIE_SECURE`

用途：控制管理员会话 Cookie 是否只通过 HTTPS 发送。

Render 环境默认开启；本地 HTTP 开发默认关闭。其他生产环境应明确设置：

```text
SESSION_COOKIE_SECURE=1
```

## 数据库配置

### `DATABASE_BACKEND`

用途：选择数据库后端。

可选值：

- `sqlite`：默认值，使用本地 SQLite 文件。
- `postgres`：使用 PostgreSQL。

示例：

```text
DATABASE_BACKEND=sqlite
```

注意：当前代码虽然预留 PostgreSQL，但仍有部分 SQLite/FTS5 相关逻辑，PostgreSQL 不是完全无缝替换。

### `DATABASE_PATH`

用途：SQLite 数据库路径。

默认值：项目根目录下的 `corpus.db`。

Render 示例：

```text
DATABASE_PATH=/opt/render/project/src/corpus.db
```

注意：

- Render 免费 Web Service 的本地文件系统不适合长期持久化数据库。
- 如果使用 SQLite，上线前必须明确备份和持久化策略。

### `DATABASE_URL`

用途：PostgreSQL 连接串，仅在 `DATABASE_BACKEND=postgres` 时使用。

示例：

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME
```

注意：

- 不要打印完整连接串。
- `database.py` 中已有脱敏辅助函数。
- 密码必须放在环境变量，不要写入源码。

### `CORPUS_SEARCH_BACKEND`

用途：选择语料检索后端。

当前 Render 配置使用：

```text
CORPUS_SEARCH_BACKEND=fts
```

可选值通常为：

- `fts`：SQLite FTS5 检索。
- `like`：LIKE 模糊匹配。

注意：使用 `fts` 时必须确保 `corpus_entries_fts` 已构建且和 `corpus_entries` 同步。

### `POSTGRES_FAST_SEARCH`

用途：PostgreSQL 场景下跳过部分总数统计以提升响应速度。

示例：

```text
POSTGRES_FAST_SEARCH=1
```

仅在 PostgreSQL 检索路径确认可用后再开启。

### `ENABLE_QUERY_TIMING`

用途：打印查询耗时诊断日志。

示例：

```text
ENABLE_QUERY_TIMING=1
```

生产环境可短期开启排查性能，长期建议关闭。

### `VISITOR_ONLINE_WINDOW_SECONDS`

用途：设置网站“当前在线”人数的活跃时间窗口，单位为秒。

默认值：

```text
VISITOR_ONLINE_WINDOW_SECONDS=90
```

允许范围为 30–300 秒。访问统计每 30 秒刷新一次；累计访客按匿名浏览器标识去重。IP 安全日志是否启用及其保存期限由下列独立变量控制。

### `VISITOR_IP_LOGGING`

用途：控制是否记录用于安全维护的 IP 聚合日志。

默认值：

```text
VISITOR_IP_LOGGING=1
```

设为 `0`、`false`、`no` 或 `off` 可关闭。开启时记录 IP、时间、请求方法、路径和响应状态，不记录请求正文、检索词或浏览器指纹。

### `VISITOR_IP_RETENTION_DAYS`

用途：设置 IP 安全日志的自动保存天数。

默认值：

```text
VISITOR_IP_RETENTION_DAYS=30
```

允许范围为 1–365 天。到期记录由访问统计服务自动清理；仍处于封禁状态的 IP 会保留在独立封禁表中，直至管理员解封。

### `VISITOR_HISTORY_RETENTION_DAYS`

用途：设置在线人数快照和每日匿名访客明细的保存天数。

默认值：

```text
VISITOR_HISTORY_RETENTION_DAYS=365
```

允许范围为 7–1095 天。

### `VISITOR_STATS_TIMEZONE`

用途：设置后台访问曲线、每日访客和指定时间查询使用的时区。

默认值：

```text
VISITOR_STATS_TIMEZONE=Asia/Shanghai
```

### `TRUST_X_FORWARDED_FOR`

用途：在没有可信 `CF-Connecting-IP` 时，是否允许读取 `X-Forwarded-For` 的第一个地址。

默认值为关闭：

```text
TRUST_X_FORWARDED_FOR=0
```

生产站点经 Cloudflare / Render 代理时优先使用带 `CF-Ray` 的 `CF-Connecting-IP`。只有确认上游代理会覆盖并清洗 `X-Forwarded-For` 时才应开启本变量，避免攻击者伪造 IP。

## 反爬与自动化滥用防护

应用层防护默认开启。它按 IP 和匿名访客 Cookie 的哈希值同时计数，对检索、共鸣接口、上下文、导出、音频和后台登录分别限流；同时拒绝跨站数据请求、已知脚本客户端直接访问数据路由、超过配置上限的深分页，并设置短期蜜罐。管理员登录会话和可信 IP 不受此限制。

### 总开关与可信地址

```text
ANTI_SCRAPING_ENABLED=1
ANTI_SCRAPE_TRUSTED_IPS=203.0.113.10,2001:db8::10
```

`ANTI_SCRAPE_TRUSTED_IPS` 只应用于确实受控的内部出口地址，不应加入动态住宅 IP 或大范围网段。

### 默认阈值

| 变量 | 默认值 | 含义 |
| --- | ---: | --- |
| `ANTI_SCRAPE_GENERAL_REQUESTS` | 240 | 普通请求每分钟上限 |
| `ANTI_SCRAPE_SEARCH_REQUESTS` | 40 | `/search`、`/browse` 和搜索计数每分钟上限 |
| `ANTI_SCRAPE_RESONANCE_REQUESTS` | 24 | 共鸣检索每分钟上限 |
| `ANTI_SCRAPE_CONTEXT_REQUESTS` | 36 | 上下文和图谱接口每分钟上限 |
| `ANTI_SCRAPE_EXPORT_REQUESTS` | 6 | 图谱导出每 10 分钟上限 |
| `ANTI_SCRAPE_AUDIO_REQUESTS` | 30 | 音频请求每分钟上限 |
| `ANTI_SCRAPE_LOGIN_REQUESTS` | 10 | 后台登录每 15 分钟上限 |
| `ANTI_SCRAPE_MAX_SEARCH_PAGE` | 100 | 公开检索允许访问的最深页码；设为 `0` 可取消页码限制 |
| `ANTI_SCRAPE_HONEYPOT_PENALTY_SECONDS` | 86400 | 命中蜜罐后的临时限制时长 |

每组还可用同名的 `*_PENALTY_SECONDS` 变量调整触发后的限制时长，具体名称见 `services/anti_scraping_service.py`。响应会携带 `RateLimit-Limit`、`RateLimit-Remaining`、`RateLimit-Reset`；触发频率限制时返回 HTTP 429 和 `Retry-After`。

这些计数保存在单个 Gunicorn 进程内，适合作为应用最后一道防线，不是分布式 WAF 的替代品。若增加多个 worker 或多个 Render 实例，每个进程会各自计数；此时必须把主要限流放到 CDN/WAF，或将应用计数迁移到 Redis 等共享存储。

### 上线前的边缘防护

正式域名建议代理到 Cloudflare 或同类 CDN/WAF，并完成以下配置：

1. 开启 Bot Fight Mode（付费方案可用更细的 Bot Management 分数）。
2. 对 `/search*`、`/browse*`、`/api/resonance*`、`/resonance/data*`、`/resonance/context*` 和 `/api/diagraph*` 分组设置速率规则，先使用 Managed Challenge，再对持续违规流量封禁。
3. 计数条件优先组合 IP、会话 Cookie 和可用的 JA3/JA4 指纹；不要只依赖可伪造的 User-Agent。
4. 排除经过验证的正常搜索引擎，并观察至少一天的正常流量分布后再收紧阈值。
5. 确认访问者无法绕过 CDN 直接请求 Render 原站；否则边缘规则可被直接绕过。

`robots.txt` 仅用于向守规矩的爬虫声明禁止抓取数据入口，不能替代上述服务端控制。

## 上传和对象存储

### `UPLOAD_FOLDER`

用途：本地上传文件保存目录。

默认值：`uploads/submissions`。

Render 示例：

```text
UPLOAD_FOLDER=/opt/render/project/src/uploads/submissions
```

注意：

- 本地上传文件默认不提交 Git。
- Render 免费环境文件系统不适合长期保存用户上传文件。

### `STORAGE_BACKEND`

用途：选择上传和音频文件存储后端。

可选值：

- `local`：默认，本地文件系统。
- `s3`：S3/R2 兼容对象存储。

示例：

```text
STORAGE_BACKEND=s3
```

## S3/R2 相关变量

项目使用 S3 兼容接口，也可连接 Cloudflare R2。

### `S3_ENDPOINT_URL`

用途：S3/R2 endpoint。

R2 示例：

```text
S3_ENDPOINT_URL=https://ACCOUNT_ID.r2.cloudflarestorage.com
```

### `S3_BUCKET`

用途：bucket 名称。

```text
S3_BUCKET=your-bucket-name
```

### `S3_ACCESS_KEY_ID`

用途：访问 key。

```text
S3_ACCESS_KEY_ID=your-access-key-id
```

### `S3_SECRET_ACCESS_KEY`

用途：访问 secret。

```text
S3_SECRET_ACCESS_KEY=your-secret-access-key
```

### `S3_PUBLIC_BASE_URL`

用途：公开访问基础 URL。如果设置，下载和音频访问会直接 redirect 到公开 URL。

```text
S3_PUBLIC_BASE_URL=https://cdn.example.com
```

如果不设置，代码会尝试生成预签名 URL。

### `S3_REGION`

用途：S3 region。R2 通常可用 `auto`。

默认值：`auto`。

```text
S3_REGION=auto
```

### `CORPUS_AUDIO_OBJECT_PREFIX`

用途：语料音频在对象存储中的 key 前缀。

默认值：

```text
CORPUS_AUDIO_OBJECT_PREFIX=corpus/audio
```

例如数据库中 `audio_file=demo1.m4a` 时，S3/R2 模式会查找：

```text
corpus/audio/demo1.m4a
```

注意：如果 `audio_file` 已经是完整 URL，则代码会直接 redirect，不再拼接对象存储前缀。

## 转写相关变量

### `OPENAI_API_KEY`

用途：管理员对音频或视频投稿执行转写时调用 OpenAI API。

示例：

```text
OPENAI_API_KEY=sk-...
```

注意：

- 没有设置时，转写接口会返回配置错误。
- 不影响普通检索和浏览。
- 不要提交到 Git。

### `TRANSCRIBE_MODEL`

用途：音频转写模型名。

默认值：

```text
TRANSCRIBE_MODEL=whisper-1
```

如需更换模型，先确认当前 OpenAI API 支持该模型，并在测试环境验证。

## Render 部署注意事项

当前 `render.yaml` 关键配置：

```yaml
services:
  - type: web
    name: modern-chinese-dialogue-corpus
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app
    envVars:
      - key: CORPUS_SEARCH_BACKEND
        value: fts
```

当前 `Procfile`：

```text
web: gunicorn app:app
```

注意事项：

1. 后续拆分 `app.py` 时，必须保持 `app.py` 中继续导出名为 `app` 的 Flask 实例，除非同步修改 Render 和 Procfile。
2. 生产环境必须设置 `SECRET_KEY`、`ADMIN_USERNAME`、`ADMIN_PASSWORD`。
3. 如果仍用 SQLite，必须明确 `DATABASE_PATH` 指向哪里，并接受 Render 免费环境文件不持久的风险。
4. 正式使用建议迁移到 PostgreSQL，并使用对象存储保存上传文件和音频。
5. 如果启用 `STORAGE_BACKEND=s3`，必须同时配置 `S3_ENDPOINT_URL`、`S3_BUCKET`、`S3_ACCESS_KEY_ID`、`S3_SECRET_ACCESS_KEY`。
6. 大数据库、上传文件、音频和导入 CSV 不应随部署代码提交。

