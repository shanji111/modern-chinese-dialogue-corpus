from __future__ import annotations

import argparse
import mimetypes
import os
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_AUDIO_DIRS = (
    BASE_DIR / "static" / "audio_imports",
    BASE_DIR / "talkdata" / "audio_raw",
)
DEFAULT_OBJECT_PREFIX = os.environ.get("CORPUS_AUDIO_OBJECT_PREFIX", "corpus/audio").strip().strip("/")


def get_s3_client():
    missing = [
        name
        for name in ("S3_ENDPOINT_URL", "S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    import boto3

    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("S3_REGION") or "auto",
    )


def find_audio_files(names):
    found = {}
    for name in names:
        safe_name = Path(name).name
        for audio_dir in DEFAULT_AUDIO_DIRS:
            candidate = audio_dir / safe_name
            if candidate.exists() and candidate.is_file():
                found[safe_name] = candidate
                break
    return found


def get_audio_names_from_sqlite(db_path):
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT audio_file
            FROM corpus_entries
            WHERE audio_file IS NOT NULL AND TRIM(audio_file) != ''
            """
        ).fetchall()
        return sorted({row[0] for row in rows})
    finally:
        conn.close()


def upload_files(files, prefix, dry_run):
    if not files:
        print("No local audio files found.")
        return

    client = None if dry_run else get_s3_client()
    bucket = os.environ.get("S3_BUCKET", "")
    uploaded = 0
    for name, path in files.items():
        key = f"{prefix}/{name}" if prefix else name
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if dry_run:
            print(f"DRY RUN upload {path} -> s3://{bucket}/{key} content_type={content_type}")
            continue
        with path.open("rb") as handle:
            client.put_object(Bucket=bucket, Key=key, Body=handle, ContentType=content_type)
        uploaded += 1
        print(f"Uploaded {path.name} -> {key}")
    print(f"Done. uploaded={uploaded} dry_run={dry_run}")


def main():
    parser = argparse.ArgumentParser(description="Upload legacy corpus audio files to S3/R2.")
    parser.add_argument("--db", default=str(BASE_DIR / "corpus.db"), help="SQLite database path for reading audio_file names.")
    parser.add_argument("--prefix", default=DEFAULT_OBJECT_PREFIX, help="Object key prefix, default: corpus/audio")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded without writing to S3/R2.")
    parser.add_argument("--names", nargs="*", help="Specific audio file names, e.g. demo1.m4a demo2.m4a")
    args = parser.parse_args()

    names = args.names or get_audio_names_from_sqlite(args.db)
    files = find_audio_files(names)
    missing = sorted(set(Path(name).name for name in names) - set(files))
    for name in missing:
        print(f"Missing local file: {name}")
    upload_files(files, args.prefix.strip().strip("/"), args.dry_run)


if __name__ == "__main__":
    main()
