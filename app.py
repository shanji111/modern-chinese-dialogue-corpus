from flask import Flask, jsonify, render_template, request, redirect, session, url_for
import csv
from hmac import compare_digest
import io
import json
import os
import math
import re
from pathlib import Path

from markupsafe import Markup, escape
from werkzeug.exceptions import RequestEntityTooLarge

import corpus_repository
from database import DATABASE_BACKEND, DATABASE_PATH, DATABASE_URL, get_db_connection, print_database_identity
from db_utils import compute_content_hash, utc_timestamp
from services.audio_service import build_corpus_audio_url, get_corpus_audio_response
from services.submission_storage_service import (
    build_submission_download_response,
    delete_submission_upload,
    print_upload_debug,
    save_submission_upload,
)
from services.transcription_service import (
    is_transcribable_submission,
    transcribe_submission_media,
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or "dev-only-temporary-secret-key"

FTS_TABLE = "corpus_entries_fts"
MAX_RESULT_SIDE_CHARS = 70
MAX_RESULT_HIT_CHARS = 150
INTERVIEW_SOURCE = "访谈语料"
INTERVIEW_RESULT_SIDE_CHARS = 34
INTERVIEW_RESULT_HIT_CHARS = 96
INTERVIEW_MODAL_SIDE_CHARS = 90
TRANSCRIPTION_TEMP_DIR = Path(app.root_path) / ".transcription_tmp"
TEXT_FILE_EXTENSIONS = {".txt"}
DIAGRAPH_NOTICE = "本图谱由程序根据词汇重现、人称映射、否定标记、疑问词和句式框架自动生成，仅供初步分析参考，复杂共指、省略和语义关系建议人工校订。"
DIAGRAPH_WINDOW_OPTIONS = {
    "pair": "当前 A/B 两轮",
    "context2": "前后 2 轮",
    "context5": "前后 5 轮",
    "full": "当前完整片段",
}
DIAGRAPH_PERSON_GROUPS = {
    "我": "dialogue_person_singular",
    "你": "dialogue_person_singular",
    "我们": "dialogue_person_plural",
    "你们": "dialogue_person_plural",
    "他": "third_person_singular",
    "她": "third_person_singular",
    "它": "third_person_singular",
    "他们": "third_person_plural",
    "她们": "third_person_plural",
    "它们": "third_person_plural",
}
DIAGRAPH_NEGATION_MARKERS = ("用不着", "没有", "不是", "不能", "不要", "别", "没", "不")
DIAGRAPH_QUESTION_MARKERS = ("为什么", "怎么", "多少", "什么", "谁", "哪儿", "哪里", "吗", "呢", "吧", "？", "?")
DIAGRAPH_REPAIR_MARKERS = ("也就是说", "我是说", "其实", "不过", "但是", "可是", "反而", "不是…而是")
DIAGRAPH_FRAME_PHRASES = ("我觉得", "能不能", "可不可以", "为什么", "因为", "不是", "而是", "也就是说", "我是说")
DIAGRAPH_LITERAL_CHUNKS = ("其他", "其它")
DIAGRAPH_SPLIT_NEGATION_BASES = {
    "不知道": ("不", "知道"),
    "不觉得": ("不", "觉得"),
    "不明白": ("不", "明白"),
    "不理解": ("不", "理解"),
    "不要": ("不要",),
    "不是": ("不是",),
    "没有": ("没有",),
    "不能": ("不能",),
    "用不着": ("用不着",),
}
DIAGRAPH_PUNCTUATION = set("，。！？、；：,.!?;:…")
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
    "txt": "TXT 文档",
    "audio": "音频 / 录音",
    "video": "视频",
    "mixed": "多模态",
    "other": "其他",
}
app.config["SEARCH_BACKEND"] = os.getenv("CORPUS_SEARCH_BACKEND", "fts").strip().lower() or "fts"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


def print_startup_database_diagnostics():
    def first_value(row):
        if isinstance(row, dict):
            return next(iter(row.values()))
        try:
            return row[0]
        except KeyError:
            return next(iter(dict(row).values()))

    print("[startup-db] cwd:", os.getcwd())
    print("[startup-db] DATABASE_BACKEND:", DATABASE_BACKEND)
    print("[startup-db] DATABASE_PATH env:", os.getenv("DATABASE_PATH") or "")
    print("[startup-db] DATABASE_URL env set:", bool(DATABASE_URL))
    print("[startup-db] resolved database path:", DATABASE_PATH.resolve())
    print("[startup-db] database exists:", DATABASE_PATH.exists())
    if DATABASE_BACKEND != "sqlite":
        print("[startup-db] resolved database path is not used because DATABASE_BACKEND is not sqlite")
    elif not DATABASE_PATH.exists():
        return

    try:
        conn = get_db_connection()
        try:
            marker = "%s" if DATABASE_BACKEND == "postgres" else "?"
            interview_total = first_value(conn.execute(
                f"SELECT COUNT(*) FROM corpus_entries WHERE source = {marker}",
                (INTERVIEW_SOURCE,),
            ).fetchone())
            civil_aviation_hits = first_value(conn.execute(
                f"""
                SELECT COUNT(*)
                FROM corpus_entries
                WHERE source = {marker}
                  AND content LIKE {marker}
                """,
                (INTERVIEW_SOURCE, "%民航%"),
            ).fetchone())
            print("[startup-db] source=访谈语料 total:", interview_total)
            print("[startup-db] source=访谈语料 AND content LIKE %民航%:", civil_aviation_hits)
        finally:
            conn.close()
    except Exception as exc:
        print("[startup-db] diagnostic query failed:", repr(exc))


