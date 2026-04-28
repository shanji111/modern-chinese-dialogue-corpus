from flask import Flask, render_template, request, redirect, session, url_for
from hmac import compare_digest
import os
import math
import re

from markupsafe import Markup, escape
from werkzeug.exceptions import RequestEntityTooLarge

import corpus_repository
from database import get_db_connection
from db_utils import compute_content_hash, utc_timestamp
from storage_utils import (
    allowed_file,
    corpus_audio_exists_locally,
    delete_submission_file,
    get_corpus_audio_response,
    get_submission_download_response,
    is_remote_url,
    print_upload_debug,
    save_submission_file,
    STORAGE_BACKEND,
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or "dev-only-temporary-secret-key"

FTS_TABLE = "corpus_entries_fts"
MAX_RESULT_SIDE_CHARS = 70
MAX_RESULT_HIT_CHARS = 150
TEXT_FILE_EXTENSIONS = {".txt"}
CATEGORY_OPTIONS = [
    "日常对话",
    "影视对白",
    "文本对话",
    "网络回帖",
    "访谈语料",
    "课堂互动",
    "多模态语料",
]
MODALITY_OPTIONS = ["text", "txt", "audio", "video", "mixed", "other"]
MODALITY_LABELS = {
    "text": "文本",
    "txt": "TXT 文件",
    "audio": "录音 / 音频",
    "video": "视频",
    "mixed": "混合材料",
    "other": "其他",
}
app.config["SEARCH_BACKEND"] = os.getenv("CORPUS_SEARCH_BACKEND", "fts").strip().lower() or "fts"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(error):
    return render_template(
        "submit.html",
        categories=CATEGORY_OPTIONS,
        modalities=MODALITY_OPTIONS,
        modality_labels=MODALITY_LABELS,
        error="上传文件过大，请将单个文件控制在 5 MB 以内。",
    ), 413


def get_admin_next_url():
    next_url = request.args.get("next") or url_for("admin_submissions")
    if not next_url.startswith("/admin") or next_url.startswith("/admin/login"):
        return url_for("admin_submissions")
    return next_url


@app.before_request
def require_admin_login():
    if not request.path.startswith("/admin"):
        return None
    if request.endpoint in {"admin_login", "admin_logout"}:
        return None
    if session.get("admin_logged_in"):
        return None
    next_url = request.full_path if request.query_string else request.path
    return redirect(url_for("admin_login", next=next_url))


def init_submission_tables():
    conn = get_db_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS corpus_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submitter_name TEXT,
                submitter_email TEXT,
                title TEXT NOT NULL,
                source TEXT,
                category TEXT NOT NULL,
                genre TEXT,
                language TEXT,
                modality TEXT NOT NULL,
                text_content TEXT,
                original_filename TEXT,
                stored_filename TEXT,
                file_path TEXT,
                file_mime_type TEXT,
                file_size INTEGER,
                status TEXT DEFAULT 'pending',
                admin_note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                reviewed_by TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS multimodal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER UNIQUE,
                title TEXT NOT NULL,
                source TEXT,
                category TEXT,
                genre TEXT,
                language TEXT,
                modality TEXT NOT NULL,
                text_content TEXT,
                original_filename TEXT,
                stored_filename TEXT,
                file_path TEXT,
                file_mime_type TEXT,
                file_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_status ON corpus_submissions (status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_created_at ON corpus_submissions (created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_multimodal_submission_id ON multimodal_entries (submission_id)")
        conn.commit()
    finally:
        conn.close()


def clean_form_value(name):
    return request.form.get(name, "").strip()


def read_text_file(path):
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def build_corpus_audio_url(audio_file):
    audio_file = (audio_file or "").strip()
    if not audio_file:
        return ""
    if is_remote_url(audio_file):
        return audio_file
    if STORAGE_BACKEND == "local" and not corpus_audio_exists_locally(audio_file):
        return ""
    return url_for("corpus_audio", filename=audio_file)


def load_all_data():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM corpus_entries ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_filter_options():
    conn = get_db_connection()
    sources = [
        row["source"]
        for row in conn.execute("""
            SELECT DISTINCT source
            FROM corpus_entries
            WHERE source IS NOT NULL AND TRIM(source) != ''
            ORDER BY source
        """).fetchall()
    ]
    years = [
        row["year"]
        for row in conn.execute("""
            SELECT DISTINCT year
            FROM corpus_entries
            WHERE year IS NOT NULL
            ORDER BY year DESC
        """).fetchall()
    ]
    conn.close()
    return sources, years


def escape_like(value):
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_search_backend():
    backend = app.config.get("SEARCH_BACKEND", "like")
    return backend if backend in {"like", "fts"} else "like"


def has_fts_table():
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (FTS_TABLE,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_active_search_backend():
    backend = get_search_backend()
    if backend == "fts" and has_fts_table():
        return "fts"
    return "like"


def build_filter_clauses(source="", year="", category="", table_name=""):
    where_clauses = []
    params = []
    prefix = f"{table_name}." if table_name else ""

    if source:
        where_clauses.append(f"{prefix}source = ?")
        params.append(source)

    if year:
        try:
            where_clauses.append(f"{prefix}year = ?")
            params.append(int(year))
        except ValueError:
            pass

    if category:
        where_clauses.append(f"{prefix}category = ?")
        params.append(category)

    return where_clauses, params


def build_search_where(keyword="", source="", year="", category=""):
    where_clauses = []
    params = []

    if keyword:
        where_clauses.append("content LIKE ? ESCAPE '\\'")
        params.append(f"%{escape_like(keyword)}%")

    filter_clauses, filter_params = build_filter_clauses(source, year, category)
    where_clauses.extend(filter_clauses)
    params.extend(filter_params)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    return where_sql, params


def escape_fts_keyword(value):
    return (value or "").replace('"', '""').strip()


def build_fts_match_query(keyword):
    safe_keyword = escape_fts_keyword(keyword)
    if not safe_keyword:
        return ""
    return f'"{safe_keyword}"'


def should_use_fts_match(keyword):
    compact = re.sub(r"\s+", "", keyword or "")
    return len(compact) >= 3


def count_search_results(keyword="", source="", year="", category=""):
    where_sql, params = build_search_where(keyword, source, year, category)
    conn = get_db_connection()
    row = conn.execute(
        f"SELECT COUNT(*) AS total FROM corpus_entries {where_sql}",
        params,
    ).fetchone()
    conn.close()
    return row["total"]


def count_search_results_fts(keyword="", source="", year="", category=""):
    if not should_use_fts_match(keyword):
        return count_search_results(keyword, source, year, category)

    match_query = build_fts_match_query(keyword)
    if not match_query:
        return count_search_results(keyword, source, year, category)

    filter_clauses, filter_params = build_filter_clauses(source, year, category, "corpus_entries")
    where_clauses = [f"{FTS_TABLE} MATCH ?"]
    where_clauses.extend(filter_clauses)
    params = [match_query, *filter_params]
    where_sql = f"WHERE {' AND '.join(where_clauses)}"

    conn = get_db_connection()
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM {FTS_TABLE}
        JOIN corpus_entries ON {FTS_TABLE}.rowid = corpus_entries.id
        {where_sql}
        """,
        params,
    ).fetchone()
    conn.close()
    return row["total"]


def query_search_page(keyword="", source="", year="", category="", limit=50, offset=0):
    where_sql, params = build_search_where(keyword, source, year, category)
    conn = get_db_connection()
    rows = conn.execute(
        f"""
        SELECT *
        FROM corpus_entries
        {where_sql}
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def query_search_page_fts(keyword="", source="", year="", category="", limit=50, offset=0):
    if not should_use_fts_match(keyword):
        return query_search_page(keyword, source, year, category, limit=limit, offset=offset)

    match_query = build_fts_match_query(keyword)
    if not match_query:
        return query_search_page(keyword, source, year, category, limit=limit, offset=offset)

    filter_clauses, filter_params = build_filter_clauses(source, year, category, "corpus_entries")
    where_clauses = [f"{FTS_TABLE} MATCH ?"]
    where_clauses.extend(filter_clauses)
    params = [match_query, *filter_params, limit, offset]
    where_sql = f"WHERE {' AND '.join(where_clauses)}"

    conn = get_db_connection()
    rows = conn.execute(
        f"""
        SELECT corpus_entries.*
        FROM {FTS_TABLE}
        JOIN corpus_entries ON {FTS_TABLE}.rowid = corpus_entries.id
        {where_sql}
        ORDER BY corpus_entries.id DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def has_extended_schema(conn):
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(corpus_entries)").fetchall()}
    return {"dataset_name", "created_at", "import_batch", "content_hash"}.issubset(columns)


def insert_entry(title, content, source, year, category):
    conn = get_db_connection()
    if has_extended_schema(conn):
        conn.execute("""
            INSERT INTO corpus_entries (
                title, content, source, year, category,
                dataset_name, created_at, import_batch, content_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title,
            content,
            source,
            year,
            category,
            category or source,
            utc_timestamp(),
            "admin_manual",
            compute_content_hash(content),
        ))
    else:
        conn.execute("""
            INSERT INTO corpus_entries (title, content, source, year, category)
            VALUES (?, ?, ?, ?, ?)
        """, (title, content, source, year, category))
    conn.commit()
    conn.close()


def insert_approved_text_submission(conn, submission):
    content = (submission["text_content"] or "").strip()
    if not content:
        raise ValueError("文本类投稿必须包含文本内容。")

    if has_extended_schema(conn):
        conn.execute("""
            INSERT INTO corpus_entries (
                title, content, source, year, category,
                dataset_name, created_at, import_batch, content_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            submission["title"],
            content,
            submission["source"] or submission["category"],
            None,
            submission["category"],
            submission["category"] or submission["source"],
            utc_timestamp(),
            "public_submission",
            compute_content_hash(content),
        ))
    else:
        conn.execute("""
            INSERT INTO corpus_entries (title, content, source, year, category)
            VALUES (?, ?, ?, ?, ?)
        """, (
            submission["title"],
            content,
            submission["source"] or submission["category"],
            None,
            submission["category"],
        ))


def insert_approved_multimodal_submission(conn, submission):
    conn.execute("""
        INSERT OR IGNORE INTO multimodal_entries (
            submission_id, title, source, category, genre, language, modality,
            text_content, original_filename, stored_filename, file_path,
            file_mime_type, file_size
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        submission["id"],
        submission["title"],
        submission["source"],
        submission["category"],
        submission["genre"],
        submission["language"],
        submission["modality"],
        submission["text_content"],
        submission["original_filename"],
        submission["stored_filename"],
        submission["file_path"],
        submission["file_mime_type"],
        submission["file_size"],
    ))


def split_context(text, keyword, left_len=30, right_len=30):
    idx = text.find(keyword)
    if idx == -1:
        return text[:left_len], "", text[left_len:left_len + right_len]

    left = text[max(0, idx - left_len):idx]
    hit = text[idx:idx + len(keyword)]
    right = text[idx + len(keyword): idx + len(keyword) + right_len]
    return left, hit, right


def get_optional(item, field_name):
    return item[field_name] if field_name in item.keys() else None


def split_dialogue_units(text):
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) > 1:
        return lines

    parts = re.split(r"(?<=[。！？!?；;])", text)
    parts = [part.strip() for part in parts if part.strip()]
    return parts or [text]


def trim_text(text, max_len, keep_tail=False):
    text = (text or "").strip()
    if max_len <= 0 or len(text) <= max_len:
        return text
    if keep_tail:
        return "…" + text[-max_len:]
    return text[:max_len] + "…"


def trim_units(units, max_len, keep_tail=False):
    selected = []
    total = 0
    iterable = reversed(units) if keep_tail else units
    for unit in iterable:
        unit_len = len(unit)
        if selected and total + unit_len > max_len:
            break
        selected.append(unit)
        total += unit_len

    if keep_tail:
        selected = list(reversed(selected))

    text = "\n".join(selected)
    return trim_text(text, max_len, keep_tail=keep_tail)


def highlight_keyword(text, keyword):
    text = text or ""
    if not keyword:
        return escape(text)
    parts = text.split(keyword)
    if len(parts) == 1:
        return escape(text)

    highlighted = []
    for index, part in enumerate(parts):
        highlighted.append(str(escape(part)))
        if index < len(parts) - 1:
            highlighted.append(f'<span class="segment-hit-word">{ escape(keyword) }</span>')
    return Markup("".join(highlighted))


def build_segment_context(item, keyword, left_len=80, right_len=80):
    left_len = min(left_len, MAX_RESULT_SIDE_CHARS)
    right_len = min(right_len, MAX_RESULT_SIDE_CHARS)
    prev_segment = get_optional(item, "prev_segment")
    current_segment = get_optional(item, "current_segment") or get_optional(item, "segment_text")
    next_segment = get_optional(item, "next_segment")

    if prev_segment or current_segment or next_segment:
        hit_segment = current_segment or ""
        return {
            "file_name": item["title"],
            "dialogue_id": get_optional(item, "conversation_id") or get_optional(item, "dialogue_id") or item["id"],
            "prev_segment": prev_segment or "",
            "hit_segment": hit_segment,
            "hit_segment_html": highlight_keyword(hit_segment, keyword),
            "next_segment": next_segment or "",
        }

    content = item["content"] or ""
    units = split_dialogue_units(content)
    if not units:
        return {
            "file_name": item["title"],
            "dialogue_id": item["id"],
            "prev_segment": "",
            "hit_segment": "",
            "hit_segment_html": "",
            "next_segment": "",
        }

    hit_index = 0
    if keyword:
        for index, unit in enumerate(units):
            if keyword in unit:
                hit_index = index
                break
        else:
            whole = content
            left, hit, right = split_context(whole, keyword, left_len, right_len)
            hit_text = hit or trim_text(whole, max(left_len + right_len, 80))
            return {
                "file_name": item["title"],
                "dialogue_id": item["id"],
                "prev_segment": left,
                "hit_segment": hit_text,
                "hit_segment_html": highlight_keyword(hit_text, keyword),
                "next_segment": right,
            }

    hit_segment = trim_text(hit_segment := units[hit_index], max(left_len + right_len, 80))
    hit_segment = trim_text(hit_segment, MAX_RESULT_HIT_CHARS)
    prev_segment_text = trim_units(units[max(0, hit_index - 3):hit_index], left_len, keep_tail=True)
    next_segment_text = trim_units(units[hit_index + 1:hit_index + 4], right_len, keep_tail=False)

    return {
        "file_name": item["title"],
        "dialogue_id": item["id"],
        "prev_segment": prev_segment_text,
        "hit_segment": hit_segment,
        "hit_segment_html": highlight_keyword(hit_segment, keyword),
        "next_segment": next_segment_text,
    }


init_submission_tables = corpus_repository.init_submission_tables
load_all_data = corpus_repository.load_all_data
get_filter_options = corpus_repository.get_filter_options
has_fts_table = corpus_repository.has_fts_table
get_active_search_backend = lambda: corpus_repository.get_active_search_backend(get_search_backend())
count_search_results = corpus_repository.count_search_results
count_search_results_fts = corpus_repository.count_search_results_fts
query_search_page = corpus_repository.query_search_page
query_search_page_fts = corpus_repository.query_search_page_fts
insert_entry = corpus_repository.insert_entry
insert_approved_text_submission = corpus_repository.insert_approved_text_submission
insert_approved_multimodal_submission = corpus_repository.insert_approved_multimodal_submission


@app.route("/")
def home():
    sources, years = get_filter_options()
    return render_template("home.html", sources=sources, years=years)


@app.route("/submit", methods=["GET", "POST"])
def submit():
    if request.method == "GET":
        return render_template(
            "submit.html",
            categories=CATEGORY_OPTIONS,
            modalities=MODALITY_OPTIONS,
            modality_labels=MODALITY_LABELS,
        )

    submitter_name = clean_form_value("submitter_name")
    submitter_email = clean_form_value("submitter_email")
    title = clean_form_value("title")
    source = clean_form_value("source")
    category = clean_form_value("category")
    genre = clean_form_value("genre")
    language = clean_form_value("language") or "zh-CN"
    modality = clean_form_value("modality")
    text_content = clean_form_value("text_content")
    consent = request.form.get("consent")
    upload = request.files.get("file")

    def render_error(message):
        return render_template(
            "submit.html",
            categories=CATEGORY_OPTIONS,
            modalities=MODALITY_OPTIONS,
            modality_labels=MODALITY_LABELS,
            error=message,
            form=request.form,
        ), 400

    if not title:
        return render_error("请填写材料标题。")
    if not category:
        return render_error("请选择语料类别。")
    if modality not in MODALITY_OPTIONS:
        return render_error("请选择有效的语料模态。")
    if not consent:
        return render_error("请确认授权说明后再提交。")
    if not text_content and not (upload and upload.filename):
        return render_error("请填写文本内容，或上传一个文件。")

    file_info = None
    try:
        file_info = save_submission_file(upload)
        if file_info and file_info["extension"] in TEXT_FILE_EXTENSIONS and not text_content and file_info.get("path"):
            text_content = read_text_file(file_info["path"]).strip()
        elif file_info and file_info["extension"] in TEXT_FILE_EXTENSIONS and not text_content:
            text_content = (file_info.get("text_content") or "").strip()
    except ValueError as exc:
        print_upload_debug(
            upload,
            selected_modality=modality,
            has_text_content=bool(text_content),
            has_file=bool(upload and upload.filename),
        )
        return render_error(str(exc))
    except OSError:
        return render_error("上传文件保存失败，请稍后重试。")

    corpus_repository.create_submission(
        {
            "submitter_name": submitter_name,
            "submitter_email": submitter_email,
            "title": title,
            "source": source,
            "category": category,
            "genre": genre,
            "language": language,
            "modality": modality,
            "text_content": text_content,
        },
        file_info,
    )

    return render_template(
        "submit.html",
        categories=CATEGORY_OPTIONS,
        modalities=MODALITY_OPTIONS,
        modality_labels=MODALITY_LABELS,
        success=True,
    )


@app.route("/search")
def search():
    keyword = request.args.get("q", "").strip()
    source = request.args.get("source", "").strip()
    year = request.args.get("year", "").strip()
    category = request.args.get("category", "").strip()
    left_len = request.args.get("left", "30").strip()
    right_len = request.args.get("right", "30").strip()
    page = request.args.get("page", "1").strip()

    try:
        left_len = int(left_len)
    except ValueError:
        left_len = 30

    try:
        right_len = int(right_len)
    except ValueError:
        right_len = 30

    try:
        page = int(page)
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    per_page = 50
    search_backend = get_active_search_backend()
    fast_search = (
        search_backend == "postgres"
        and corpus_repository.POSTGRES_FAST_SEARCH
    )
    if fast_search:
        total = 0
    elif search_backend == "fts":
        total = count_search_results_fts(keyword, source, year, category)
    else:
        total = count_search_results(keyword, source, year, category)
    total_pages = 1 if fast_search else max(1, math.ceil(total / per_page))

    if not fast_search and page > total_pages:
        page = total_pages

    page_window_size = 10
    half_window = page_window_size // 2
    page_window_start = max(1, page - half_window)
    page_window_end = page_window_start + page_window_size - 1

    if page_window_end > total_pages:
        page_window_end = total_pages
        page_window_start = max(1, page_window_end - page_window_size + 1)

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    query_limit = per_page + 1 if fast_search else per_page
    if search_backend == "fts":
        page_rows = query_search_page_fts(
            keyword=keyword,
            source=source,
            year=year,
            category=category,
            limit=query_limit,
            offset=start_idx,
        )
    else:
        page_rows = query_search_page(
            keyword=keyword,
            source=source,
            year=year,
            category=category,
            limit=query_limit,
            offset=start_idx,
        )
    has_next_page = fast_search and len(page_rows) > per_page
    if fast_search:
        page_rows = page_rows[:per_page]
        total = start_idx + len(page_rows) + (1 if has_next_page else 0)
        total_pages = page + 1 if has_next_page else page
    page_results = []
    for item in page_rows:
        if keyword:
            left, hit, right = split_context(item["content"], keyword, left_len, right_len)
        else:
            left, hit, right = "", "", item["content"][:right_len]

        result = dict(item)
        result["left_context"] = left
        result["hit"] = hit
        result["right_context"] = right
        result.update(build_segment_context(item, keyword, left_len, right_len))
        audio_file = result.get("audio_file")
        result["audio_url"] = build_corpus_audio_url(audio_file)
        page_results.append(result)

    start_no = start_idx + 1 if total > 0 else 0
    end_no = min(end_idx, total)

    sources, years = get_filter_options()

    return render_template(
        "results.html",
        keyword=keyword,
        source=source,
        year=year,
        category=category,
        left_len=left_len,
        right_len=right_len,
        results=page_results,
        total=total,
        sources=sources,
        years=years,
        page=page,
        total_pages=total_pages,
        page_window_start=page_window_start,
        page_window_end=page_window_end,
        start_no=start_no,
        end_no=end_no,
        search_backend=search_backend,
    )


@app.route("/corpus/audio/<path:filename>")
def corpus_audio(filename):
    try:
        return get_corpus_audio_response(filename)
    except FileNotFoundError:
        return "Audio file is not available.", 404


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = ""
    if request.method == "POST":
        expected_username = os.getenv("ADMIN_USERNAME", "")
        expected_password = os.getenv("ADMIN_PASSWORD", "")
        username = clean_form_value("username")
        password = request.form.get("password", "")

        if not expected_username or not expected_password:
            error = "请先在环境变量中设置管理员账号和密码。"
        elif compare_digest(username, expected_username) and compare_digest(password, expected_password):
            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = username
            return redirect(get_admin_next_url())
        else:
            error = "账号或密码不正确，请重新输入。"

    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/admin/upload-demo", methods=["POST"])
def upload_demo():
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    source_type = request.form.get("source_type", "").strip()
    year = request.form.get("year", "").strip()
    category = request.form.get("category", "").strip()

    if not title or not content or not source_type:
        return render_template(
            "admin.html",
            error="请至少填写标题、内容和语料类型。"
        )

    try:
        year_value = int(year) if year else None
    except ValueError:
        year_value = None

    insert_entry(title, content, source_type, year_value, category)

    return render_template(
        "admin.html",
        success=True,
        success_message="语料已成功写入数据库。"
    )


@app.route("/admin/list")
def admin_list():
    data = load_all_data()
    return render_template("admin_list.html", entries=data)


@app.route("/admin/submissions")
def admin_submissions():
    status = request.args.get("status", "pending").strip().lower()
    if status not in {"pending", "approved", "rejected", "all"}:
        status = "pending"

    rows = corpus_repository.list_submissions(status)

    return render_template("admin_submissions.html", submissions=rows, status=status)


@app.route("/admin/submissions/<int:submission_id>")
def admin_submission_detail(submission_id):
    submission = corpus_repository.get_submission_by_id(submission_id)

    if submission is None:
        return render_template("admin_submission_detail.html", error="未找到该投稿。"), 404

    return render_template("admin_submission_detail.html", submission=submission)


@app.route("/admin/submissions/<int:submission_id>/approve", methods=["POST"])
def approve_submission(submission_id):
    admin_note = clean_form_value("admin_note")
    try:
        submission, result = corpus_repository.approve_submission_record(submission_id, admin_note)
        if result == "missing":
            return redirect(url_for("admin_submissions"))
        if result == "already_approved":
            return redirect(url_for("admin_submission_detail", submission_id=submission_id, already_approved=1))
    except Exception:
        return render_template(
            "admin_submission_detail.html",
            submission=corpus_repository.get_submission_by_id(submission_id),
            error="该投稿暂时无法通过审核，请确认其中包含可用的文本内容或文件信息。",
        ), 400

    return redirect(url_for("admin_submission_detail", submission_id=submission_id, approved=1))


@app.route("/admin/submissions/<int:submission_id>/reject", methods=["POST"])
def reject_submission(submission_id):
    admin_note = clean_form_value("admin_note")
    corpus_repository.reject_submission_record(submission_id, admin_note)
    return redirect(url_for("admin_submission_detail", submission_id=submission_id, rejected=1))


@app.route("/admin/submissions/<int:submission_id>/delete", methods=["POST"])
def delete_submission(submission_id):
    submission = corpus_repository.delete_submission_record(submission_id)
    if submission and submission["status"] != "approved":
        delete_submission_file(
            submission["stored_filename"],
            object_key=submission.get("object_key"),
            storage_backend=submission.get("storage_backend"),
        )
    return redirect(url_for("admin_submissions"))


@app.route("/admin/submissions/<int:submission_id>/download")
def download_submission_file(submission_id):
    submission = corpus_repository.get_submission_by_id(submission_id)

    if submission is None or not submission["stored_filename"]:
        return redirect(url_for("admin_submission_detail", submission_id=submission_id))

    try:
        return get_submission_download_response(
            submission["stored_filename"],
            submission["original_filename"] or submission["stored_filename"],
            object_key=submission.get("object_key"),
            file_url=submission.get("file_url"),
            storage_backend=submission.get("storage_backend"),
        )
    except FileNotFoundError:
        return render_template(
            "admin_submission_detail.html",
            submission=submission,
            error="未找到上传文件。",
        ), 404

init_submission_tables()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
