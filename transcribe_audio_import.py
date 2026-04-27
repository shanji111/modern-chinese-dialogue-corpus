from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
from pathlib import Path

from db_utils import utc_timestamp


DB_FILE = Path("corpus.db")
AUDIO_STORAGE_DIR = Path("static") / "audio_imports"


def clean_text(value: str | None) -> str:
    return (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def segment_hash(audio_file: str, start_time: float, end_time: float, text: str) -> str:
    raw = f"{audio_file}|{start_time:.3f}|{end_time:.3f}|{clean_text(text)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ensure_audio_schema(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(corpus_entries)").fetchall()}
    required = {
        "audio_file",
        "segment_text",
        "current_segment",
        "prev_segment",
        "next_segment",
        "start_time",
        "end_time",
        "speaker",
        "conversation_id",
        "segment_index",
    }
    missing = sorted(required - columns)
    if missing:
        raise RuntimeError(f"数据库缺少音频字段: {', '.join(missing)}。请先运行 migrate_audio_db.py。")


def store_audio_file(audio_path: Path, storage_dir: Path, copy_audio: bool = True) -> str:
    if not copy_audio:
        return audio_path.name
    storage_dir.mkdir(parents=True, exist_ok=True)
    target = storage_dir / audio_path.name
    if audio_path.resolve() != target.resolve():
        shutil.copy2(audio_path, target)
    return target.name


def as_dict(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return dict(value)


def transcribe_audio(client, audio_path: Path, model: str, language: str | None):
    with audio_path.open("rb") as audio_file:
        kwargs = {
            "model": model,
            "file": audio_file,
            "response_format": "verbose_json",
            "timestamp_granularities": ["segment"],
        }
        if language:
            kwargs["language"] = language
        transcript = client.audio.transcriptions.create(**kwargs)

    data = as_dict(transcript)
    return data.get("segments", [])


def insert_segments(
    conn: sqlite3.Connection,
    audio_file: str,
    audio_title: str,
    segments: list[dict],
    source: str,
    category: str,
    dataset_name: str,
    import_batch: str,
    speaker: str,
) -> tuple[int, int]:
    success = 0
    skipped = 0
    created_at = utc_timestamp()
    conversation_id = Path(audio_file).stem

    cleaned_segments = []
    for segment in segments:
        text = clean_text(segment.get("text"))
        start_time = float(segment.get("start", 0) or 0)
        end_time = float(segment.get("end", 0) or 0)
        if not text or end_time <= start_time:
            skipped += 1
            continue
        cleaned_segments.append(
            {
                "text": text,
                "start": start_time,
                "end": end_time,
            }
        )

    for index, segment in enumerate(cleaned_segments):
        prev_text = cleaned_segments[index - 1]["text"] if index > 0 else ""
        next_text = cleaned_segments[index + 1]["text"] if index + 1 < len(cleaned_segments) else ""
        text = segment["text"]
        content_hash = segment_hash(audio_file, segment["start"], segment["end"], text)

        duplicate = conn.execute(
            "SELECT id FROM corpus_entries WHERE content_hash = ? LIMIT 1",
            (content_hash,),
        ).fetchone()
        if duplicate:
            skipped += 1
            continue

        conn.execute(
            """
            INSERT INTO corpus_entries (
                title, content, source, year, category,
                dataset_name, created_at, import_batch, content_hash,
                audio_file, segment_text, current_segment, prev_segment, next_segment,
                start_time, end_time, speaker, conversation_id, segment_index
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{audio_title} 片段 {index + 1}",
                text,
                source,
                None,
                category,
                dataset_name,
                created_at,
                import_batch,
                content_hash,
                audio_file,
                text,
                text,
                prev_text,
                next_text,
                segment["start"],
                segment["end"],
                speaker,
                conversation_id,
                index + 1,
            ),
        )
        success += 1

    return success, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe static audio files and import segments into SQLite.")
    parser.add_argument("audio_files", nargs="+", type=Path, help="要转写的音频文件路径")
    parser.add_argument("--db", type=Path, default=DB_FILE, help="SQLite 数据库路径")
    parser.add_argument("--batch", required=True, help="导入批次名，例如 audio_demo_20260416")
    parser.add_argument("--model", default="whisper-1", help="转写模型，默认 whisper-1")
    parser.add_argument("--language", default="zh", help="音频语言，中文建议 zh；留空可自动检测")
    parser.add_argument("--source", default="多模态语料", help="前台来源分类")
    parser.add_argument("--category", default="音频转写", help="细分类")
    parser.add_argument("--dataset-name", default="local-audio-demo", help="数据集名称")
    parser.add_argument("--speaker", default="", help="预留说话人字段")
    parser.add_argument("--audio-dir", type=Path, default=AUDIO_STORAGE_DIR, help="用于前台播放的音频存放目录")
    parser.add_argument("--no-copy-audio", action="store_true", help="只记录文件名，不复制音频到 static/audio_imports")
    args = parser.parse_args()

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("缺少 openai 依赖，请先运行: pip install -r requirements.txt") from exc

    client = OpenAI()
    conn = sqlite3.connect(args.db)
    try:
        ensure_audio_schema(conn)
        total_success = 0
        total_skipped = 0

        for audio_path in args.audio_files:
            if not audio_path.exists():
                raise FileNotFoundError(f"找不到音频文件: {audio_path}")

            stored_audio_name = store_audio_file(audio_path, args.audio_dir, not args.no_copy_audio)
            segments = transcribe_audio(
                client=client,
                audio_path=audio_path,
                model=args.model,
                language=args.language.strip() or None,
            )
            success, skipped = insert_segments(
                conn=conn,
                audio_file=stored_audio_name,
                audio_title=audio_path.stem,
                segments=segments,
                source=args.source,
                category=args.category,
                dataset_name=args.dataset_name,
                import_batch=args.batch,
                speaker=args.speaker,
            )
            total_success += success
            total_skipped += skipped
            print(f"- {audio_path}: 导入 {success} 条，跳过 {skipped} 条")

        conn.commit()
        print("音频转写导入完成")
        print(f"成功导入 {total_success} 条")
        print(f"跳过 {total_skipped} 条")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
