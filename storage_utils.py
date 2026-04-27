import hashlib
import os
import uuid
from pathlib import Path

from flask import redirect, send_from_directory
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local").strip().lower() or "local"
UPLOAD_FOLDER = Path(os.environ.get("UPLOAD_FOLDER", BASE_DIR / "uploads" / "submissions"))
if not UPLOAD_FOLDER.is_absolute():
    UPLOAD_FOLDER = BASE_DIR / UPLOAD_FOLDER

ALLOWED_SUBMISSION_EXTENSIONS = {".txt", ".mp3", ".wav", ".m4a", ".mp4", ".mov", ".json", ".csv"}


def extract_extension(filename):
    return Path(filename or "").suffix.lower()


def is_allowed_extension(extension):
    return extension.lower() in ALLOWED_SUBMISSION_EXTENSIONS


def normalized_secure_filename(filename, extension):
    secure_name = secure_filename(filename or "")
    secure_path = Path(secure_name)
    stem = secure_path.stem if secure_path.suffix else secure_path.name
    if not stem or stem.lower() == extension.lstrip("."):
        stem = "upload"
    return f"{stem}{extension}"


def upload_debug_info(file_storage):
    raw_filename = file_storage.filename if file_storage else ""
    secure_name = secure_filename(raw_filename or "")
    extension = extract_extension(raw_filename)
    return {
        "filename": raw_filename,
        "secure": secure_name,
        "ext": extension,
        "mimetype": getattr(file_storage, "mimetype", None),
        "allowed": sorted(ALLOWED_SUBMISSION_EXTENSIONS),
        "is_allowed": is_allowed_extension(extension),
    }


def print_upload_debug(file_storage, **details):
    info = upload_debug_info(file_storage)
    info.update(details)
    detail_text = " ".join(f"{key}={value}" for key, value in info.items())
    print(f"[UPLOAD DEBUG] {detail_text}", flush=True)


class LocalStorageBackend:
    def __init__(self, upload_folder=UPLOAD_FOLDER):
        self.upload_folder = Path(upload_folder)

    def ensure_ready(self):
        self.upload_folder.mkdir(parents=True, exist_ok=True)

    def allowed_file(self, filename):
        return is_allowed_extension(extract_extension(filename))

    def safe_submission_path(self, stored_filename):
        if not stored_filename:
            return None
        upload_root = self.upload_folder.resolve()
        target = (self.upload_folder / stored_filename).resolve()
        if upload_root not in target.parents and target != upload_root:
            return None
        return target

    def save_submission_file(self, file_storage):
        if not file_storage or not file_storage.filename:
            return None

        extension = extract_extension(file_storage.filename)
        if not is_allowed_extension(extension):
            print_upload_debug(file_storage)
            raise ValueError("该文件类型暂不支持上传。")

        original_filename = normalized_secure_filename(file_storage.filename, extension)
        stored_filename = f"{uuid.uuid4().hex}{extension}"
        self.ensure_ready()
        stored_path = self.upload_folder / stored_filename
        file_storage.save(stored_path)
        file_hash = sha256_file(stored_path)

        return {
            "original_filename": original_filename,
            "stored_filename": stored_filename,
            "file_path": str(stored_path.as_posix()),
            "file_mime_type": file_storage.mimetype,
            "file_size": stored_path.stat().st_size,
            "storage_backend": "local",
            "object_key": stored_filename,
            "file_url": None,
            "file_hash": file_hash,
            "extension": extension,
            "path": stored_path,
        }

    def get_submission_download_response(self, stored_filename, download_name=None):
        target = self.safe_submission_path(stored_filename)
        if target is None or not target.exists():
            raise FileNotFoundError(stored_filename or "")
        return send_from_directory(
            self.upload_folder,
            stored_filename,
            as_attachment=True,
            download_name=download_name or stored_filename,
        )

    def delete_submission_file(self, stored_filename):
        target = self.safe_submission_path(stored_filename)
        if target is None or not target.exists():
            return False
        try:
            target.unlink()
            return True
        except OSError:
            return False


