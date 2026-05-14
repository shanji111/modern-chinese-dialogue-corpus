import os
import re
import sqlite3
import time
import json

from database import DATABASE_BACKEND, get_db_connection, get_readonly_db_connection, row_to_dict
from db_utils import compute_content_hash, utc_timestamp


FTS_TABLE = "corpus_entries_fts"
POSTGRES_SEARCH_FIELDS = ("content", "title", "speaker", "current_segment", "segment_text")
POSTGRES_SEARCH_TEXT_FIELD = "search_text"
SEARCH_FIELD_COLUMNS = {
    "all": ("title", "content", "speaker", "current_segment", "segment_text"),
    "content": ("content",),
    "title": ("title",),
    "speaker": ("speaker",),
    "segment": ("current_segment", "segment_text"),
}
SEARCH_MODES = {"contains", "exact", "starts_with", "ends_with"}
SORT_OPTIONS = {
    "id_desc": "id DESC",
    "id_asc": "id ASC",
    "year_desc": "year DESC, id DESC",
    "year_asc": "year ASC, id DESC",
    "title_asc": "title ASC, id DESC",
    "start_time_asc": "start_time ASC, id DESC",
}
ENABLE_QUERY_TIMING = os.environ.get("ENABLE_QUERY_TIMING", "").strip().lower() in {"1", "true", "yes", "on"}
POSTGRES_FAST_SEARCH = os.environ.get("POSTGRES_FAST_SEARCH", "").strip().lower() in {"1", "true", "yes", "on"}
TURN_TABLE = "dialogue_turns"
PAIR_TABLE = "dialogue_pairs"
STATS_TABLE = "corpus_stats"
MIN_TURN_TEXT_CHARS = 2
DEFAULT_RESONANCE_CANDIDATE_LIMIT = 300
MAX_RESONANCE_CANDIDATE_LIMIT = 1000
MAX_RESONANCE_PAGE_SIZE = 50
RESONANCE_CONTEXT_CHARS = 6000
RESONANCE_SAMPLE_CANDIDATE_LIMIT = 100
RESONANCE_FILTER_SOURCES = ()
RESONANCE_PRESET_ALIASES = {
    "lexical_echo": "reproduction",
    "pattern_reuse": "parallel",
    "qa_response": "resonance",
    "question_response": "resonance",
    "contrast_response": "contrast",
    "negation_turn": "contrast",
    "repair_revision": "selection",
    "repair_repetition": "selection",
}
PAIR_PRESET_FLAGS = {
    "lexical_echo": "has_lexical_echo",
    "pattern_reuse": "has_pattern_reuse",
    "qa_response": "has_question_response",
    "contrast_response": "has_negation_turn",
    "repair_revision": "has_repair_repetition",
}
DIALOGUE_SYNTAX_MODE_FLAGS = {
    "resonance": ("has_lexical_echo", "has_pattern_reuse", "has_question_response", "has_repair_repetition"),
    "reproduction": ("has_lexical_echo",),
    "parallel": ("has_pattern_reuse",),
    "selection": ("has_repair_repetition",),
    "contrast": ("has_negation_turn",),
    "analogy": (),
}
RESONANCE_FILTER_CATEGORIES = ("日常对话", "访谈语料", "影视对白", "课堂互动", "多模态语料", "外交部记者会", "其他")
RESONANCE_PRESETS = {
    "resonance": {
        "label": "共鸣",
        "description": "检索相邻话轮中较明确的词汇、句式、问答或修正呼应；单个否定词不单独算入。",
    },
    "reproduction": {
        "label": "重现",
        "description": "检索 A 轮中的词语或表达在 B 轮被复现、重复使用的例子。",
    },
    "parallel": {
        "label": "平行",
        "description": "检索两个话轮共享相似句式框架，形成平行结构的例子。",
    },
    "selection": {
        "label": "选择",
        "description": "检索后一话轮选择前一话轮部分成分，并伴随补充、修正或改写推进的例子。",
    },
    "contrast": {
        "label": "对比",
        "description": "检索后一话轮通过否定、转折或对照标记回应前一话轮的例子。",
    },
    "analogy": {
        "label": "类比",
        "description": "保留接口，后续用于识别更抽象的语义或结构对应关系。",
        "disabled_reason": "类比需要更复杂的语义与结构对齐，当前先保留接口。",
    },
}
TOKEN_STOPWORDS = {
    "我们", "你们", "他们", "她们", "它们", "这个", "那个", "这些", "那些", "这里", "那里",
    "什么", "怎么", "为什么", "是不是", "有没有", "一个", "一种", "一些", "一下", "一样",
    "就是", "还是", "还是说", "然后", "所以", "但是", "不过", "因为", "如果", "可以",
    "应该", "可能", "没有", "不是", "已经", "现在", "这样", "那样", "自己", "大家",
    "进行", "表示", "认为", "觉得", "问题", "情况", "方面", "时候", "或者", "以及",
    "and", "the", "that", "this", "with", "from", "have", "will", "would", "could", "should",
}
TOKEN_STOP_CHARS = set("的一是在有和与及或就都也很不没吗呢啊吧呀嘛么着过了我你他她它这那")
COMMON_PHRASE_MIN_CHARS = 2
SPEAKER_LABEL_PATTERN = re.compile(
    r"^\s*(?P<label>[^:：\s][^:：]{0,31})\s*[：:]\s*(?P<text>.+?)\s*$"
)
INLINE_SPEAKER_BOUNDARY_PATTERN = re.compile(
    r"(?:^|(?<=[。！？!?；;]))\s*(?=[^:：\s][^:：]{0,31}\s*[：:])"
)
FUNCTION_PATTERNS = (
    ("我觉得...", re.compile(r"我觉得|我认为|我想|我感觉")),
    ("不是...而是...", re.compile(r"不是|而是|并非")),
    ("能不能...", re.compile(r"能不能|可不可以|可以不可以|能否|是否可以")),
    ("为什么...", re.compile(r"为什么|为何|怎么会|怎么")),
    ("如果...就...", re.compile(r"如果|要是|假如|只要|就")),
    ("一边...一边...", re.compile(r"一边|同时|一方面|另一方面")),
)
QUESTION_MARKERS = ("?", "？", "吗", "呢", "么", "为什么", "为何", "怎么", "能不能", "可不可以", "是不是", "有没有", "是否", "谁", "什么", "哪", "哪里", "多少", "几")
RESPONSE_MARKERS = ("是", "不是", "对", "没有", "因为", "所以", "其实", "我觉得", "我认为", "可以", "不能", "应该", "需要", "这个", "那")
CONTRAST_MARKERS = ("不是", "不能", "没有", "没法", "不一定", "不属于", "并不", "不对", "但是", "不过", "然而", "可是", "而是", "并非", "相反", "却")
REVISION_MARKERS = ("不是", "不对", "应该说", "也就是说", "换句话说", "准确地说", "其实", "我是说", "或者说", "更准确", "补充", "另外", "而且")
_DIALOGUE_PAIRS_TABLE_EXISTS_CACHE = None
STORAGE_METADATA_COLUMNS = {
    "storage_backend": "TEXT DEFAULT 'local'",
    "object_key": "TEXT",
    "file_url": "TEXT",
    "file_hash": "TEXT",
}


def is_postgres():
    return DATABASE_BACKEND == "postgres"


def placeholder():
    return "%s" if is_postgres() else "?"


def close_connection(conn):
    conn.close()


def timing_log(label, start_time, **details):
    if not ENABLE_QUERY_TIMING:
        return
    detail_text = " ".join(f"{key}={value}" for key, value in details.items())
    print(f"[query_timing] {label} elapsed_ms={(time.perf_counter() - start_time) * 1000:.2f} {detail_text}", flush=True)


def timed_connection(label):
    start = time.perf_counter()
    conn = get_db_connection()
    if is_postgres():
        timing_log(f"{label}.connect", start)
    return conn


def is_missing_search_text_error(exc):
    return is_postgres() and "search_text" in str(exc).lower()


def fetch_all_dicts(cursor):
    return [row_to_dict(row) for row in cursor.fetchall()]


def fetch_one_dict(cursor):
    return row_to_dict(cursor.fetchone())


def execute_many(conn, sql, rows):
    if not rows:
        return
    if hasattr(conn, "executemany"):
        conn.executemany(sql, rows)
        return
    with conn.cursor() as cursor:
        cursor.executemany(sql, rows)


def safe_rollback(conn):
    try:
        conn.rollback()
    except Exception:
        pass


def build_search_text(*values):
    return " ".join(str(value).strip() for value in values if value is not None and str(value).strip())


def normalize_turn_text(value):
    return re.sub(r"\s+", " ", (value or "").strip())


def split_inline_speaker_turns(line):
    line = (line or "").strip()
    if not line:
        return []
    boundaries = [match.start() for match in INLINE_SPEAKER_BOUNDARY_PATTERN.finditer(line)]
    if not boundaries or boundaries[0] != 0:
        boundaries.insert(0, 0)
    if len(boundaries) == 1:
        return [line]

    parts = []
    for index, start in enumerate(boundaries):
        end = boundaries[index + 1] if index + 1 < len(boundaries) else len(line)
        piece = line[start:end].strip()
        if piece:
            parts.append(piece)
    return parts or [line]


def parse_speaker_turn(line):
    line = normalize_turn_text(line)
    match = SPEAKER_LABEL_PATTERN.match(line)
    if not match:
        return "", line
    label = match.group("label").strip()
    text = match.group("text").strip()
    if len(label) > 32 or not text:
        return "", line
    return label, text


