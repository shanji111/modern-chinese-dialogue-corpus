import os
from pathlib import Path

from flask import redirect, send_from_directory, url_for

from services.submission_storage_service import S3StorageBackend


BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local").strip().lower() or "local"
CORPUS_AUDIO_DIRS = (
    BASE_DIR / "static" / "audio_imports",
    BASE_DIR / "talkdata" / "audio_raw",
)
CORPUS_AUDIO_OBJECT_PREFIX = os.environ.get("CORPUS_AUDIO_OBJECT_PREFIX", "corpus/audio").strip().strip("/")


def safe_child_path(base_dir, filename):
    if not filename:
        return None
    base = Path(base_dir).resolve()
    target = (base / filename).resolve()
    if base not in target.parents and target != base:
        return None
    return target


def find_local_corpus_audio(filename):
    for audio_dir in CORPUS_AUDIO_DIRS:
        target = safe_child_path(audio_dir, filename)
        if target and target.exists() and target.is_file():
            return audio_dir, target
    return None, None


def normalize_corpus_audio_object_key(filename):
    filename = (filename or "").strip().replace("\\", "/").lstrip("/")
    if not filename:
        return ""
    if "/" in filename:
        return filename
    if CORPUS_AUDIO_OBJECT_PREFIX:
        return f"{CORPUS_AUDIO_OBJECT_PREFIX}/{filename}"
    return filename


def corpus_audio_exists_locally(filename):
    _, target = find_local_corpus_audio(filename)
    return target is not None


def is_remote_url(value):
    value = (value or "").strip().lower()
    return value.startswith("http://") or value.startswith("https://")


def get_corpus_audio_response(filename):
    if is_remote_url(filename):
        return redirect(filename)
    if STORAGE_BACKEND == "s3":
        key = normalize_corpus_audio_object_key(filename)
        return S3StorageBackend().get_object_redirect_response(key, download_name=Path(key).name)

    audio_dir, target = find_local_corpus_audio(filename)
    if target is None:
        raise FileNotFoundError(filename or "")
    return send_from_directory(audio_dir, target.name, as_attachment=False, conditional=True)


def build_corpus_audio_url(audio_file):
    audio_file = (audio_file or "").strip()
    if not audio_file:
        return ""
    if is_remote_url(audio_file):
        return audio_file
    if STORAGE_BACKEND == "local" and not corpus_audio_exists_locally(audio_file):
        return ""
    return url_for("audio_file", filename=audio_file)
