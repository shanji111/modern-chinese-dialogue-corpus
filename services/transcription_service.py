import os
import shutil
import subprocess
import uuid
from pathlib import Path

from storage_utils import S3StorageBackend, UPLOAD_FOLDER


AUDIO_TRANSCRIPTION_EXTENSIONS = {".mp3", ".wav", ".m4a"}
VIDEO_TRANSCRIPTION_EXTENSIONS = {".mp4", ".mov"}


def get_file_extension(*names):
    for name in names:
        extension = Path(name or "").suffix.lower()
        if extension:
            return extension
    return ""


def is_transcribable_submission(submission):
    if not submission or not submission.get("original_filename"):
        return False
    extension = get_file_extension(submission.get("original_filename"), submission.get("stored_filename"), submission.get("object_key"))
    mime_type = (submission.get("file_mime_type") or "").lower()
    return (
        extension in AUDIO_TRANSCRIPTION_EXTENSIONS
        or extension in VIDEO_TRANSCRIPTION_EXTENSIONS
        or mime_type.startswith("audio/")
        or mime_type.startswith("video/")
    )


def is_video_submission_file(path, submission):
    extension = get_file_extension(path, submission.get("original_filename"))
    mime_type = (submission.get("file_mime_type") or "").lower()
    return extension in VIDEO_TRANSCRIPTION_EXTENSIONS or mime_type.startswith("video/")


def safe_upload_file_path(stored_filename):
    if not stored_filename:
        return None
    upload_root = UPLOAD_FOLDER.resolve()
    target = (UPLOAD_FOLDER / stored_filename).resolve()
    if upload_root not in target.parents and target != upload_root:
        return None
    return target


def local_submission_file_path(submission):
    target = safe_upload_file_path(submission.get("stored_filename") or submission.get("object_key"))
    if target and target.exists() and target.is_file():
        return target

    file_path = submission.get("file_path")
    if not file_path:
        return None
    upload_root = UPLOAD_FOLDER.resolve()
    target = Path(file_path).resolve()
    if upload_root not in target.parents and target != upload_root:
        return None
    if target.exists() and target.is_file():
        return target
    return None


def copy_submission_file_to_temp(submission, temp_dir):
    storage_backend = (submission.get("storage_backend") or "local").strip().lower()
    extension = get_file_extension(submission.get("original_filename"), submission.get("stored_filename"), submission.get("object_key")) or ".bin"
    temp_path = Path(temp_dir) / f"{uuid.uuid4().hex}{extension}"

    if storage_backend == "s3":
        object_key = submission.get("object_key") or submission.get("stored_filename")
        if not object_key:
            raise RuntimeError("未找到对象存储文件键，无法下载投稿文件。")
        try:
            backend = S3StorageBackend()
            backend.client().download_file(backend.bucket, object_key, str(temp_path))
        except Exception as exc:
            raise RuntimeError("无法从对象存储读取投稿文件，请检查 R2/S3 配置和文件是否存在。") from exc
        return temp_path

    local_path = local_submission_file_path(submission)
    if local_path is None:
        raise RuntimeError("未找到本地上传文件，无法继续处理。")
    shutil.copyfile(local_path, temp_path)
    return temp_path


def extract_audio_from_video(video_path, temp_dir):
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("该投稿是视频文件，需要先安装 ffmpeg 才能提取音频。")

    audio_path = Path(temp_dir) / f"{uuid.uuid4().hex}.m4a"
    try:
        subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-acodec",
                "aac",
                "-b:a",
                "96k",
                str(audio_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("ffmpeg 提取音频失败，请确认视频文件可播放且包含音轨。") from exc
    return audio_path


def transcribe_media_file(media_path, model_name):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("未配置转写 API Key，请先设置 OPENAI_API_KEY。")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("未安装 OpenAI Python SDK，请先安装 requirements.txt 中的依赖。") from exc

    client = OpenAI(api_key=api_key)
    with Path(media_path).open("rb") as media_file:
        result = client.audio.transcriptions.create(
            model=model_name,
            file=media_file,
            response_format="text",
        )
    return str(result or "").strip()


def cleanup_transcription_temp_files(paths):
    for path in paths:
        if not path:
            continue
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass


def transcribe_submission_media(submission, temp_dir, model_name):
    temp_paths = []
    try:
        media_path = copy_submission_file_to_temp(submission, temp_dir)
        temp_paths.append(media_path)
        transcription_path = media_path
        if is_video_submission_file(media_path, submission):
            transcription_path = extract_audio_from_video(media_path, temp_dir)
            temp_paths.append(transcription_path)
        return transcribe_media_file(transcription_path, model_name)
    finally:
        cleanup_transcription_temp_files(temp_paths)