def split_entry_turns(entry):
    current_segment = normalize_turn_text(entry.get("current_segment") or entry.get("segment_text") or "")
    if current_segment:
        speaker = normalize_turn_text(entry.get("speaker") or "")
        turn_index = entry.get("segment_index") or 1
        return [{
            "turn_index": int(turn_index) if str(turn_index).isdigit() else 1,
            "speaker_label": speaker,
            "turn_text": current_segment,
            "conversation_key": normalize_turn_text(entry.get("conversation_id") or f"entry:{entry['id']}"),
        }]

    text = (entry.get("content") or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    turns = []
    for raw_line in text.split("\n"):
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        for piece in split_inline_speaker_turns(raw_line):
            speaker, turn_text = parse_speaker_turn(piece)
            turn_text = normalize_turn_text(turn_text)
            if len(turn_text) < MIN_TURN_TEXT_CHARS:
                continue
            turns.append({
                "turn_index": len(turns) + 1,
                "speaker_label": speaker,
                "turn_text": turn_text,
                "conversation_key": f"entry:{entry['id']}",
            })
    return turns


def create_dialogue_turns_schema(conn):
    if is_postgres():
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {TURN_TABLE} (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                entry_id BIGINT NOT NULL,
                turn_index INTEGER NOT NULL,
                speaker_label TEXT,
                turn_text TEXT NOT NULL,
                source TEXT,
                category TEXT,
                dataset_name TEXT,
                conversation_key TEXT NOT NULL
            )
        """)
    else:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {TURN_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL,
                turn_index INTEGER NOT NULL,
                speaker_label TEXT,
                turn_text TEXT NOT NULL,
                source TEXT,
                category TEXT,
                dataset_name TEXT,
                conversation_key TEXT NOT NULL
            )
        """)

    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_turns_entry ON {TURN_TABLE} (entry_id)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_turns_entry_id ON {TURN_TABLE} (entry_id)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_turns_conversation ON {TURN_TABLE} (conversation_key, turn_index)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_turns_conversation_turn ON {TURN_TABLE} (conversation_key, turn_index)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_turns_source ON {TURN_TABLE} (source)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_turns_category ON {TURN_TABLE} (category)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_turns_source_category_id ON {TURN_TABLE} (source, category, id)")
    if not is_postgres():
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_turns_turn_text ON {TURN_TABLE} (turn_text)")