print_database_identity("[startup-db]")
if os.getenv("ENABLE_STARTUP_DB_DIAGNOSTICS", "").strip().lower() in {"1", "true", "yes", "on"}:
    print_startup_database_diagnostics()


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
        conn.execute(""""
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
        conn.execute(""""
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


def load_all_data():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM corpus_entries ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_filter_options():
    conn = get_db_connection()
    sources = [
        row["source"]
        for row in conn.execute(""""
            SELECT DISTINCT source
            FROM corpus_entries
            WHERE source IS NOT NULL AND TRIM(source) != ''
            ORDER BY source
        """).fetchall()
    ]
    years = [
        row["year"]
        for row in conn.execute(""""
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
        conn.execute(""""
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
        conn.execute(""""
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
        conn.execute(""""
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
        conn.execute(""""
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
    conn.execute(""""
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

    parts = re.split(r"(?<=[銆傦紒锛??锛?])", text)
    parts = [part.strip() for part in parts if part.strip()]
    return parts or [text]


def trim_text(text, max_len, keep_tail=False):
    text = (text or "").strip()
    if max_len <= 0 or len(text) <= max_len:
        return text
    if keep_tail:
        return "..." + text[-max_len:]
    return text[:max_len] + "..."


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


def highlight_terms(text, terms):
    text = text or ""
    terms = [term for term in (terms or []) if term]
    if not terms:
        return escape(text)
    pattern = re.compile("|".join(re.escape(term) for term in sorted(terms, key=len, reverse=True)))
    highlighted = []
    last_index = 0
    for match in pattern.finditer(text):
        highlighted.append(str(escape(text[last_index:match.start()])))
        highlighted.append(f'<span class="segment-hit-word">{ escape(match.group(0)) }</span>')
        last_index = match.end()
    highlighted.append(str(escape(text[last_index:])))
    return Markup("".join(highlighted))


def highlight_resonance_text(text, marker_terms=None, keyword=""):
    text = text or ""
    marker_terms = [term for term in (marker_terms or []) if term]
    keyword = (keyword or "").strip()
    if not text:
        return Markup("")

    query_hits = [False] * len(text)
    marker_hits = [False] * len(text)

    def mark_occurrences(term, target):
        if not term:
            return
        start = 0
        while True:
            index = text.find(term, start)
            if index == -1:
                break
            for pos in range(index, min(index + len(term), len(text))):
                target[pos] = True
            start = index + max(1, len(term))

    if keyword:
        mark_occurrences(keyword, query_hits)
    for term in marker_terms:
        mark_occurrences(term, marker_hits)

    html = []
    index = 0
    while index < len(text):
        is_query = query_hits[index]
        is_marker = marker_hits[index]
        end = index + 1
        while end < len(text) and query_hits[end] == is_query and marker_hits[end] == is_marker:
            end += 1
        segment = str(escape(text[index:end]))
        classes = []
        if is_marker:
            classes.append("resonance-marker")
        if is_query:
            classes.append("query-highlight")
        if classes:
            html.append(f'<span class="{" ".join(classes)}">{segment}</span>')
        else:
            html.append(segment)
        index = end
    return Markup("".join(html))


def normalize_diagraph_window(window_mode):
    window_mode = (window_mode or "pair").strip().lower()
    return window_mode if window_mode in DIAGRAPH_WINDOW_OPTIONS else "pair"


def build_diagraph_column_label(index):
    label = ""
    value = index
    while True:
        value, remainder = divmod(value, 26)
        label = chr(65 + remainder) + label
        if value == 0:
            return label
        value -= 1


def escape_html(text):
    return str(escape(text or ""))


def load_diagraph_terms(pair):
    groups = []
    for field_name in ("shared_terms", "markers"):
        raw = pair.get(field_name) or "[]"
        try:
            values = json.loads(raw)
        except (TypeError, ValueError):
            values = []
        groups.append(values)
    return corpus_repository.merge_common_terms(*groups, max_terms=24)


def collect_diagraph_anchors(turns, pair_terms):
    phrases = [list(pair_terms)]
    texts = [turn.get("turn_text") or "" for turn in turns]
    for index_a, text_a in enumerate(texts):
        for index_b in range(index_a + 1, len(texts)):
            phrases.append(corpus_repository.longest_common_phrases(text_a, texts[index_b], max_phrases=3))
    phrases.append(DIAGRAPH_FRAME_PHRASES)
    return corpus_repository.merge_common_terms(*phrases, max_terms=24)


def classify_diagraph_token(token_text):
    if token_text in DIAGRAPH_PERSON_GROUPS:
        return {"text": token_text, "kind": "pronoun", "group": DIAGRAPH_PERSON_GROUPS[token_text]}
    if token_text in DIAGRAPH_NEGATION_MARKERS:
        return {"text": token_text, "kind": "negation", "group": "negation"}
    if token_text in DIAGRAPH_QUESTION_MARKERS:
        return {"text": token_text, "kind": "question", "group": "question"}
    if token_text in DIAGRAPH_REPAIR_MARKERS:
        return {"text": token_text, "kind": "repair", "group": "repair"}
    if token_text in DIAGRAPH_FRAME_PHRASES:
        return {"text": token_text, "kind": "frame", "group": token_text}
    if token_text in DIAGRAPH_PUNCTUATION:
        return {"text": token_text, "kind": "punctuation", "group": token_text}
    return {"text": token_text, "kind": "lexical", "group": token_text}


def maybe_split_negation_token(token_text):
    mapped = DIAGRAPH_SPLIT_NEGATION_BASES.get(token_text)
    if mapped:
        return [classify_diagraph_token(value) for value in mapped]
    if token_text.startswith("不") and len(token_text) >= 3 and corpus_repository.is_substantive_common_phrase(token_text[1:]):
        return [classify_diagraph_token("不"), classify_diagraph_token(token_text[1:])]
    if token_text.startswith("没") and len(token_text) >= 3 and corpus_repository.is_substantive_common_phrase(token_text[1:]):
        return [classify_diagraph_token("没"), classify_diagraph_token(token_text[1:])]
    return [classify_diagraph_token(token_text)]


def flush_diagraph_buffer(buffer, tokens):
    if not buffer:
        return
    chunk = "".join(buffer).strip()
    buffer.clear()
    if chunk:
        tokens.append(classify_diagraph_token(chunk))


def tokenize_diagraph_text(text, anchor_terms):
    text = corpus_repository.normalize_turn_text(text or "")
    lexicon = sorted(
        {
            *anchor_terms,
            *DIAGRAPH_PERSON_GROUPS.keys(),
            *DIAGRAPH_NEGATION_MARKERS,
            *DIAGRAPH_QUESTION_MARKERS,
            *DIAGRAPH_REPAIR_MARKERS,
            *DIAGRAPH_FRAME_PHRASES,
            *DIAGRAPH_LITERAL_CHUNKS,
        },
        key=len,
        reverse=True,
    )
    tokens = []
    buffer = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            flush_diagraph_buffer(buffer, tokens)
            index += 1
            continue
        matched = ""
        for phrase in lexicon:
            if phrase and text.startswith(phrase, index):
                matched = phrase
                break
        if matched:
            flush_diagraph_buffer(buffer, tokens)
            tokens.extend(maybe_split_negation_token(matched))
            index += len(matched)
            continue
        if char in DIAGRAPH_PUNCTUATION:
            flush_diagraph_buffer(buffer, tokens)
            tokens.append(classify_diagraph_token(char))
            index += 1
            continue
        if re.match(r"[A-Za-z0-9_]", char):
            flush_diagraph_buffer(buffer, tokens)
            end = index + 1
            while end < len(text) and re.match(r"[A-Za-z0-9_]", text[end]):
                end += 1
            tokens.append(classify_diagraph_token(text[index:end]))
            index = end
            continue
        buffer.append(char)
        index += 1
    flush_diagraph_buffer(buffer, tokens)
    return tokens


def diagraph_tokens_match(left_token, right_token):
    if left_token["text"] == right_token["text"]:
        return True
    if left_token["kind"] == "pronoun" and right_token["kind"] == "pronoun":
        return left_token["group"] == right_token["group"]
    if left_token["kind"] == right_token["kind"] and left_token["kind"] in {"negation", "question", "repair"}:
        return True
    return False


def compute_diagraph_lcs(left_tokens, right_tokens):
    rows = len(left_tokens)
    cols = len(right_tokens)
    table = [[0] * (cols + 1) for _ in range(rows + 1)]
    for row in range(rows - 1, -1, -1):
        for col in range(cols - 1, -1, -1):
            if diagraph_tokens_match(left_tokens[row], right_tokens[col]):
                table[row][col] = table[row + 1][col + 1] + 1
            else:
                table[row][col] = max(table[row + 1][col], table[row][col + 1])

    matches = []
    row = 0
    col = 0
    while row < rows and col < cols:
        if diagraph_tokens_match(left_tokens[row], right_tokens[col]):
            matches.append((row, col))
            row += 1
            col += 1
        elif table[row + 1][col] >= table[row][col + 1]:
            row += 1
        else:
            col += 1
    return matches


def merge_diagraph_columns(master_columns, row_tokens):
    if not master_columns:
        return [{"token": token} for token in row_tokens]
    matches = compute_diagraph_lcs([column["token"] for column in master_columns], row_tokens)
    merged = []
    master_index = 0
    row_index = 0
    match_index = 0
    while match_index < len(matches):
        target_master, target_row = matches[match_index]
        while master_index < target_master:
            merged.append(master_columns[master_index])
            master_index += 1
        while row_index < target_row:
            merged.append({"token": row_tokens[row_index]})
            row_index += 1
        merged.append(master_columns[master_index])
        master_index += 1
        row_index += 1
        match_index += 1
    merged.extend(master_columns[master_index:])
    while row_index < len(row_tokens):
        merged.append({"token": row_tokens[row_index]})
        row_index += 1
    return merged


def place_diagraph_row(master_columns, row_tokens):
    cells = []
    matches = compute_diagraph_lcs([column["token"] for column in master_columns], row_tokens)
    row_index = 0
    match_index = 0
    for column_index, column in enumerate(master_columns):
        if match_index < len(matches) and matches[match_index][0] == column_index:
            row_token_index = matches[match_index][1]
            while row_index < row_token_index:
                row_index += 1
            cells.append(row_tokens[row_index]["text"])
            row_index += 1
            match_index += 1
        else:
            cells.append("")
    return cells


def build_diagraph_grid(pair, turns):
    anchor_terms = collect_diagraph_anchors(turns, load_diagraph_terms(pair))
    token_rows = [
        tokenize_diagraph_text(turn.get("turn_text") or "", anchor_terms)
        for turn in turns
    ]
    master_columns = []
    for row_tokens in token_rows:
        master_columns = merge_diagraph_columns(master_columns, row_tokens)

    column_labels = [build_diagraph_column_label(index) for index in range(len(master_columns))]
    grid_rows = []
    for turn, row_tokens in zip(turns, token_rows):
        cell_values = place_diagraph_row(master_columns, row_tokens)
        grid_rows.append({
            "row_no": int(turn.get("turn_index") or 0),
            "speaker": turn.get("speaker_label") or "未标注",
            "text": turn.get("turn_text") or "",
            "cells": {
                column_label: cell_value
                for column_label, cell_value in zip(column_labels, cell_values)
                if cell_value
            },
        })
    return master_columns, column_labels, grid_rows


def join_column_range(labels):
    labels = [label for label in labels if label]
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    return f"{labels[0]}-{labels[-1]}"


def build_column_mapping(values):
    ordered = []
    seen = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return "：".join(ordered)


def build_diagraph_affordances(master_columns, column_labels, grid_rows):
    affordances = []
    column_values = []
    column_row_counts = []
    column_row_positions = []
    for index, column in enumerate(master_columns):
        values = []
        row_positions = []
        for row_position, row in enumerate(grid_rows):
            value = row["cells"].get(column_labels[index], "")
            if value:
                values.append(value)
                row_positions.append(row_position)
        column_values.append(values)
        column_row_counts.append(len(values))
        column_row_positions.append(row_positions)
        token = column["token"]
        if not values:
            continue
        row_count = column_row_counts[index]
        unique_values = {value for value in values if value}
        relation = ""
        description = ""
        include = False
        if token["kind"] == "pronoun":
            if row_count >= 2:
                include = True
                if token["group"].startswith("third_person"):
                    relation = "共指候选"
                    description = "第三人称成分在不同话轮中持续出现，可作为共指候选。"
                else:
                    relation = "人称映射"
                    description = "对话角色在相邻话轮之间发生我/你类转换。"
        elif token["kind"] == "question":
            include = True
            relation = "疑问词"
            description = "该纵栏集中呈现疑问词或疑问语气标记。"
        elif token["kind"] == "negation":
            include = True
            relation = "否定"
            description = "该纵栏呈现否定性标记，可与相邻谓词形成否定回应。"
        elif token["kind"] == "repair":
            include = True
            relation = "转折/修正"
            description = "该纵栏呈现转折或修正标记。"
        elif token["kind"] == "frame":
            if row_count >= 2:
                include = True
                relation = "句式复现"
                description = "该纵栏体现固定句式框架的重复或呼应。"
        else:
            if row_count >= 2 or len(unique_values) >= 2:
                include = True
                relation = "词汇重现"
                description = "相同或高度接近的词汇在多个话轮中重复出现。"
        if not include:
            continue
        affordances.append({
            "column": column_labels[index],
            "mapping": build_column_mapping(values),
            "relation": relation,
            "description": description,
        })

    for index, column in enumerate(master_columns[:-1]):
        token = column["token"]
        if token["kind"] != "negation":
            continue
        candidate_rows = [row_position for row_position in column_row_positions[index] if row_position > 0]
        if not candidate_rows:
            continue
        lexical_values = []
        combined_values = []
        for row_position in candidate_rows:
            token_value = grid_rows[row_position]["cells"].get(column_labels[index], "")
            lexical_value = grid_rows[row_position]["cells"].get(column_labels[index + 1], "")
            if lexical_value:
                lexical_values.append(lexical_value)
            if token_value and lexical_value:
                combined_values.append(f"{token_value}{lexical_value}")
        if not combined_values and not lexical_values:
            continue
        mapping = build_column_mapping(combined_values or lexical_values)
        affordances.append({
            "column": join_column_range([column_labels[index], column_labels[index + 1]]),
            "mapping": mapping,
            "relation": "否定回应",
            "description": "后一话轮使用否定标记并与相邻词项组合，形成否定性回应或修正。",
        })

    question_labels = []
    for index, column in enumerate(master_columns):
        if column["token"]["kind"] != "question":
            continue
        if any(row_position < len(grid_rows) - 1 for row_position in column_row_positions[index]):
            question_labels.append(column_labels[index])

    if question_labels and len(grid_rows) >= 2:
        affordances.append({
            "column": join_column_range(question_labels),
            "mapping": build_column_mapping([
                row["cells"].get(label, "")
                for row in grid_rows
                for label in question_labels
                if row["cells"].get(label, "")
            ]),
            "relation": "疑问回应",
            "description": "前一话轮含疑问词或疑问标记，后一话轮构成相邻回应。",
        })

    return affordances


def build_diagraph_payload(pair, turns, window_mode):
    master_columns, column_labels, grid_rows = build_diagraph_grid(pair, turns)
    affordances = build_diagraph_affordances(master_columns, column_labels, grid_rows)
    return {
        "pair_id": pair["id"],
        "window_mode": window_mode,
        "window_label": DIAGRAPH_WINDOW_OPTIONS[window_mode],
        "notice": DIAGRAPH_NOTICE,
        "turns": [
            {
                "row_no": int(turn.get("turn_index") or 0),
                "speaker": turn.get("speaker_label") or "未标注",
                "text": turn.get("turn_text") or "",
            }
            for turn in turns
        ],
        "columns": column_labels,
        "grid": grid_rows,
        "affordances": affordances,
    }


def serialize_diagraph_csv(payload):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["跨句图谱"])
    writer.writerow([payload["notice"]])
    writer.writerow([])
    header = ["行号", "说话人", *payload["columns"]]
    writer.writerow(header)
    for row in payload["grid"]:
        writer.writerow([
            row["row_no"],
            row["speaker"],
            *[row["cells"].get(column, "") for column in payload["columns"]],
        ])
    writer.writerow([])
    writer.writerow(["结构可供性表"])
    writer.writerow(["纵栏", "映射", "关系", "描述"])
    for item in payload["affordances"]:
        writer.writerow([item["column"], item["mapping"], item["relation"], item["description"]])
    return output.getvalue()


def is_interview_item(item):
    return (item.get("source") or "") == INTERVIEW_SOURCE


def split_interview_turns(content):
    text = (content or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    speaker_pattern = re.compile(
        r'(?m)(?:^|\n)[\u200b\ufeff]*\s*(?P<label>[\u4e00-\u9fffA-Za-z0-9+\u00b7\uff08\uff09()\u300a\u300b\u201c\u201d"\u3001 \u3000]{1,34})[\uff1a:]\s*'
    )
    matches = list(speaker_pattern.finditer(text))
    if not matches:
        return []

    turns = []
    skip_speakers = {
        "时间",
        "地点",
        "来源",
        "责任编辑",
        "编辑",
        "记者来源",
        "原标题",
        "编者按",
        "摘要",
        "关键词",
        "链接",
        "网址",
        "声明",
    }
    for index, match in enumerate(matches):
        start = match.start("label")
        end = matches[index + 1].start("label") if index + 1 < len(matches) else len(text)
        turn = text[start:end].strip()
        speaker = re.split(r"[：:]", turn, maxsplit=1)[0].strip()
        if speaker in skip_speakers:
            continue
        turns.append(turn)
    return turns


def clean_interview_turn(turn):
    turn = (turn or "").strip()
    for token in ("???", "???", "???:"):
        index = turn.find(token)
        if index >= 0:
            turn = turn[:index].strip()
    return turn


def build_interview_context(content, keyword="", left_len=30, right_len=30):
    content = content or ""
    if keyword:
        turns = split_interview_turns(content)
        cleaned_turns = [clean_interview_turn(turn) for turn in turns]
        for index, turn in enumerate(cleaned_turns):
            if keyword in turn:
                prev_turn = cleaned_turns[index - 1] if index > 0 else ""
                next_turn = cleaned_turns[index + 1] if index + 1 < len(cleaned_turns) else ""
                return prev_turn, turn, next_turn, prev_turn, next_turn

    fallback_left, fallback_hit, fallback_right = split_context(
        content,
        keyword,
        INTERVIEW_RESULT_SIDE_CHARS,
        INTERVIEW_RESULT_SIDE_CHARS,
    )
    fallback = (fallback_left + fallback_hit + fallback_right).strip()
    fallback = fallback or trim_text(content, INTERVIEW_RESULT_HIT_CHARS)
    return "", fallback, "", "", ""


def interview_label_set():
    return dialogue_label_set()


def dialogue_label_set():
    return {
        "prev": "前序话轮",
        "hit": "命中话轮",
        "next": "后续话轮",
        "context": "",
        "modal_prev": "前序话轮",
        "modal_hit": "命中话轮",
        "modal_next": "后续话轮",
    }


def build_segment_context(item, keyword, left_len=80, right_len=80):
    if is_interview_item(item):
        prev_segment, hit_segment, next_segment, modal_prev, modal_next = build_interview_context(
            item["content"] or "",
            keyword,
            left_len,
            right_len,
        )
        return {
            "file_name": item["title"],
            "dialogue_id": item["id"],
            "prev_segment": prev_segment,
            "hit_segment": hit_segment,
            "hit_segment_html": highlight_keyword(hit_segment, keyword),
            "next_segment": next_segment,
            "modal_prev_segment": modal_prev or prev_segment,
            "modal_hit_segment": hit_segment,
            "modal_next_segment": modal_next or next_segment,
            "labels": interview_label_set(),
            "is_interview": True,
        }

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
            "modal_prev_segment": prev_segment or "",
            "modal_hit_segment": hit_segment,
            "modal_next_segment": next_segment or "",
            "labels": dialogue_label_set(),
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
            "modal_prev_segment": "",
            "modal_hit_segment": "",
            "modal_next_segment": "",
            "labels": dialogue_label_set(),
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
                "modal_prev_segment": left,
                "modal_hit_segment": hit_text,
                "modal_next_segment": right,
                "labels": dialogue_label_set(),
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
        "modal_prev_segment": prev_segment_text,
        "modal_hit_segment": hit_segment,
        "modal_next_segment": next_segment_text,
        "labels": dialogue_label_set(),
    }


init_submission_tables = corpus_repository.init_submission_tables
load_all_data = corpus_repository.load_all_data
count_admin_entries = corpus_repository.count_admin_entries
list_admin_entries_page = corpus_repository.list_admin_entries_page
get_filter_options = corpus_repository.get_filter_options
get_advanced_filter_options = corpus_repository.get_advanced_filter_options
has_fts_table = corpus_repository.has_fts_table
get_active_search_backend = lambda: corpus_repository.get_active_search_backend(get_search_backend())
count_search_results = corpus_repository.count_search_results
count_search_results_fts = corpus_repository.count_search_results_fts
query_search_page = corpus_repository.query_search_page
query_search_page_fts = corpus_repository.query_search_page_fts
get_resonance_presets = corpus_repository.get_resonance_presets
query_resonance_page = corpus_repository.query_resonance_page
count_dialogue_turns = corpus_repository.count_dialogue_turns
insert_entry = corpus_repository.insert_entry
insert_approved_text_submission = corpus_repository.insert_approved_text_submission
insert_approved_multimodal_submission = corpus_repository.insert_approved_multimodal_submission


@app.route("/")
def home():
    sources, years = get_filter_options()
    return render_template("home.html", sources=sources, years=years)


@app.route("/data-sources")
def data_sources():
    return render_template("data_sources.html")


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
        file_info = save_submission_upload(upload)
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
    advanced_filters = corpus_repository.normalize_search_filters({
        "field": request.args.get("field", "content").strip(),
        "mode": request.args.get("mode", "contains").strip(),
        "exclude": request.args.get("exclude", "").strip(),
        "year_from": request.args.get("year_from", "").strip(),
        "year_to": request.args.get("year_to", "").strip(),
        "dataset_name": request.args.get("dataset_name", "").strip(),
        "speaker": request.args.get("speaker", "").strip(),
        "title": request.args.get("title", "").strip(),
        "content_min": request.args.get("content_min", "").strip(),
        "content_max": request.args.get("content_max", "").strip(),
        "has_audio": request.args.get("has_audio", "").strip(),
        "sort": request.args.get("sort", "id_desc").strip(),
    })
    is_advanced_search = corpus_repository.has_advanced_filters(advanced_filters) or request.args.get("advanced") == "1"
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
        total = count_search_results_fts(keyword, source, year, category, advanced_filters)
    else:
        total = count_search_results(keyword, source, year, category, advanced_filters)
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
            filters=advanced_filters,
        )
    else:
        page_rows = query_search_page(
            keyword=keyword,
            source=source,
            year=year,
            category=category,
            limit=query_limit,
            offset=start_idx,
            filters=advanced_filters,
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
        result["source_url"] = result.get("source_url") or ""
        result["crawl_source"] = result.get("crawl_source") or result.get("dataset_name") or result.get("category") or ""
        result["crawl_date"] = result.get("crawl_date") or ""
        result["license_note"] = result.get("license_note") or ""
        result["is_interview"] = bool(result.get("is_interview") or is_interview_item(result))
        audio_file = result.get("audio_file")
        result["audio_url"] = build_corpus_audio_url(audio_file)
        page_results.append(result)

    start_no = start_idx + 1 if total > 0 else 0
    end_no = min(end_idx, total)

    sources, years = get_filter_options()
    categories, datasets = get_advanced_filter_options()
    query_args = {
        "q": keyword,
        "source": source,
        "year": year,
        "category": category,
        "left": left_len,
        "right": right_len,
        "advanced": "1" if is_advanced_search else "",
        **advanced_filters,
    }

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
        categories=categories,
        datasets=datasets,
        advanced_filters=advanced_filters,
        is_advanced_search=is_advanced_search,
        query_args=query_args,
        page=page,
        total_pages=total_pages,
        page_window_start=page_window_start,
        page_window_end=page_window_end,
        start_no=start_no,
        end_no=end_no,
        search_backend=search_backend,
    )


@app.route("/resonance")
def resonance_search():
    preset = corpus_repository.normalize_resonance_preset(request.args.get("preset", "resonance").strip())
    keyword = request.args.get("q", "").strip()
    source = request.args.get("source", "").strip()
    category = request.args.get("category", "").strip()
    page_size = request.args.get("page_size", "10").strip()
    try:
        page_size = int(page_size)
    except ValueError:
        page_size = 20
    page_size = max(1, min(page_size, corpus_repository.MAX_RESONANCE_PAGE_SIZE))
    resonance_sources, resonance_categories = corpus_repository.get_resonance_filter_options_cached()
    return render_template(
        "resonance.html",
        presets=get_resonance_presets(),
        active_preset=preset,
        active_preset_meta=corpus_repository.RESONANCE_PRESETS[preset],
        keyword=keyword,
        source=source,
        category=category,
        sources=resonance_sources,
        categories=resonance_categories,
        query_args={"page_size": page_size},
        should_auto_search=bool(keyword or request.args.get("auto") == "1"),
    )
@app.route("/resonance/data")
@app.route("/api/resonance")
def resonance_data():
    preset = corpus_repository.normalize_resonance_preset(request.args.get("preset", "resonance").strip())
    keyword = request.args.get("q", "").strip()
    source = request.args.get("source", "").strip()
    category = request.args.get("category", "").strip()
    sample = request.args.get("sample", "").strip() == "1"
    cursor = request.args.get("cursor", "").strip()
    start = request.args.get("start", "1").strip()
    try:
        start = max(1, int(start))
    except ValueError:
        start = 1

    page_size = request.args.get("page_size", "10").strip()
    try:
        page_size = int(page_size)
    except ValueError:
        page_size = 20
    page_size = max(1, min(page_size, corpus_repository.MAX_RESONANCE_PAGE_SIZE))
    error_message = ""
    page_data = {"results": [], "has_next": False, "next_cursor": None, "turn_count": 0}
    if keyword and len(keyword) < 2 and not sample:
        error_message = "关键词过短，可能产生大量结果。请尝试输入两个字以上的表达，如‘我觉得’‘台湾问题’。"
    elif not keyword and not sample:
        error_message = "请输入关键词后开始检索；也可以点击预设浏览少量样例。"
    else:
        try:
            page_data = query_resonance_page(
                preset=preset,
                keyword=keyword,
                source=source,
                category=category,
                limit=page_size,
                cursor=cursor,
                include_turn_count=False,
            )
            if page_data.get("missing_pairs"):
                error_message = "共鸣索引尚未生成，请先运行 rebuild_dialogue_pairs。"
            elif page_data.get("unsupported_mode"):
                error_message = "类比检索接口已保留，后续将接入关系框架识别；当前请先使用共鸣、重现、平行、选择或对比。"
        except Exception as exc:
            error_text = str(exc).lower()
            if "diskfull" in exc.__class__.__name__.lower() or "no space left on device" in error_text or "disk full" in error_text:
                error_message = "\u672c\u6b21\u67e5\u8be2\u7ed3\u679c\u8fc7\u591a\uff0c\u5df2\u8d85\u8fc7\u6570\u636e\u5e93\u4e34\u65f6\u7a7a\u95f4\u9650\u5236\u3002\u8bf7\u5c1d\u8bd5\u8f93\u5165\u66f4\u591a\u5173\u952e\u8bcd\u3001\u7f29\u5c0f\u6765\u6e90/\u7c7b\u522b\uff0c\u6216\u5207\u6362\u5176\u4ed6\u5171\u9e23\u7c7b\u578b\u3002"
            else:
                error_message = "\u672c\u6b21\u5171\u9e23\u68c0\u7d22\u6682\u65f6\u65e0\u6cd5\u5b8c\u6210\u3002\u8bf7\u5c1d\u8bd5\u8f93\u5165\u66f4\u591a\u5173\u952e\u8bcd\u3001\u7f29\u5c0f\u6765\u6e90/\u7c7b\u522b\uff0c\u6216\u7a0d\u540e\u91cd\u8bd5\u3002"
            print(f"[resonance] async query failed: {exc!r}", flush=True)

    results = []
    for item in page_data["results"]:
        result = dict(item)
        terms = list(result.get("terms") or [])
        result["turn_a_html"] = highlight_resonance_text(result.get("turn_a_text"), terms, keyword)
        result["turn_b_html"] = highlight_resonance_text(result.get("turn_b_text"), terms, keyword)
        result["source_url"] = result.get("source_url") or ""
        result["crawl_source"] = result.get("crawl_source") or result.get("dataset_name") or result.get("category") or ""
        result["crawl_date"] = result.get("crawl_date") or ""
        result["license_note"] = result.get("license_note") or ""
        result["audio_url"] = build_corpus_audio_url(result.get("audio_file"))
        result["dataset_name"] = result.get("dataset_name") or result.get("crawl_source") or ""
        result["fragment_label"] = f"{result.get('conversation_key') or '片段'} · {result.get('turn_a_index')}-{result.get('turn_b_index')}"
        results.append(result)

    start_no = start if results else 0
    end_no = start + len(results) - 1 if results else 0
    html = render_template(
        "_resonance_results.html",
        results=results,
        start_no=start_no,
    )
    return jsonify({
        "html": html,
        "has_next": page_data["has_next"],
        "next_cursor": page_data.get("next_cursor"),
        "next_start": end_no + 1,
        "error_message": error_message,
        "count": len(results),
        "mode": "sample" if sample else "search",
        "page_size": page_size,
    })


@app.route("/api/diagraph/<int:pair_id>")
def diagraph_data(pair_id):
    window_mode = normalize_diagraph_window(request.args.get("window", "pair"))
    pair, turns = corpus_repository.get_diagraph_turns(pair_id, window_mode=window_mode)
    if not pair:
        return jsonify({"error": "未找到对应的共鸣结果。"}), 404
    if not turns:
        return jsonify({"error": "当前片段未找到可用话轮，暂时无法生成跨句图谱。"}), 404
    payload = build_diagraph_payload(pair, turns, window_mode)
    return jsonify(payload)


@app.route("/api/diagraph/export_csv")
@app.route("/api/diagraph/export_excel")
def diagraph_export():
    pair_id = request.args.get("pair_id", "").strip()
    try:
        pair_id = int(pair_id)
    except (TypeError, ValueError):
        return jsonify({"error": "缺少有效的 pair_id。"}), 400
    window_mode = normalize_diagraph_window(request.args.get("window", "pair"))
    pair, turns = corpus_repository.get_diagraph_turns(pair_id, window_mode=window_mode)
    if not pair:
        return jsonify({"error": "未找到对应的共鸣结果。"}), 404
    if not turns:
        return jsonify({"error": "当前片段未找到可用话轮，暂时无法导出图谱。"}), 404
    payload = build_diagraph_payload(pair, turns, window_mode)
    csv_text = "\ufeff" + serialize_diagraph_csv(payload)
    filename = f"diagraph_pair_{pair_id}_{window_mode}.csv"
    return app.response_class(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/resonance/context/<int:entry_id>")
def resonance_context(entry_id):
    try:
        context = corpus_repository.get_resonance_entry_context(entry_id)
    except Exception as exc:
        print(f"[resonance] context failed: {exc!r}", flush=True)
        return jsonify({"error": "原文上下文暂时无法加载，请稍后重试。"}), 500
    if not context:
        return jsonify({"error": "未找到对应原文。"}), 404
    return jsonify(context)


@app.route("/audio/<path:filename>")
def audio_file(filename):
    try:
        return get_corpus_audio_response(filename)
    except FileNotFoundError:
        return "Audio file is not available.", 404


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
            error = "管理员账号未配置，请先设置 ADMIN_USERNAME 和 ADMIN_PASSWORD。"
        elif compare_digest(username, expected_username) and compare_digest(password, expected_password):
            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = username
            return redirect(get_admin_next_url())
        else:
            error = "用户名或密码错误，请重试。"

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
            error="请填写标题、内容和来源。"
        )

    try:
        year_value = int(year) if year else None
    except ValueError:
        year_value = None

    insert_entry(title, content, source_type, year_value, category)

    return render_template(
        "admin.html",
        success=True,
        success_message="语料已成功录入。"
    )


@app.route("/admin/list")
def admin_list():
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    per_page = 50
    offset = (page - 1) * per_page
    rows = list_admin_entries_page(limit=per_page + 1, offset=offset)
    has_next = len(rows) > per_page
    data = rows[:per_page]
    return render_template(
        "admin_list.html",
        entries=data,
        page=page,
        has_prev=page > 1,
        has_next=has_next,
    )


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

    return render_template(
        "admin_submission_detail.html",
        submission=submission,
        can_transcribe=is_transcribable_submission(submission),
    )


@app.route("/admin/submissions/<int:submission_id>/approve", methods=["POST"])
def approve_submission(submission_id):
    admin_note = clean_form_value("admin_note")
    edited_text_content = request.form.get("text_content")
    if edited_text_content is not None:
        corpus_repository.update_submission_text_content(submission_id, edited_text_content.strip())
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


@app.route("/admin/submissions/<int:submission_id>/transcribe", methods=["POST"])
def transcribe_submission(submission_id):
    submission = corpus_repository.get_submission_by_id(submission_id)
    if submission is None:
        return render_template("admin_submission_detail.html", error="未找到该投稿。"), 404

    if not is_transcribable_submission(submission):
        return render_template(
            "admin_submission_detail.html",
            submission=submission,
            can_transcribe=False,
            transcription_error="该投稿不是可转写的音频或视频文件。",
        ), 400

    model_name = os.getenv("TRANSCRIBE_MODEL", "whisper-1").strip() or "whisper-1"
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return render_template(
            "admin_submission_detail.html",
            submission=submission,
            can_transcribe=True,
            transcription_error="未配置转写 API Key，请先设置 OPENAI_API_KEY。",
        ), 400

    try:
        TRANSCRIPTION_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        transcript = transcribe_submission_media(submission, TRANSCRIPTION_TEMP_DIR, model_name)
        if not transcript:
            raise RuntimeError("转写结果为空，请检查媒体文件是否包含可识别语音。")
        corpus_repository.update_submission_text_content(submission_id, transcript)
    except RuntimeError as exc:
        return render_template(
            "admin_submission_detail.html",
            submission=submission,
            can_transcribe=True,
            transcription_error=str(exc),
        ), 400
    except Exception:
        return render_template(
            "admin_submission_detail.html",
            submission=submission,
            can_transcribe=True,
            transcription_error="转写失败，请稍后重试，或检查媒体文件和转写配置。",
        ), 500
    updated_submission = corpus_repository.get_submission_by_id(submission_id)
    return render_template(
        "admin_submission_detail.html",
        submission=updated_submission,
        can_transcribe=is_transcribable_submission(updated_submission),
        transcription_success=f"已使用 {model_name} 完成转写，内容已更新到待审核记录。",
    )


@app.route("/admin/submissions/<int:submission_id>/reject", methods=["POST"])
def reject_submission(submission_id):
    admin_note = clean_form_value("admin_note")
    corpus_repository.reject_submission_record(submission_id, admin_note)
    return redirect(url_for("admin_submission_detail", submission_id=submission_id, rejected=1))


@app.route("/admin/submissions/<int:submission_id>/delete", methods=["POST"])
def delete_submission(submission_id):
    submission = corpus_repository.delete_submission_record(submission_id)
    if submission and submission["status"] != "approved":
        delete_submission_upload(
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
        return build_submission_download_response(
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

try:
    init_submission_tables()
except Exception as exc:
    print(f"[startup-db] submission table init skipped: {exc!r}", flush=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
