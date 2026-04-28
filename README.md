# 现代汉语对话语料库

一个基于 Flask 和 SQLite 的现代汉语对话语料库检索与投稿展示网站，包含首页检索、用户投稿、管理员审核和多模态文件上传功能。

## 本地运行

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

macOS/Linux:

```bash
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

默认使用项目根目录下的 `corpus.db`，上传文件保存到 `uploads/submissions/`。

## Render 部署

1. 将项目上传到 GitHub 仓库。
2. 在 Render 新建 Web Service。
3. 连接 GitHub 仓库。
4. Build Command 填写：

```bash
pip install -r requirements.txt
```

5. Start Command 填写：

```bash
gunicorn app:app
```

可选环境变量：

```text
DATABASE_PATH=/opt/render/project/src/corpus.db
UPLOAD_FOLDER=/opt/render/project/src/uploads/submissions
CORPUS_SEARCH_BACKEND=fts
SECRET_KEY=请在生产环境设置一个足够长的随机字符串
ADMIN_USERNAME=请设置管理员账号
ADMIN_PASSWORD=请设置管理员密码
```

## 注意事项

生产环境必须设置 `SECRET_KEY`、`ADMIN_USERNAME` 和 `ADMIN_PASSWORD`。不要把管理员密码、数据库连接串或对象存储密钥写入代码或提交到仓库。

Render 免费 Web Service 的本地文件系统不是长期持久存储。预览网站中新增的 SQLite 写入和上传文件，在服务重启或重新部署后可能丢失。

当前版本适合给老师展示和预览。如果后续要正式开放公众投稿，建议迁移到 PostgreSQL，并使用 Render Persistent Disk 或对象存储保存 mp3、mp4 等上传文件。