def create_dialogue_pairs_schema(conn):
    global _DIALOGUE_PAIRS_TABLE_EXISTS_CACHE
    if is_postgres():
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {PAIR_TABLE} (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                turn_a_id BIGINT NOT NULL,
                turn_b_id BIGINT NOT NULL,
                entry_id BIGINT NOT NULL,
                conversation_key TEXT NOT NULL,
                turn_index_a INTEGER NOT NULL,
                turn_index_b INTEGER NOT NULL,
                speaker_a TEXT,
                speaker_b TEXT,
                text_a TEXT NOT NULL,
                text_b TEXT NOT NULL,
                source TEXT,
                category TEXT,
                dataset_name TEXT,
                shared_terms TEXT,
                markers TEXT,
                has_lexical_echo INTEGER DEFAULT 0,
                has_pattern_reuse INTEGER DEFAULT 0,
                has_question_response INTEGER DEFAULT 0,
                has_negation_turn INTEGER DEFAULT 0,
                has_repair_repetition INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {PAIR_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn_a_id INTEGER NOT NULL,
                turn_b_id INTEGER NOT NULL,
                entry_id INTEGER NOT NULL,
                conversation_key TEXT NOT NULL,
                turn_index_a INTEGER NOT NULL,
                turn_index_b INTEGER NOT NULL,
                speaker_a TEXT,
                speaker_b TEXT,
                text_a TEXT NOT NULL,
                text_b TEXT NOT NULL,
                source TEXT,
                category TEXT,
                dataset_name TEXT,
                shared_terms TEXT,
                markers TEXT,
                has_lexical_echo INTEGER DEFAULT 0,
                has_pattern_reuse INTEGER DEFAULT 0,
                has_question_response INTEGER DEFAULT 0,
                has_negation_turn INTEGER DEFAULT 0,
                has_repair_repetition INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_pairs_a ON {PAIR_TABLE}(turn_a_id)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_pairs_b ON {PAIR_TABLE}(turn_b_id)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_pairs_entry ON {PAIR_TABLE}(entry_id)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_pairs_source_category_id ON {PAIR_TABLE}(source, category, id)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_pairs_lexical ON {PAIR_TABLE}(has_lexical_echo, id)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_pairs_pattern ON {PAIR_TABLE}(has_pattern_reuse, id)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_pairs_question ON {PAIR_TABLE}(has_question_response, id)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_pairs_negation ON {PAIR_TABLE}(has_negation_turn, id)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_pairs_repair ON {PAIR_TABLE}(has_repair_repetition, id)")
    _DIALOGUE_PAIRS_TABLE_EXISTS_CACHE = True


def create_corpus_stats_schema(conn):
    if is_postgres():
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {STATS_TABLE} (
                stat_key TEXT PRIMARY KEY,
                stat_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {STATS_TABLE} (
                stat_key TEXT PRIMARY KEY,
                stat_value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def set_corpus_stat(conn, key, value):
    create_corpus_stats_schema(conn)
    marker = placeholder()
    if is_postgres():
        conn.execute(
            f"""
            INSERT INTO {STATS_TABLE} (stat_key, stat_value, updated_at)
            VALUES ({marker}, {marker}, CURRENT_TIMESTAMP)
            ON CONFLICT (stat_key)
            DO UPDATE SET stat_value = EXCLUDED.stat_value, updated_at = CURRENT_TIMESTAMP
            """,
            (key, str(value)),
        )
    else:
        conn.execute(
            f"""
            INSERT INTO {STATS_TABLE} (stat_key, stat_value, updated_at)
            VALUES ({marker}, {marker}, CURRENT_TIMESTAMP)
            ON CONFLICT(stat_key)
            DO UPDATE SET stat_value = excluded.stat_value, updated_at = CURRENT_TIMESTAMP
            """,
            (key, str(value)),
        )


def get_corpus_stat(key):
    conn = get_db_connection()
    marker = placeholder()
    try:
        row = fetch_one_dict(conn.execute(
            f"SELECT stat_value FROM {STATS_TABLE} WHERE stat_key = {marker} LIMIT 1",
            (key,),
        ))
        return (row or {}).get("stat_value") or ""
    except Exception:
        return ""
    finally:
        close_connection(conn)


def get_cached_dialogue_turn_count():
    value = get_corpus_stat("dialogue_turn_count")
    try:
        return int(value) if value else None
    except ValueError:
        return None


def get_resonance_filter_options_cached():
    return list(RESONANCE_FILTER_SOURCES), list(RESONANCE_FILTER_CATEGORIES)


def sqlite_integrity_check(conn):
    if is_postgres():
        return "ok"
    row = conn.execute("PRAGMA integrity_check").fetchone()
    if row is None:
        return "missing integrity_check result"
    try:
        return row[0]
    except (KeyError, IndexError):
        return next(iter(dict(row).values()))


def prepare_sqlite_for_safe_indexing(conn):
    if is_postgres():
        return
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")


def has_dialogue_turns_table():
    conn = get_db_connection()
    try:
        if is_postgres():
            row = conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_name = %s
                """,
                (TURN_TABLE,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                (TURN_TABLE,),
            ).fetchone()
        return row is not None
    finally:
        close_connection(conn)


def rebuild_dialogue_turns(batch_size=1000, progress_callback=None):
    conn = get_db_connection()
    marker = placeholder()
    insert_columns = (
        "entry_id", "turn_index", "speaker_label", "turn_text",
        "source", "category", "dataset_name", "conversation_key",
    )
    insert_sql = (
        f"INSERT INTO {TURN_TABLE} ({', '.join(insert_columns)}) "
        f"VALUES ({', '.join(marker for _ in insert_columns)})"
    )
    inserted = 0
    entries = 0
    try:
        create_dialogue_turns_schema(conn)
        if is_postgres():
            conn.execute(f"TRUNCATE TABLE {TURN_TABLE} RESTART IDENTITY")
            conn.commit()
        else:
            conn.execute(f"DELETE FROM {TURN_TABLE}")
        rows = conn.execute("""
            SELECT id, title, content, source, category, dataset_name,
                   current_segment, segment_text, speaker, conversation_id, segment_index
            FROM corpus_entries
            ORDER BY id
        """).fetchall()
        batch = []
        total_rows = len(rows)
        if progress_callback:
            progress_callback({
                "phase": "start",
                "processed": 0,
                "total": total_rows,
                "entries_with_turns": entries,
                "inserted_turns": inserted,
            })
        for index, row in enumerate(rows, start=1):
            entry = row_to_dict(row)
            turns = split_entry_turns(entry)
            if turns:
                entries += 1
            for turn in turns:
                batch.append((
                    entry["id"],
                    turn["turn_index"],
                    turn["speaker_label"],
                    turn["turn_text"],
                    entry.get("source") or "",
                    entry.get("category") or "",
                    entry.get("dataset_name") or "",
                    turn["conversation_key"],
                ))
                if len(batch) >= batch_size:
                    execute_many(conn, insert_sql, batch)
                    inserted += len(batch)
                    batch.clear()
                    if is_postgres():
                        conn.commit()
            if progress_callback and (index % batch_size == 0 or index == total_rows):
                progress_callback({
                    "phase": "processing",
                    "processed": index,
                    "total": total_rows,
                    "entries_with_turns": entries,
                    "inserted_turns": inserted + len(batch),
                })
        if batch:
            execute_many(conn, insert_sql, batch)
            inserted += len(batch)
            if is_postgres():
                conn.commit()
        set_corpus_stat(conn, "dialogue_turn_count", inserted)
        conn.commit()
        if progress_callback:
            progress_callback({
                "phase": "done",
                "processed": total_rows,
                "total": total_rows,
                "entries_with_turns": entries,
                "inserted_turns": inserted,
            })
        return {"entries": entries, "turns": inserted}
    except Exception:
        safe_rollback(conn)
        raise
    finally:
        close_connection(conn)


def count_dialogue_turns():
    if not has_dialogue_turns_table():
        return 0
    conn = get_db_connection()
    try:
        row = fetch_one_dict(conn.execute(f"SELECT COUNT(*) AS total FROM {TURN_TABLE}"))
        return row["total"]
    finally:
        close_connection(conn)


def has_dialogue_pairs_table():
    global _DIALOGUE_PAIRS_TABLE_EXISTS_CACHE
    if _DIALOGUE_PAIRS_TABLE_EXISTS_CACHE is not None:
        return _DIALOGUE_PAIRS_TABLE_EXISTS_CACHE
    conn = get_readonly_db_connection()
    try:
        if is_postgres():
            row = conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_name = %s
                """,
                (PAIR_TABLE,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                (PAIR_TABLE,),
            ).fetchone()
        _DIALOGUE_PAIRS_TABLE_EXISTS_CACHE = row is not None
        return _DIALOGUE_PAIRS_TABLE_EXISTS_CACHE
    finally:
        close_connection(conn)


def count_dialogue_pairs():
    if not has_dialogue_pairs_table():
        return 0
    conn = get_readonly_db_connection()
    try:
        row = fetch_one_dict(conn.execute(f"SELECT COUNT(*) AS total FROM {PAIR_TABLE}"))
        return row["total"]
    finally:
        close_connection(conn)


def dialogue_pairs_has_rows(conn):
    try:
        return conn.execute(f"SELECT 1 FROM {PAIR_TABLE} LIMIT 1").fetchone() is not None
    except Exception:
        return False


def ensure_postgres_dialogue_turn_text_trigram_index(conn=None):
    if not is_postgres():
        return False
    owns_connection = conn is None
    if owns_connection:
        conn = get_db_connection()
    try:
        conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_turns_turn_text_trgm ON {TURN_TABLE} USING gin (turn_text gin_trgm_ops)")
        if owns_connection:
            conn.commit()
        return True
    except Exception as exc:
        print(f"PostgreSQL trigram index skipped for {TURN_TABLE}: {exc}", flush=True)
        if owns_connection:
            try:
                conn.rollback()
            except Exception:
                pass
        return False
    finally:
        if owns_connection:
            close_connection(conn)


def ensure_postgres_dialogue_pairs_trigram_indexes(conn=None):
    if not is_postgres():
        return False
    owns_connection = conn is None
    if owns_connection:
        conn = get_db_connection()
    try:
        conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_pairs_text_a_trgm ON {PAIR_TABLE} USING gin (text_a gin_trgm_ops)")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dialogue_pairs_text_b_trgm ON {PAIR_TABLE} USING gin (text_b gin_trgm_ops)")
        if owns_connection:
            conn.commit()
        return True
    except Exception as exc:
        print(f"PostgreSQL trigram indexes skipped for {PAIR_TABLE}: {exc}", flush=True)
        if owns_connection:
            try:
                conn.rollback()
            except Exception:
                pass
        return False
    finally:
        if owns_connection:
            close_connection(conn)


def ensure_storage_metadata_columns(conn):
    table_names = ("corpus_submissions", "multimodal_entries")
    if is_postgres():
        for table_name in table_names:
            for column, column_type in STORAGE_METADATA_COLUMNS.items():
                conn.execute(f'ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column} {column_type}')
        return
    for table_name in table_names:
        try:
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
            for column, column_type in STORAGE_METADATA_COLUMNS.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column} {column_type}")
        except sqlite3.OperationalError as exc:
            print(f"SQLite storage metadata migration skipped for {table_name}: {exc}", flush=True)


def has_storage_metadata_schema(conn, table_name):
    if is_postgres():
        return True
    try:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    except sqlite3.OperationalError:
        return False
    return set(STORAGE_METADATA_COLUMNS).issubset(existing)


def init_submission_tables():
    conn = get_db_connection()
    try:
        if is_postgres():
            conn.execute("""
                CREATE TABLE IF NOT EXISTS corpus_submissions (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
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
                    file_size BIGINT,
                    storage_backend TEXT DEFAULT 'local',
                    object_key TEXT,
                    file_url TEXT,
                    file_hash TEXT,
                    status TEXT DEFAULT 'pending',
                    admin_note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP,
                    reviewed_by TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS multimodal_entries (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    submission_id BIGINT UNIQUE,
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
                    file_size BIGINT,
                    storage_backend TEXT DEFAULT 'local',
                    object_key TEXT,
                    file_url TEXT,
                    file_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
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
                    storage_backend TEXT DEFAULT 'local',
                    object_key TEXT,
                    file_url TEXT,
                    file_hash TEXT,
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
                    storage_backend TEXT DEFAULT 'local',
                    object_key TEXT,
                    file_url TEXT,
                    file_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        ensure_storage_metadata_columns(conn)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_status ON corpus_submissions (status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_created_at ON corpus_submissions (created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_multimodal_submission_id ON multimodal_entries (submission_id)")
        conn.commit()
    finally:
        close_connection(conn)


def load_all_data():
    conn = get_db_connection()
    try:
        return fetch_all_dicts(conn.execute("SELECT * FROM corpus_entries ORDER BY id DESC"))
    finally:
        close_connection(conn)


def get_filter_options():
    start = time.perf_counter()
    conn = timed_connection("get_filter_options")
    try:
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
        return sources, years
    finally:
        close_connection(conn)
        if is_postgres():
            timing_log("get_filter_options.total", start)


def get_advanced_filter_options():
    conn = timed_connection("get_advanced_filter_options")
    try:
        categories = [
            row["category"]
            for row in conn.execute("""
                SELECT DISTINCT category
                FROM corpus_entries
                WHERE category IS NOT NULL AND TRIM(category) != ''
                ORDER BY category
            """).fetchall()
        ]
        datasets = [
            row["dataset_name"]
            for row in conn.execute("""
                SELECT DISTINCT dataset_name
                FROM corpus_entries
                WHERE dataset_name IS NOT NULL AND TRIM(dataset_name) != ''
                ORDER BY dataset_name
                LIMIT 300
            """).fetchall()
        ]
        return categories, datasets
    finally:
        close_connection(conn)


def escape_like(value):
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def normalize_search_filters(filters=None):
    filters = dict(filters or {})
    filters.setdefault("field", "content")
    filters.setdefault("mode", "contains")
    filters.setdefault("exclude", "")
    filters.setdefault("year_from", "")
    filters.setdefault("year_to", "")
    filters.setdefault("dataset_name", "")
    filters.setdefault("speaker", "")
    filters.setdefault("title", "")
    filters.setdefault("content_min", "")
    filters.setdefault("content_max", "")
    filters.setdefault("has_audio", "")
    filters.setdefault("sort", "id_desc")
    if filters["field"] not in SEARCH_FIELD_COLUMNS:
        filters["field"] = "content"
    if filters["mode"] not in SEARCH_MODES:
        filters["mode"] = "contains"
    if filters["sort"] not in SORT_OPTIONS:
        filters["sort"] = "id_desc"
    return filters


def build_like_pattern(value, mode="contains"):
    escaped = escape_like(value)
    if mode == "exact":
        return escaped
    if mode == "starts_with":
        return f"{escaped}%"
    if mode == "ends_with":
        return f"%{escaped}"
    return f"%{escaped}%"


def add_text_search_clause(where_clauses, params, keyword, columns, mode="contains", negate=False, table_name=""):
    if not keyword:
        return
    marker = placeholder()
    prefix = f"{table_name}." if table_name else ""
    like_operator = "ILIKE" if is_postgres() else "LIKE"
    operator = f"NOT {like_operator}" if negate else like_operator
    joiner = " AND " if negate else " OR "
    parts = [f"COALESCE({prefix}{column}, '') {operator} {marker} ESCAPE '\\'" for column in columns]
    where_clauses.append(f"({joiner.join(parts)})")
    params.extend([build_like_pattern(keyword, mode)] * len(columns))


def add_int_filter(where_clauses, params, column, value, operator, table_name=""):
    if value in (None, ""):
        return
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return
    marker = placeholder()
    prefix = f"{table_name}." if table_name else ""
    where_clauses.append(f"{prefix}{column} {operator} {marker}")
    params.append(parsed)


def build_sqlite_filter_clauses(source="", year="", category="", table_name="", filters=None):
    marker = placeholder()
    where_clauses = []
    params = []
    prefix = f"{table_name}." if table_name else ""
    filters = normalize_search_filters(filters)
    if source:
        where_clauses.append(f"{prefix}source = {marker}")
        params.append(source)
    if year:
        try:
            where_clauses.append(f"{prefix}year = {marker}")
            params.append(int(year))
        except ValueError:
            pass
    if category:
        where_clauses.append(f"{prefix}category = {marker}")
        params.append(category)
    if filters["year_from"]:
        add_int_filter(where_clauses, params, "year", filters["year_from"], ">=", table_name)
    if filters["year_to"]:
        add_int_filter(where_clauses, params, "year", filters["year_to"], "<=", table_name)
    if filters["dataset_name"]:
        where_clauses.append(f"{prefix}dataset_name = {marker}")
        params.append(filters["dataset_name"])
    if filters["speaker"]:
        where_clauses.append(f"COALESCE({prefix}speaker, '') LIKE {marker} ESCAPE '\\'")
        params.append(build_like_pattern(filters["speaker"]))
    if filters["title"]:
        where_clauses.append(f"COALESCE({prefix}title, '') LIKE {marker} ESCAPE '\\'")
        params.append(build_like_pattern(filters["title"]))
    if filters["content_min"]:
        try:
            where_clauses.append(f"LENGTH({prefix}content) >= {marker}")
            params.append(int(filters["content_min"]))
        except (TypeError, ValueError):
            pass
    if filters["content_max"]:
        try:
            where_clauses.append(f"LENGTH({prefix}content) <= {marker}")
            params.append(int(filters["content_max"]))
        except (TypeError, ValueError):
            pass
    if filters["has_audio"] == "1":
        where_clauses.append(f"{prefix}audio_file IS NOT NULL AND TRIM({prefix}audio_file) != ''")
    return where_clauses, params


def build_postgres_search_where(keyword="", source="", year="", category="", filters=None):
    where_clauses = []
    params = []
    filters = normalize_search_filters(filters)
    if keyword:
        columns = (POSTGRES_SEARCH_TEXT_FIELD,) if filters["field"] == "all" else SEARCH_FIELD_COLUMNS[filters["field"]]
        add_text_search_clause(where_clauses, params, keyword, columns, filters["mode"])
    if source:
        where_clauses.append("source = %s")
        params.append(source)
    if year:
        try:
            where_clauses.append("year = %s")
            params.append(int(year))
        except ValueError:
            pass
    if category:
        where_clauses.append("category = %s")
        params.append(category)
    if filters["year_from"]:
        add_int_filter(where_clauses, params, "year", filters["year_from"], ">=")
    if filters["year_to"]:
        add_int_filter(where_clauses, params, "year", filters["year_to"], "<=")
    if filters["dataset_name"]:
        where_clauses.append("dataset_name = %s")
        params.append(filters["dataset_name"])
    if filters["speaker"]:
        where_clauses.append("COALESCE(speaker, '') ILIKE %s")
        params.append(build_like_pattern(filters["speaker"]))
    if filters["title"]:
        where_clauses.append("COALESCE(title, '') ILIKE %s")
        params.append(build_like_pattern(filters["title"]))
    if filters["content_min"]:
        add_int_filter(where_clauses, params, "CHAR_LENGTH(content)", filters["content_min"], ">=")
    if filters["content_max"]:
        add_int_filter(where_clauses, params, "CHAR_LENGTH(content)", filters["content_max"], "<=")
    if filters["has_audio"] == "1":
        where_clauses.append("audio_file IS NOT NULL AND TRIM(audio_file) != ''")
    add_text_search_clause(
        where_clauses,
        params,
        filters["exclude"],
        SEARCH_FIELD_COLUMNS["all"],
        "contains",
        negate=True,
    )
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    return where_sql, params


def build_search_where(keyword="", source="", year="", category="", filters=None):
    filters = normalize_search_filters(filters)
    if is_postgres():
        return build_postgres_search_where(keyword, source, year, category, filters)
    where_clauses = []
    params = []
    if keyword:
        add_text_search_clause(
            where_clauses,
            params,
            keyword,
            SEARCH_FIELD_COLUMNS[filters["field"]],
            filters["mode"],
        )
    filter_clauses, filter_params = build_sqlite_filter_clauses(source, year, category, filters=filters)
    where_clauses.extend(filter_clauses)
    params.extend(filter_params)
    add_text_search_clause(
        where_clauses,
        params,
        filters["exclude"],
        SEARCH_FIELD_COLUMNS["all"],
        "contains",
        negate=True,
    )
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    return where_sql, params


def build_postgres_legacy_search_where(keyword="", source="", year="", category="", filters=None):
    where_clauses = []
    params = []
    filters = normalize_search_filters(filters)
    if keyword:
        add_text_search_clause(
            where_clauses,
            params,
            keyword,
            SEARCH_FIELD_COLUMNS[filters["field"]],
            filters["mode"],
        )
    if source:
        where_clauses.append("source = %s")
        params.append(source)
    if year:
        try:
            where_clauses.append("year = %s")
            params.append(int(year))
        except ValueError:
            pass
    if category:
        where_clauses.append("category = %s")
        params.append(category)
    if filters["year_from"]:
        add_int_filter(where_clauses, params, "year", filters["year_from"], ">=")
    if filters["year_to"]:
        add_int_filter(where_clauses, params, "year", filters["year_to"], "<=")
    if filters["dataset_name"]:
        where_clauses.append("dataset_name = %s")
        params.append(filters["dataset_name"])
    if filters["speaker"]:
        where_clauses.append("COALESCE(speaker, '') ILIKE %s")
        params.append(build_like_pattern(filters["speaker"]))
    if filters["title"]:
        where_clauses.append("COALESCE(title, '') ILIKE %s")
        params.append(build_like_pattern(filters["title"]))
    if filters["content_min"]:
        add_int_filter(where_clauses, params, "CHAR_LENGTH(content)", filters["content_min"], ">=")
    if filters["content_max"]:
        add_int_filter(where_clauses, params, "CHAR_LENGTH(content)", filters["content_max"], "<=")
    if filters["has_audio"] == "1":
        where_clauses.append("audio_file IS NOT NULL AND TRIM(audio_file) != ''")
    add_text_search_clause(
        where_clauses,
        params,
        filters["exclude"],
        SEARCH_FIELD_COLUMNS["all"],
        "contains",
        negate=True,
    )
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    return where_sql, params


def has_advanced_filters(filters=None):
    filters = normalize_search_filters(filters)
    defaults = normalize_search_filters()
    return any(filters[key] != defaults[key] for key in defaults)


def should_use_fts_match(keyword):
    compact = re.sub(r"\s+", "", keyword or "")
    return len(compact) >= 3


def escape_fts_keyword(value):
    return (value or "").replace('"', '""').strip()


def build_fts_match_query(keyword):
    safe_keyword = escape_fts_keyword(keyword)
    if not safe_keyword:
        return ""
    return f'"{safe_keyword}"'


def has_fts_table():
    if is_postgres():
        return False
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (FTS_TABLE,),
        ).fetchone()
        return row is not None
    finally:
        close_connection(conn)


def get_active_search_backend(configured_backend="fts"):
    if is_postgres():
        return "postgres"
    backend = configured_backend if configured_backend in {"like", "fts"} else "like"
    if backend == "fts" and has_fts_table():
        return "fts"
    return "like"


def count_search_results(keyword="", source="", year="", category="", filters=None):
    start = time.perf_counter()
    filters = normalize_search_filters(filters)
    where_sql, params = build_search_where(keyword, source, year, category, filters)
    conn = timed_connection("count_search_results")
    try:
        try:
            row = fetch_one_dict(conn.execute(f"SELECT COUNT(*) AS total FROM corpus_entries {where_sql}", params))
        except Exception as exc:
            if not is_missing_search_text_error(exc):
                raise
            conn.rollback()
            legacy_where_sql, legacy_params = build_postgres_legacy_search_where(keyword, source, year, category, filters)
            row = fetch_one_dict(conn.execute(f"SELECT COUNT(*) AS total FROM corpus_entries {legacy_where_sql}", legacy_params))
        return row["total"]
    finally:
        close_connection(conn)
        if is_postgres():
            timing_log("count_search_results.total", start, keyword_len=len(keyword or ""), has_filter=bool(source or year or category))


def count_search_results_fts(keyword="", source="", year="", category="", filters=None):
    filters = normalize_search_filters(filters)
    if is_postgres() or has_advanced_filters(filters) or not should_use_fts_match(keyword):
        return count_search_results(keyword, source, year, category, filters)
    match_query = build_fts_match_query(keyword)
    if not match_query:
        return count_search_results(keyword, source, year, category, filters)
    filter_clauses, filter_params = build_sqlite_filter_clauses(source, year, category, "corpus_entries", filters)
    where_clauses = [f"{FTS_TABLE} MATCH ?"]
    where_clauses.extend(filter_clauses)
    params = [match_query, *filter_params]
    where_sql = f"WHERE {' AND '.join(where_clauses)}"
    conn = get_db_connection()
    try:
        row = fetch_one_dict(conn.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM {FTS_TABLE}
            JOIN corpus_entries ON {FTS_TABLE}.rowid = corpus_entries.id
            {where_sql}
            """,
            params,
        ))
        return row["total"]
    finally:
        close_connection(conn)


def query_search_page(keyword="", source="", year="", category="", limit=50, offset=0, filters=None):
    start = time.perf_counter()
    filters = normalize_search_filters(filters)
    where_sql, params = build_search_where(keyword, source, year, category, filters)
    marker = placeholder()
    order_sql = SORT_OPTIONS[filters["sort"]]
    conn = timed_connection("query_search_page")
    try:
        try:
            rows = conn.execute(
                f"""
                SELECT *
                FROM corpus_entries
                {where_sql}
                ORDER BY {order_sql}
                LIMIT {marker} OFFSET {marker}
                """,
                [*params, limit, offset],
            ).fetchall()
        except Exception as exc:
            if not is_missing_search_text_error(exc):
                raise
            conn.rollback()
            legacy_where_sql, legacy_params = build_postgres_legacy_search_where(keyword, source, year, category, filters)
            rows = conn.execute(
                f"""
                SELECT *
                FROM corpus_entries
                {legacy_where_sql}
                ORDER BY {order_sql}
                LIMIT {marker} OFFSET {marker}
                """,
                [*legacy_params, limit, offset],
            ).fetchall()
        return [row_to_dict(row) for row in rows]
    finally:
        close_connection(conn)
        if is_postgres():
            timing_log("query_search_page.total", start, keyword_len=len(keyword or ""), limit=limit, offset=offset)


def query_search_page_fts(keyword="", source="", year="", category="", limit=50, offset=0, filters=None):
    filters = normalize_search_filters(filters)
    if is_postgres() or has_advanced_filters(filters) or not should_use_fts_match(keyword):
        return query_search_page(keyword, source, year, category, limit=limit, offset=offset, filters=filters)
    match_query = build_fts_match_query(keyword)
    if not match_query:
        return query_search_page(keyword, source, year, category, limit=limit, offset=offset, filters=filters)
    filter_clauses, filter_params = build_sqlite_filter_clauses(source, year, category, "corpus_entries", filters)
    where_clauses = [f"{FTS_TABLE} MATCH ?"]
    where_clauses.extend(filter_clauses)
    params = [match_query, *filter_params, limit, offset]
    where_sql = f"WHERE {' AND '.join(where_clauses)}"
    conn = get_db_connection()
    try:
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
        return [row_to_dict(row) for row in rows]
    finally:
        close_connection(conn)


def get_resonance_presets():
    return [
        {"key": key, **value}
        for key, value in RESONANCE_PRESETS.items()
    ]


def normalize_resonance_preset(preset):
    preset = RESONANCE_PRESET_ALIASES.get(preset, preset)
    return preset if preset in RESONANCE_PRESETS else "resonance"


def contains_any(text, markers):
    return any(marker in (text or "") for marker in markers)


def extract_resonance_tokens(text, max_tokens=24):
    text = normalize_turn_text(text)
    raw_tokens = re.findall(r"[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,6}", text)
    candidates = []
    for token in raw_tokens:
        if token in TOKEN_STOPWORDS:
            continue
        if len(token) < 2:
            continue
        candidates.append(token)

    # Short Chinese lines often have no whitespace; add compact bigrams so that
    # cross-turn echoes like “下次见 / 有缘再见” are still discoverable.
    chinese_text = "".join(re.findall(r"[\u4e00-\u9fff]+", text))
    for index in range(0, max(0, len(chinese_text) - 1)):
        token = chinese_text[index:index + 2]
        if token[0] in TOKEN_STOP_CHARS or token[-1] in TOKEN_STOP_CHARS:
            continue
        if token not in TOKEN_STOPWORDS:
            candidates.append(token)

    seen = set()
    tokens = []
    for token in candidates:
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
        if len(tokens) >= max_tokens:
            break
    return tokens


def trim_common_phrase(phrase):
    phrase = (phrase or "").strip()
    punctuation = " \t\r\n，。！？、；：,.!?;:\"'（）()【】[]《》<>"
    phrase = phrase.strip(punctuation)
    while len(phrase) > COMMON_PHRASE_MIN_CHARS and phrase[0] in TOKEN_STOP_CHARS:
        phrase = phrase[1:]
    while len(phrase) > COMMON_PHRASE_MIN_CHARS and phrase[-1] in TOKEN_STOP_CHARS:
        phrase = phrase[:-1]
    return phrase


def is_substantive_common_phrase(phrase):
    phrase = trim_common_phrase(phrase)
    if len(phrase) < COMMON_PHRASE_MIN_CHARS:
        return False
    if phrase in TOKEN_STOPWORDS:
        return False
    if all(char in TOKEN_STOP_CHARS for char in phrase):
        return False
    return True


def longest_common_phrases(text_a, text_b, max_phrases=5):
    text_a = normalize_turn_text(text_a)
    text_b = normalize_turn_text(text_b)
    if not text_a or not text_b:
        return []

    previous = [0] * (len(text_b) + 1)
    best_length = 0
    candidates = []
    for index_a, char_a in enumerate(text_a, 1):
        current = [0] * (len(text_b) + 1)
        if char_a.isspace():
            previous = current
            continue
        for index_b, char_b in enumerate(text_b, 1):
            if char_a != char_b or char_b.isspace():
                continue
            length = previous[index_b - 1] + 1
            current[index_b] = length
            if length < COMMON_PHRASE_MIN_CHARS:
                continue
            phrase = trim_common_phrase(text_a[index_a - length:index_a])
            if not is_substantive_common_phrase(phrase):
                continue
            if len(phrase) > best_length:
                best_length = len(phrase)
                candidates = [phrase]
            elif len(phrase) == best_length:
                candidates.append(phrase)
        previous = current

    result = []
    for phrase in candidates:
        if phrase in result:
            continue
        result.append(phrase)
        if len(result) >= max_phrases:
            break
    return result


def merge_common_terms(*term_groups, max_terms=24):
    terms = []
    for group in term_groups:
        for term in group:
            term = trim_common_phrase(term)
            if not is_substantive_common_phrase(term):
                continue
            if any(term == existing or term in existing for existing in terms):
                continue
            terms = [existing for existing in terms if existing not in term]
            terms.append(term)
            if len(terms) >= max_terms:
                return terms
    return terms


def shared_resonance_tokens(text_a, text_b):
    exact_phrases = longest_common_phrases(text_a, text_b)
    tokens_a = extract_resonance_tokens(text_a)
    tokens_b = set(extract_resonance_tokens(text_b))
    shared_tokens = [token for token in tokens_a if token in tokens_b]
    return merge_common_terms(exact_phrases, shared_tokens)



def matched_function_patterns(text_a, text_b):
    matches = []
    for label, pattern in FUNCTION_PATTERNS:
        if pattern.search(text_a or "") and pattern.search(text_b or ""):
            matches.append(label)
    if "为什么" in (text_a or "") and "因为" in (text_b or ""):
        matches.append("为什么...因为")
    return list(dict.fromkeys(matches))


def explain_resonance_pair(preset, text_a, text_b):
    if preset == "resonance":
        for inner_preset in ("lexical_echo", "pattern_reuse", "qa_response", "repair_revision"):
            result = explain_resonance_pair(inner_preset, text_a, text_b)
            if result:
                return result
        return None

    if preset == "reproduction":
        return explain_resonance_pair("lexical_echo", text_a, text_b)

    if preset == "parallel":
        return explain_resonance_pair("pattern_reuse", text_a, text_b)

    if preset == "selection":
        return explain_resonance_pair("repair_revision", text_a, text_b)

    if preset == "contrast":
        return explain_resonance_pair("contrast_response", text_a, text_b)

    if preset == "analogy":
        return None

    shared = shared_resonance_tokens(text_a, text_b)
    patterns = matched_function_patterns(text_a, text_b)

    if preset == "lexical_echo":
        if not shared:
            return None
        return {
            "terms": shared[:5],
            "explanation": "相邻话轮共享关键词：" + " / ".join(shared[:5]),
        }

    if preset == "pattern_reuse":
        if patterns:
            return {
                "terms": patterns[:4],
                "explanation": "相邻话轮复用句式框架：" + " / ".join(patterns[:4]),
            }
        if len(shared) >= 2:
            return {
                "terms": shared[:4],
                "explanation": "相邻话轮出现多处形式复现：" + " / ".join(shared[:4]),
            }
        return None

    if preset == "qa_response":
        if contains_any(text_a, QUESTION_MARKERS) and (contains_any(text_b, RESPONSE_MARKERS) or len(text_b or "") >= 8):
            terms = [marker for marker in QUESTION_MARKERS if marker in (text_a or "")][:3]
            if not terms:
                terms = ["问答相邻"]
            return {
                "terms": terms,
                "explanation": "前一话轮具有提问特征，后一话轮形成回应。",
            }
        return None

    if preset == "contrast_response":
        markers = [marker for marker in CONTRAST_MARKERS if marker in (text_b or "")]
        if markers:
            return {
                "terms": markers[:4],
                "explanation": "后一话轮使用否定或转折标记：" + " / ".join(markers[:4]),
            }
        return None

    if preset == "repair_revision":
        markers = [marker for marker in REVISION_MARKERS if marker in (text_b or "")]
        if shared and markers:
            terms = list(dict.fromkeys([*shared[:3], *markers[:3]]))
            return {
                "terms": terms,
                "explanation": "后一话轮复现前一话轮成分，并出现修正/补充标记。",
            }
        return None

    return None


def clamp_resonance_page_size(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 20
    return max(1, min(parsed, MAX_RESONANCE_PAGE_SIZE))


def clamp_resonance_candidate_limit(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_RESONANCE_CANDIDATE_LIMIT
    return max(1, min(parsed, MAX_RESONANCE_CANDIDATE_LIMIT))


def fetch_turn_neighbor(conn, conversation_key, turn_index):
    marker = placeholder()
    return fetch_one_dict(conn.execute(
        f"""
        SELECT id, entry_id, turn_index, speaker_label, turn_text,
               source, category, dataset_name, conversation_key
        FROM {TURN_TABLE}
        WHERE conversation_key = {marker}
          AND turn_index = {marker}
        LIMIT 1
        """,
        (conversation_key, turn_index),
    ))


def fetch_entry_for_resonance(conn, entry_id, include_content=False):
    marker = placeholder()
    content_column = ", content" if include_content else ""
    return fetch_one_dict(conn.execute(
        f"""
        SELECT id, title, year{content_column}, source_url, crawl_source, crawl_date,
               license_note, audio_file
        FROM corpus_entries
        WHERE id = {marker}
        LIMIT 1
        """,
        (entry_id,),
    ))


def build_resonance_pair(turn_a, turn_b, entry):
    return {
        "turn_a_id": turn_a["id"],
        "entry_id": turn_a["entry_id"],
        "turn_a_index": turn_a["turn_index"],
        "speaker_a": turn_a.get("speaker_label") or "",
        "turn_a_text": turn_a["turn_text"],
        "turn_b_id": turn_b["id"],
        "turn_b_index": turn_b["turn_index"],
        "speaker_b": turn_b.get("speaker_label") or "",
        "turn_b_text": turn_b["turn_text"],
        "source": turn_a.get("source") or "",
        "category": turn_a.get("category") or "",
        "dataset_name": turn_a.get("dataset_name") or "",
        "conversation_key": turn_a["conversation_key"],
        "entry_title": (entry or {}).get("title") or "",
        "year": (entry or {}).get("year"),
        "content": (entry or {}).get("content") or "",
        "source_url": (entry or {}).get("source_url") or "",
        "crawl_source": (entry or {}).get("crawl_source") or "",
        "crawl_date": (entry or {}).get("crawl_date") or "",
        "license_note": (entry or {}).get("license_note") or "",
        "audio_file": (entry or {}).get("audio_file") or "",
    }


def compute_pair_resonance_features(text_a, text_b):
    preset_results = {
        preset: explain_resonance_pair(preset, text_a, text_b)
        for preset in PAIR_PRESET_FLAGS
    }
    shared_terms = shared_resonance_tokens(text_a, text_b)[:8]
    markers = []
    for result in preset_results.values():
        if result:
            markers.extend(result.get("terms") or [])
    markers = list(dict.fromkeys(markers))[:12]
    return {
        "shared_terms": shared_terms,
        "markers": markers,
        "has_lexical_echo": 1 if preset_results["lexical_echo"] else 0,
        "has_pattern_reuse": 1 if preset_results["pattern_reuse"] else 0,
        "has_question_response": 1 if preset_results["qa_response"] else 0,
        "has_negation_turn": 1 if preset_results["contrast_response"] else 0,
        "has_repair_repetition": 1 if preset_results["repair_revision"] else 0,
    }


def build_dialogue_pair_row(turn_a, turn_b):
    features = compute_pair_resonance_features(turn_a["turn_text"], turn_b["turn_text"])
    return (
        turn_a["id"],
        turn_b["id"],
        turn_a["entry_id"],
        turn_a["conversation_key"],
        turn_a["turn_index"],
        turn_b["turn_index"],
        turn_a.get("speaker_label") or "",
        turn_b.get("speaker_label") or "",
        turn_a["turn_text"],
        turn_b["turn_text"],
        turn_a.get("source") or "",
        turn_a.get("category") or "",
        turn_a.get("dataset_name") or "",
        json.dumps(features["shared_terms"], ensure_ascii=False),
        json.dumps(features["markers"], ensure_ascii=False),
        features["has_lexical_echo"],
        features["has_pattern_reuse"],
        features["has_question_response"],
        features["has_negation_turn"],
        features["has_repair_repetition"],
    )


def rebuild_dialogue_pairs(batch_size=5000, progress_callback=None):
    conn = get_db_connection()
    marker = placeholder()
    columns = (
        "turn_a_id", "turn_b_id", "entry_id", "conversation_key",
        "turn_index_a", "turn_index_b", "speaker_a", "speaker_b",
        "text_a", "text_b", "source", "category", "dataset_name",
        "shared_terms", "markers", "has_lexical_echo", "has_pattern_reuse",
        "has_question_response", "has_negation_turn", "has_repair_repetition",
    )
    insert_sql = (
        f"INSERT INTO {PAIR_TABLE} ({', '.join(columns)}) "
        f"VALUES ({', '.join(marker for _ in columns)})"
    )
    stats = {
        "turns": 0,
        "pairs": 0,
        "lexical_echo": 0,
        "pattern_reuse": 0,
        "question_response": 0,
        "negation_turn": 0,
        "repair_repetition": 0,
    }
    try:
        create_dialogue_pairs_schema(conn)
        if is_postgres():
            conn.execute(f"TRUNCATE TABLE {PAIR_TABLE} RESTART IDENTITY")
            conn.commit()
        else:
            conn.execute(f"DELETE FROM {PAIR_TABLE}")
        rows = conn.execute(
            f"""
            SELECT id, entry_id, turn_index, speaker_label, turn_text,
                   source, category, dataset_name, conversation_key
            FROM {TURN_TABLE}
            ORDER BY conversation_key, turn_index, id
            """
        ).fetchall()
        stats["turns"] = len(rows)
        previous = None
        batch = []
        total_rows = len(rows)
        if progress_callback:
            progress_callback({
                "phase": "start",
                "processed": 0,
                "total": total_rows,
                "pairs": stats["pairs"],
            })
        for index, row in enumerate(rows, start=1):
            current = row_to_dict(row)
            if (
                previous
                and previous["conversation_key"] == current["conversation_key"]
                and int(current["turn_index"]) == int(previous["turn_index"]) + 1
            ):
                pair_row = build_dialogue_pair_row(previous, current)
                batch.append(pair_row)
                stats["pairs"] += 1
                stats["lexical_echo"] += pair_row[15]
                stats["pattern_reuse"] += pair_row[16]
                stats["question_response"] += pair_row[17]
                stats["negation_turn"] += pair_row[18]
                stats["repair_repetition"] += pair_row[19]
                if len(batch) >= batch_size:
                    execute_many(conn, insert_sql, batch)
                    batch.clear()
                    if is_postgres():
                        conn.commit()
            previous = current
            if progress_callback and (index % batch_size == 0 or index == total_rows):
                progress_callback({
                    "phase": "processing",
                    "processed": index,
                    "total": total_rows,
                    "pairs": stats["pairs"],
                })
        if batch:
            execute_many(conn, insert_sql, batch)
            if is_postgres():
                conn.commit()
        set_corpus_stat(conn, "dialogue_pairs_count", stats["pairs"])
        for key in ("lexical_echo", "pattern_reuse", "question_response", "negation_turn", "repair_repetition"):
            set_corpus_stat(conn, f"dialogue_pairs_{key}_count", stats[key])
        conn.commit()
        if progress_callback:
            progress_callback({
                "phase": "done",
                "processed": total_rows,
                "total": total_rows,
                "pairs": stats["pairs"],
            })
        return stats
    except Exception:
        safe_rollback(conn)
        raise
    finally:
        close_connection(conn)


def query_candidate_turns(
    keyword="",
    source="",
    category="",
    candidate_limit=DEFAULT_RESONANCE_CANDIDATE_LIMIT,
    before_id=None,
):
    marker = placeholder()
    candidate_limit = clamp_resonance_candidate_limit(candidate_limit)
    where_clauses = []
    params = []
    try:
        before_id = int(before_id) if before_id not in (None, "") else None
    except (TypeError, ValueError):
        before_id = None
    if before_id:
        where_clauses.append(f"id < {marker}")
        params.append(before_id)
    if keyword:
        operator = "ILIKE" if is_postgres() else "LIKE"
        where_clauses.append(f"turn_text {operator} {marker} ESCAPE '\\'")
        params.append(build_like_pattern(keyword))
    if source:
        where_clauses.append(f"source = {marker}")
        params.append(source)
    if category:
        where_clauses.append(f"category = {marker}")
        params.append(category)
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT id, entry_id, turn_index, speaker_label, turn_text,
                   source, category, dataset_name, conversation_key
            FROM {TURN_TABLE}
            {where_sql}
            ORDER BY id DESC
            LIMIT {marker}
            """,
            [*params, candidate_limit],
        ).fetchall()
        return [row_to_dict(row) for row in rows]
    finally:
        close_connection(conn)


def query_adjacent_turn_pairs(
    keyword="",
    source="",
    category="",
    candidate_limit=DEFAULT_RESONANCE_CANDIDATE_LIMIT,
    before_id=None,
):
    candidates = query_candidate_turns(
        keyword=keyword,
        source=source,
        category=category,
        candidate_limit=candidate_limit,
        before_id=before_id,
    )
    if not candidates:
        return [], None, False

    conn = get_db_connection()
    seen = set()
    pairs = []
    last_candidate_id = None
    has_more_candidates = len(candidates) >= clamp_resonance_candidate_limit(candidate_limit)
    try:
        entry_cache = {}
        for candidate in candidates:
            last_candidate_id = candidate["id"]
            if keyword:
                next_turn = fetch_turn_neighbor(conn, candidate["conversation_key"], candidate["turn_index"] + 1)
                if next_turn:
                    pair_key = (candidate["id"], next_turn["id"])
                    if pair_key not in seen:
                        seen.add(pair_key)
                        entry = entry_cache.get(candidate["entry_id"])
                        if entry is None:
                            entry = fetch_entry_for_resonance(conn, candidate["entry_id"])
                            entry_cache[candidate["entry_id"]] = entry
                        pairs.append(build_resonance_pair(candidate, next_turn, entry))

                prev_turn = fetch_turn_neighbor(conn, candidate["conversation_key"], candidate["turn_index"] - 1)
                if prev_turn:
                    pair_key = (prev_turn["id"], candidate["id"])
                    if pair_key not in seen:
                        seen.add(pair_key)
                        entry = entry_cache.get(prev_turn["entry_id"])
                        if entry is None:
                            entry = fetch_entry_for_resonance(conn, prev_turn["entry_id"])
                            entry_cache[prev_turn["entry_id"]] = entry
                        pairs.append(build_resonance_pair(prev_turn, candidate, entry))
            else:
                next_turn = fetch_turn_neighbor(conn, candidate["conversation_key"], candidate["turn_index"] + 1)
                if not next_turn:
                    continue
                pair_key = (candidate["id"], next_turn["id"])
                if pair_key in seen:
                    continue
                seen.add(pair_key)
                entry = entry_cache.get(candidate["entry_id"])
                if entry is None:
                    entry = fetch_entry_for_resonance(conn, candidate["entry_id"])
                    entry_cache[candidate["entry_id"]] = entry
                pairs.append(build_resonance_pair(candidate, next_turn, entry))
        return pairs, last_candidate_id, has_more_candidates
    finally:
        close_connection(conn)


def query_resonance_page(
    preset="resonance",
    keyword="",
    source="",
    category="",
    limit=20,
    cursor=None,
    candidate_limit=DEFAULT_RESONANCE_CANDIDATE_LIMIT,
    include_turn_count=True,
):
    preset = normalize_resonance_preset(preset)
    limit = clamp_resonance_page_size(limit)
    try:
        cursor = int(cursor) if cursor not in (None, "") else None
    except (TypeError, ValueError):
        cursor = None
    mode_flags = DIALOGUE_SYNTAX_MODE_FLAGS.get(preset, ())
    if preset == "analogy" or not mode_flags:
        return {
            "results": [],
            "has_next": False,
            "next_cursor": None,
            "turn_count": 0,
            "missing_pairs": False,
            "unsupported_mode": True,
        }

    marker = placeholder()
    flag_clause = "(" + " OR ".join(f"{flag} = 1" for flag in mode_flags) + ")"
    where_clauses = [flag_clause]
    params = []
    if cursor:
        where_clauses.append(f"id < {marker}")
        params.append(cursor)
    if keyword:
        operator = "ILIKE" if is_postgres() else "LIKE"
        where_clauses.append(f"(text_a {operator} {marker} ESCAPE '\\' OR text_b {operator} {marker} ESCAPE '\\')")
        pattern = build_like_pattern(keyword)
        params.extend([pattern, pattern])
    if source:
        where_clauses.append(f"source = {marker}")
        params.append(source)
    if category:
        where_clauses.append(f"category = {marker}")
        params.append(category)
    where_sql = "WHERE " + " AND ".join(where_clauses)
    conn = get_readonly_db_connection()
    try:
        if not dialogue_pairs_has_rows(conn):
            return {"results": [], "has_next": False, "next_cursor": None, "turn_count": 0, "missing_pairs": True}
        fetch_limit = min(max(limit + 1, limit * 8 + 1), 200)
        rows = conn.execute(
            f"""
            SELECT id, turn_a_id, turn_b_id, entry_id, conversation_key,
                   turn_index_a, turn_index_b, speaker_a, speaker_b,
                   text_a, text_b, source, category, dataset_name,
                   shared_terms, markers
            FROM {PAIR_TABLE}
            {where_sql}
            ORDER BY id DESC
            LIMIT {marker}
            """,
            [*params, fetch_limit],
        ).fetchall()
        pair_rows = [row_to_dict(row) for row in rows]
        entry_cache = {}
        results = []
        last_scanned_id = None
        scanned_count = 0
        for pair in pair_rows:
            last_scanned_id = pair["id"]
            scanned_count += 1
            try:
                terms = json.loads(pair.get("shared_terms") or "[]")
            except (TypeError, ValueError):
                terms = []
            try:
                markers = json.loads(pair.get("markers") or "[]")
            except (TypeError, ValueError):
                markers = []
            terms = list(dict.fromkeys([*terms, *markers]))[:8]
            explanation = explain_resonance_pair(preset, pair["text_a"], pair["text_b"])
            if not explanation:
                continue
            entry = entry_cache.get(pair["entry_id"])
            if entry is None:
                entry = fetch_entry_for_resonance(conn, pair["entry_id"])
                entry_cache[pair["entry_id"]] = entry
            results.append({
                "pair_id": pair["id"],
                "turn_a_id": pair["turn_a_id"],
                "entry_id": pair["entry_id"],
                "turn_a_index": pair["turn_index_a"],
                "speaker_a": pair.get("speaker_a") or "",
                "turn_a_text": pair["text_a"],
                "turn_b_id": pair["turn_b_id"],
                "turn_b_index": pair["turn_index_b"],
                "speaker_b": pair.get("speaker_b") or "",
                "turn_b_text": pair["text_b"],
                "source": pair.get("source") or "",
                "category": pair.get("category") or "",
                "dataset_name": pair.get("dataset_name") or "",
                "conversation_key": pair["conversation_key"],
                "entry_title": (entry or {}).get("title") or "",
                "year": (entry or {}).get("year"),
                "content": "",
                "source_url": (entry or {}).get("source_url") or "",
                "crawl_source": (entry or {}).get("crawl_source") or "",
                "crawl_date": (entry or {}).get("crawl_date") or "",
                "license_note": (entry or {}).get("license_note") or "",
                "audio_file": (entry or {}).get("audio_file") or "",
                "terms": explanation.get("terms") or terms,
                "explanation": explanation.get("explanation") or RESONANCE_PRESETS[preset]["label"],
                "preset": preset,
                "preset_label": RESONANCE_PRESETS[preset]["label"],
            })
            if len(results) >= limit:
                break
    finally:
        close_connection(conn)

    has_next = len(pair_rows) > scanned_count or (len(pair_rows) == fetch_limit and last_scanned_id is not None)
    return {
        "results": results,
        "has_next": has_next,
        "next_cursor": last_scanned_id if has_next else None,
        "turn_count": count_dialogue_turns() if include_turn_count else 0,
        "missing_pairs": False,
    }


def get_dialogue_pair_by_id(pair_id):
    if not has_dialogue_pairs_table():
        return None
    marker = placeholder()
    conn = get_readonly_db_connection()
    try:
        return fetch_one_dict(conn.execute(
            f"""
            SELECT id, turn_a_id, turn_b_id, entry_id, conversation_key,
                   turn_index_a, turn_index_b, speaker_a, speaker_b,
                   text_a, text_b, source, category, dataset_name,
                   shared_terms, markers
            FROM {PAIR_TABLE}
            WHERE id = {marker}
            LIMIT 1
            """,
            (pair_id,),
        ))
    finally:
        close_connection(conn)


def get_diagraph_turns(pair_id, window_mode="pair"):
    pair = get_dialogue_pair_by_id(pair_id)
    if not pair:
        return None, []

    marker = placeholder()
    conn = get_readonly_db_connection()
    try:
        turns = fetch_all_dicts(conn.execute(
            f"""
            SELECT id, entry_id, turn_index, speaker_label, turn_text,
                   source, category, dataset_name, conversation_key
            FROM {TURN_TABLE}
            WHERE conversation_key = {marker}
            ORDER BY turn_index, id
            """,
            (pair["conversation_key"],),
        ))
    finally:
        close_connection(conn)

    if not turns:
        return pair, []

    start_index = int(pair["turn_index_a"])
    end_index = int(pair["turn_index_b"])
    mode = (window_mode or "pair").strip().lower()
    if mode == "context2":
        lower = start_index - 2
        upper = end_index + 2
        filtered = [turn for turn in turns if lower <= int(turn["turn_index"]) <= upper]
    elif mode == "context5":
        lower = start_index - 5
        upper = end_index + 5
        filtered = [turn for turn in turns if lower <= int(turn["turn_index"]) <= upper]
    elif mode == "full":
        filtered = turns
    else:
        filtered = [
            turn for turn in turns
            if int(turn["turn_index"]) in {start_index, end_index}
        ]
    return pair, filtered


def get_resonance_entry_context(entry_id, max_chars=RESONANCE_CONTEXT_CHARS):
    marker = placeholder()
    try:
        max_chars = max(200, min(int(max_chars), RESONANCE_CONTEXT_CHARS))
    except (TypeError, ValueError):
        max_chars = RESONANCE_CONTEXT_CHARS
    conn = get_readonly_db_connection()
    try:
        row = fetch_one_dict(conn.execute(
            f"""
            SELECT id, title, content, source_url
            FROM corpus_entries
            WHERE id = {marker}
            LIMIT 1
            """,
            (entry_id,),
        ))
    finally:
        close_connection(conn)
    if not row:
        return None
    content = row.get("content") or ""
    truncated = len(content) > max_chars
    if truncated:
        content = content[:max_chars] + "..."
    return {
        "id": row.get("id"),
        "title": row.get("title") or "",
        "content": content,
        "source_url": row.get("source_url") or "",
        "truncated": truncated,
    }


def has_extended_schema(conn):
    if is_postgres():
        return True
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(corpus_entries)").fetchall()}
    return {"dataset_name", "created_at", "import_batch", "content_hash"}.issubset(columns)


def insert_entry(title, content, source, year, category):
    conn = get_db_connection()
    try:
        if is_postgres():
            conn.execute(
                """
                INSERT INTO corpus_entries (
                    title, content, source, year, category,
                    dataset_name, created_at, import_batch, content_hash, search_text
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    title,
                    content,
                    source,
                    year,
                    category,
                    "admin_manual",
                    utc_timestamp(),
                    "admin_manual",
                    compute_content_hash(content),
                    build_search_text(title, content),
                ),
            )
        elif has_extended_schema(conn):
            conn.execute(
                f"""
                INSERT INTO corpus_entries (
                    title, content, source, year, category,
                    dataset_name, created_at, import_batch, content_hash
                )
                VALUES ({placeholder()}, {placeholder()}, {placeholder()}, {placeholder()}, {placeholder()},
                        {placeholder()}, {placeholder()}, {placeholder()}, {placeholder()})
                """,
                (
                    title,
                    content,
                    source,
                    year,
                    category,
                    category or source,
                    utc_timestamp(),
                    "admin_manual",
                    compute_content_hash(content),
                ),
            )
        else:
            conn.execute(
                "INSERT INTO corpus_entries (title, content, source, year, category) VALUES (?, ?, ?, ?, ?)",
                (title, content, source, year, category),
            )
        conn.commit()
    finally:
        close_connection(conn)


def insert_approved_text_submission(conn, submission):
    content = (submission["text_content"] or "").strip()
    if not content:
        raise ValueError("文本类投稿必须包含文本内容。")
    if is_postgres():
        conn.execute(
            """
            INSERT INTO corpus_entries (
                title, content, source, year, category,
                dataset_name, created_at, import_batch, content_hash, search_text
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                submission["title"],
                content,
                submission["source"] or submission["category"],
                None,
                submission["category"],
                "public_submission",
                utc_timestamp(),
                "public_submission",
                compute_content_hash(content),
                build_search_text(submission["title"], content),
            ),
        )
    elif has_extended_schema(conn):
        conn.execute(
            f"""
            INSERT INTO corpus_entries (
                title, content, source, year, category,
                dataset_name, created_at, import_batch, content_hash
            )
            VALUES ({placeholder()}, {placeholder()}, {placeholder()}, {placeholder()}, {placeholder()},
                    {placeholder()}, {placeholder()}, {placeholder()}, {placeholder()})
            """,
            (
                submission["title"],
                content,
                submission["source"] or submission["category"],
                None,
                submission["category"],
                submission["category"] or submission["source"],
                utc_timestamp(),
                "public_submission",
                compute_content_hash(content),
            ),
        )
    else:
        conn.execute(
            "INSERT INTO corpus_entries (title, content, source, year, category) VALUES (?, ?, ?, ?, ?)",
            (
                submission["title"],
                content,
                submission["source"] or submission["category"],
                None,
                submission["category"],
            ),
        )


def insert_multimodal_entry(conn, submission):
    include_storage_metadata = has_storage_metadata_schema(conn, "multimodal_entries")
    conflict_sql = "ON CONFLICT (submission_id) DO NOTHING" if is_postgres() else "OR IGNORE"
    if include_storage_metadata and is_postgres():
        sql = """
            INSERT INTO multimodal_entries (
                submission_id, title, source, category, genre, language, modality,
                text_content, original_filename, stored_filename, file_path,
                file_mime_type, file_size, storage_backend, object_key, file_url, file_hash
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (submission_id) DO NOTHING
        """
    elif include_storage_metadata:
        sql = """
            INSERT OR IGNORE INTO multimodal_entries (
                submission_id, title, source, category, genre, language, modality,
                text_content, original_filename, stored_filename, file_path,
                file_mime_type, file_size, storage_backend, object_key, file_url, file_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    else:
        sql = """
            INSERT OR IGNORE INTO multimodal_entries (
                submission_id, title, source, category, genre, language, modality,
                text_content, original_filename, stored_filename, file_path,
                file_mime_type, file_size
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    values = [
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
    ]
    if include_storage_metadata:
        values.extend([
            submission.get("storage_backend") or "local",
            submission.get("object_key") or submission.get("stored_filename"),
            submission.get("file_url"),
            submission.get("file_hash"),
        ])
    conn.execute(sql, tuple(values))


insert_approved_multimodal_submission = insert_multimodal_entry


def create_submission(form_values, file_info=None):
    marker = placeholder()
    conn = get_db_connection()
    try:
        include_storage_metadata = has_storage_metadata_schema(conn, "corpus_submissions")
        if include_storage_metadata:
            columns = """
                submitter_name, submitter_email, title, source, category, genre,
                language, modality, text_content, original_filename, stored_filename,
                file_path, file_mime_type, file_size, storage_backend, object_key,
                file_url, file_hash, status
            """
            values_sql = f"""
                {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker},
                {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker},
                {marker}, {marker}, 'pending'
            """
            values = (
                form_values["submitter_name"],
                form_values["submitter_email"],
                form_values["title"],
                form_values["source"],
                form_values["category"],
                form_values["genre"],
                form_values["language"],
                form_values["modality"],
                form_values["text_content"],
                file_info["original_filename"] if file_info else None,
                file_info["stored_filename"] if file_info else None,
                file_info["file_path"] if file_info else None,
                file_info["file_mime_type"] if file_info else None,
                file_info["file_size"] if file_info else None,
                file_info.get("storage_backend", "local") if file_info else "local",
                file_info.get("object_key") if file_info else None,
                file_info.get("file_url") if file_info else None,
                file_info.get("file_hash") if file_info else None,
            )
        else:
            columns = """
                submitter_name, submitter_email, title, source, category, genre,
                language, modality, text_content, original_filename, stored_filename,
                file_path, file_mime_type, file_size, status
            """
            values_sql = f"""
                {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker},
                {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, 'pending'
            """
            values = (
                form_values["submitter_name"],
                form_values["submitter_email"],
                form_values["title"],
                form_values["source"],
                form_values["category"],
                form_values["genre"],
                form_values["language"],
                form_values["modality"],
                form_values["text_content"],
                file_info["original_filename"] if file_info else None,
                file_info["stored_filename"] if file_info else None,
                file_info["file_path"] if file_info else None,
                file_info["file_mime_type"] if file_info else None,
                file_info["file_size"] if file_info else None,
            )
        conn.execute(
            f"""
            INSERT INTO corpus_submissions ({columns})
            VALUES ({values_sql})
            """,
            values,
        )
        conn.commit()
    finally:
        close_connection(conn)


def list_submissions(status="pending"):
    marker = placeholder()
    conn = get_db_connection()
    try:
        if status == "all":
            rows = conn.execute("""
                SELECT *
                FROM corpus_submissions
                ORDER BY created_at DESC, id DESC
            """).fetchall()
        else:
            rows = conn.execute(
                f"""
                SELECT *
                FROM corpus_submissions
                WHERE status = {marker}
                ORDER BY created_at DESC, id DESC
                """,
                (status,),
            ).fetchall()
        return [row_to_dict(row) for row in rows]
    finally:
        close_connection(conn)


def get_submission_by_id(submission_id):
    conn = get_db_connection()
    try:
        row = conn.execute(
            f"SELECT * FROM corpus_submissions WHERE id = {placeholder()}",
            (submission_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        close_connection(conn)


def update_submission_text_content(submission_id, text_content):
    marker = placeholder()
    conn = get_db_connection()
    try:
        conn.execute(
            f"""
            UPDATE corpus_submissions
            SET text_content = {marker}
            WHERE id = {marker}
            """,
            (text_content, submission_id),
        )
        conn.commit()
    finally:
        close_connection(conn)


def approve_submission_record(submission_id, admin_note=""):
    marker = placeholder()
    conn = get_db_connection()
    submission = None
    try:
        submission = row_to_dict(conn.execute(
            f"SELECT * FROM corpus_submissions WHERE id = {marker}",
            (submission_id,),
        ).fetchone())
        if submission is None:
            return None, "missing"
        if submission["status"] == "approved":
            return submission, "already_approved"
        if submission["modality"] in {"text", "txt"} and not submission["stored_filename"]:
            insert_approved_text_submission(conn, submission)
        elif submission["modality"] in {"text", "txt"} and (submission["text_content"] or "").strip():
            insert_approved_text_submission(conn, submission)
        else:
            insert_multimodal_entry(conn, submission)
        conn.execute(
            f"""
            UPDATE corpus_submissions
            SET status = 'approved',
                admin_note = {marker},
                reviewed_at = CURRENT_TIMESTAMP,
                reviewed_by = {marker}
            WHERE id = {marker}
            """,
            (admin_note, "admin", submission_id),
        )
        conn.commit()
        return submission, "approved"
    except Exception:
        conn.rollback()
        raise
    finally:
        close_connection(conn)


def reject_submission_record(submission_id, admin_note=""):
    marker = placeholder()
    conn = get_db_connection()
    try:
        conn.execute(
            f"""
            UPDATE corpus_submissions
            SET status = 'rejected',
                admin_note = {marker},
                reviewed_at = CURRENT_TIMESTAMP,
                reviewed_by = {marker}
            WHERE id = {marker}
            """,
            (admin_note, "admin", submission_id),
        )
        conn.commit()
    finally:
        close_connection(conn)


def delete_submission_record(submission_id):
    marker = placeholder()
    conn = get_db_connection()
    try:
        submission = row_to_dict(conn.execute(
            f"SELECT * FROM corpus_submissions WHERE id = {marker}",
            (submission_id,),
        ).fetchone())
        if submission:
            conn.execute(f"DELETE FROM corpus_submissions WHERE id = {marker}", (submission_id,))
            conn.commit()
        return submission
    finally:
        close_connection(conn)
