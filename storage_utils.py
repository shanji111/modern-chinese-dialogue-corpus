"""
Legacy compatibility layer for storage and corpus-audio helpers.

Runtime code has been moved to:
- services.submission_storage_service
- services.audio_service

Keep this module as a stable import surface for older scripts while the
codebase transitions to the service-based layout.
"""

from pathlib import Path

from services.audio_service import (
    CORPUS_AUDIO_DIRS,
    CORPUS_AUDIO_OBJECT_PREFIX,
    STORAGE_BACKEND,
    corpus_audio_exists_locally,
    find_local_corpus_audio,
    get_corpus_audio_response,
    is_remote_url,
    normalize_corpus_audio_object_key,
    safe_child_path,
)
from services.submission_storage_service import (
    ALLOWED_SUBMISSION_EXTENSIONS,
    LocalStorageBackend,
    S3StorageBackend,
    UPLOAD_FOLDER,
    allowed_submission_file,
    build_submission_download_response,
    decode_text_bytes,
    delete_submission_upload,
    extract_extension,
    get_storage_backend,
    is_allowed_extension,
    normalized_secure_filename,
    print_upload_debug,
    save_submission_upload,
    sha256_file,
    upload_debug_info,
)


BASE_DIR = Path(__file__).resolve().parent


def allowed_file(filename):
    return allowed_submission_file(filename)


def save_submission_file(file_storage):
    return save_submission_upload(file_storage)


def get_submission_download_response(stored_filename, download_name=None, object_key=None, file_url=None, storage_backend=None):
    return build_submission_download_response(
        stored_filename,
        download_name,
        object_key=object_key,
        file_url=file_url,
        storage_backend=storage_backend,
    )


def delete_submission_file(stored_filename, object_key=None, storage_backend=None):
    return delete_submission_upload(
        stored_filename,
        object_key=object_key,
        storage_backend=storage_backend,
    )
