import os
import traceback


TARGET_NAMES = ("demo1", "demo2")
ROUTES = (
    "/audio/demo1.m4a",
    "/audio/demo2.m4a",
    "/corpus/audio/demo1.m4a",
    "/corpus/audio/demo2.m4a",
)
FIELD_CANDIDATES = (
    "id",
    "title",
    "audio_file",
    "audio_url",
    "audio_path",
    "file_path",
    "source_url",
    "media_url",
    "filename",
    "dataset_name",
    "conversation_id",
    "start_time",
    "end_time",
)


def print_heading(title):
    print()
    print(title)
    print("=" * len(title))


def env_value(name, default=""):
    return os.environ.get(name, default).strip()


def print_environment():
    print_heading("Environment")
    print(f"STORAGE_BACKEND={env_value('STORAGE_BACKEND', 'local') or 'local'}")
    print(f"S3_BUCKET={env_value('S3_BUCKET') or '(missing)'}")
    print(f"S3_REGION={env_value('S3_REGION', 'auto') or 'auto'}")
    print(f"CORPUS_AUDIO_OBJECT_PREFIX={env_value('CORPUS_AUDIO_OBJECT_PREFIX', 'corpus/audio').strip('/') or '(empty)'}")
    print(f"S3_ENDPOINT_URL present={'yes' if env_value('S3_ENDPOINT_URL') else 'NO'}")
    print(f"S3_PUBLIC_BASE_URL present={'yes' if env_value('S3_PUBLIC_BASE_URL') else 'NO'}")


def get_existing_columns(conn, table_name):
    try:
        from database import DATABASE_BACKEND
    except Exception:
        DATABASE_BACKEND = "sqlite"

    if DATABASE_BACKEND == "postgres":
        rows = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
            """,
            (table_name,),
        ).fetchall()
        return {row["column_name"] if isinstance(row, dict) else row[0] for row in rows}

    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def marker():
    from database import DATABASE_BACKEND

    return "%s" if DATABASE_BACKEND == "postgres" else "?"


def fetch_demo_rows():
    from database import get_db_connection, row_to_dict

    conn = get_db_connection()
    try:
        columns = get_existing_columns(conn, "corpus_entries")
        selected = [field for field in FIELD_CANDIDATES if field in columns]
        if not selected:
            selected = ["id", "title"]

        all_rows = []
        m = marker()
        for name in TARGET_NAMES:
            where_parts = []
            params = []
            for field in ("audio_file", "title", "conversation_id", "dataset_name"):
                if field in columns:
                    where_parts.append(f"{field} LIKE {m}")
                    params.append(f"%{name}%")
            if not where_parts:
                continue
            rows = conn.execute(
                f"""
                SELECT {', '.join(selected)}
                FROM corpus_entries
                WHERE {' OR '.join(where_parts)}
                ORDER BY id
                LIMIT 8
                """,
                params,
            ).fetchall()
            all_rows.extend(row_to_dict(row) for row in rows)

        return selected, all_rows
    finally:
        conn.close()


def print_demo_rows():
    import app as app_module

    print_heading("Database demo1/demo2 rows")
    selected, rows = fetch_demo_rows()
    print(f"Selected fields: {', '.join(selected)}")
    if not rows:
        print("No rows found by audio_file/title/conversation_id/dataset_name containing demo1/demo2.")
        return

    with app_module.app.test_request_context("/"):
        for row in rows:
            print("-" * 48)
            for field in selected:
                print(f"{field}: {row.get(field)}")
            audio_file = row.get("audio_file") or ""
            generated_url = app_module.build_corpus_audio_url(audio_file)
            print(f"build_corpus_audio_url(audio_file): {generated_url!r}")
            print("template item.audioUrl would be:", generated_url or "(empty)")


def print_search_render_probe():
    import app as app_module

    print_heading("Search page rendered audioUrl probe")
    with app_module.app.test_client() as client:
        for keyword in TARGET_NAMES:
            try:
                response = client.get(f"/search?q={keyword}")
                text = response.get_data(as_text=True)
                print(f"/search?q={keyword}: status={response.status_code}, contains audioUrl={('audioUrl:' in text)}")
                for token in ("/audio/demo1.m4a", "/audio/demo2.m4a", "/corpus/audio/demo1.m4a", "/corpus/audio/demo2.m4a", "/audio/corpus/audio/demo1.m4a", "/audio/corpus/audio/demo2.m4a"):
                    if token in text:
                        print(f"  found token: {token}")
                if "audioUrl: \"\"" in text or "audioUrl: null" in text:
                    print("  found empty/null audioUrl marker")
            except Exception:
                print(f"/search?q={keyword}: ERROR")
                traceback.print_exc()


def print_route_probe():
    import app as app_module

    print_heading("Audio route Range probes")
    with app_module.app.test_client() as client:
        for route in ROUTES:
            try:
                response = client.get(route, headers={"Range": "bytes=0-99"})
                print(f"{route}: status={response.status_code}")
                print(f"  Content-Range: {response.headers.get('Content-Range')}")
                print(f"  Content-Type: {response.headers.get('Content-Type')}")
                print(f"  Location: {response.headers.get('Location')}")
                if response.status_code >= 500:
                    print(f"  Body preview: {response.get_data(as_text=True)[:500]}")
            except Exception:
                print(f"{route}: EXCEPTION")
                traceback.print_exc()


def print_key_normalization_probe():
    from storage_utils import normalize_corpus_audio_object_key

    print_heading("Object key normalization")
    for value in ("demo1.m4a", "demo2.m4a", "corpus/audio/demo1.m4a", "corpus/audio/demo2.m4a", "/corpus/audio/demo1.m4a"):
        try:
            print(f"{value!r} -> {normalize_corpus_audio_object_key(value)!r}")
        except Exception:
            print(f"{value!r} -> ERROR")
            traceback.print_exc()


def main():
    print_environment()
    print_key_normalization_probe()
    print_demo_rows()
    print_search_render_probe()
    print_route_probe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