class S3StorageBackend:
    def __init__(self):
        self.endpoint_url = os.environ.get("S3_ENDPOINT_URL", "").strip()
        self.bucket = os.environ.get("S3_BUCKET", "").strip()
        self.access_key_id = os.environ.get("S3_ACCESS_KEY_ID", "").strip()
        self.secret_access_key = os.environ.get("S3_SECRET_ACCESS_KEY", "").strip()
        self.public_base_url = os.environ.get("S3_PUBLIC_BASE_URL", "").strip().rstrip("/")
        self.region = os.environ.get("S3_REGION", "").strip() or "auto"

    def ensure_ready(self):
        missing = [
            name
            for name, value in {
                "S3_ENDPOINT_URL": self.endpoint_url,
                "S3_BUCKET": self.bucket,
                "S3_ACCESS_KEY_ID": self.access_key_id,
                "S3_SECRET_ACCESS_KEY": self.secret_access_key,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(f"STORAGE_BACKEND=s3 requires environment variables: {', '.join(missing)}")

    def client(self):
        self.ensure_ready()
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Install S3 dependency first: pip install -r requirements.txt") from exc
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region,
        )

    def allowed_file(self, filename):
        return is_allowed_extension(extract_extension(filename))

    def save_submission_file(self, file_storage):
        if not file_storage or not file_storage.filename:
            return None

        extension = extract_extension(file_storage.filename)
        if not is_allowed_extension(extension):
            print_upload_debug(file_storage)
            raise ValueError("该文件类型暂不支持上传。")

        original_filename = normalized_secure_filename(file_storage.filename, extension)
        object_key = f"submissions/pending/{uuid.uuid4().hex}{extension}"
        data = file_storage.read()
        file_hash = hashlib.sha256(data).hexdigest()
        content_type = file_storage.mimetype or "application/octet-stream"

        self.client().put_object(
            Bucket=self.bucket,
            Key=object_key,
            Body=data,
            ContentType=content_type,
        )
        file_url = f"{self.public_base_url}/{object_key}" if self.public_base_url else None
        result = {
            "original_filename": original_filename,
            "stored_filename": object_key,
            "file_path": None,
            "file_mime_type": content_type,
            "file_size": len(data),
            "storage_backend": "s3",
            "object_key": object_key,
            "file_url": file_url,
            "file_hash": file_hash,
            "extension": extension,
            "path": None,
        }
        if extension == ".txt":
            result["text_content"] = decode_text_bytes(data)
        return result

    def get_submission_download_response(self, stored_filename, download_name=None, object_key=None, file_url=None):
        key = object_key or stored_filename
        if not key:
            raise FileNotFoundError("")
        if file_url:
            return redirect(file_url)
        if self.public_base_url:
            return redirect(f"{self.public_base_url}/{key}")
        url = self.client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{download_name or Path(key).name}"',
            },
            ExpiresIn=3600,
        )
        return redirect(url)

    def delete_submission_file(self, stored_filename, object_key=None):
        key = object_key or stored_filename
        if not key:
            return False
        try:
            self.client().delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode_text_bytes(data):
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def get_storage_backend():
    if STORAGE_BACKEND == "local":
        return LocalStorageBackend(UPLOAD_FOLDER)
    if STORAGE_BACKEND == "s3":
        return S3StorageBackend()
    raise NotImplementedError(f"Unsupported STORAGE_BACKEND: {STORAGE_BACKEND}")


def allowed_file(filename):
    return get_storage_backend().allowed_file(filename)


def save_submission_file(file_storage):
    return get_storage_backend().save_submission_file(file_storage)


def get_submission_download_response(stored_filename, download_name=None, object_key=None, file_url=None, storage_backend=None):
    backend = S3StorageBackend() if storage_backend == "s3" else get_storage_backend()
    if isinstance(backend, S3StorageBackend):
        return backend.get_submission_download_response(stored_filename, download_name, object_key, file_url)
    return backend.get_submission_download_response(stored_filename, download_name)


def delete_submission_file(stored_filename, object_key=None, storage_backend=None):
    backend = S3StorageBackend() if storage_backend == "s3" else get_storage_backend()
    if isinstance(backend, S3StorageBackend):
        return backend.delete_submission_file(stored_filename, object_key)
    return backend.delete_submission_file(stored_filename)
