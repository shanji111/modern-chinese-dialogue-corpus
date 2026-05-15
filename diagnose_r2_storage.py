import os
from itertools import islice


PREFIXES = (
    "submissions/pending/",
    "corpus/audio/",
    "submissions/",
    "uploads/",
    "static/audio_imports/",
)

REQUIRED_ENV = (
    "S3_ENDPOINT_URL",
    "S3_BUCKET",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
)


def env_value(name, default=""):
    return os.environ.get(name, default).strip()


def mask_secret(value):
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return f"{value[:2]}***{value[-2:]}"
    return f"{value[:4]}***{value[-4:]}"


def mask_endpoint(value):
    if not value:
        return "(missing)"
    value = value.rstrip("/")
    if "://" not in value:
        return mask_secret(value)
    scheme, rest = value.split("://", 1)
    host = rest.split("/", 1)[0]
    parts = host.split(".")
    if len(parts) >= 3:
        parts[0] = mask_secret(parts[0])
        masked_host = ".".join(parts)
    else:
        masked_host = mask_secret(host)
    return f"{scheme}://{masked_host}"


def looks_like_r2_api_endpoint(value):
    lowered = (value or "").strip().lower()
    return lowered.startswith("https://") and lowered.endswith(".r2.cloudflarestorage.com")


def looks_like_public_base_url(value):
    lowered = (value or "").strip().lower()
    return bool(lowered) and not lowered.endswith(".r2.cloudflarestorage.com")


def print_config():
    storage_backend = env_value("STORAGE_BACKEND", "local") or "local"
    endpoint = env_value("S3_ENDPOINT_URL")
    public_base_url = env_value("S3_PUBLIC_BASE_URL")
    print("R2/S3 storage diagnostics")
    print("=" * 32)
    print(f"STORAGE_BACKEND: {storage_backend}")
    print(f"STORAGE_BACKEND enables R2/S3 uploads: {'yes' if storage_backend == 's3' else 'NO - code will use local storage'}")
    print(f"S3_ENDPOINT_URL: {mask_endpoint(endpoint)}")
    print(f"S3_ENDPOINT_URL looks like Cloudflare R2 S3 API endpoint: {'yes' if looks_like_r2_api_endpoint(endpoint) else 'NO'}")
    print(f"S3_BUCKET: {env_value('S3_BUCKET') or '(missing)'}")
    print(f"S3_REGION: {env_value('S3_REGION', 'auto') or 'auto'}")
    print(f"S3_REGION is auto: {'yes' if (env_value('S3_REGION', 'auto') or 'auto') == 'auto' else 'NO'}")
    print(f"S3_PUBLIC_BASE_URL: {mask_endpoint(public_base_url) if public_base_url else '(empty)'}")
    print(f"S3_PUBLIC_BASE_URL is separate from S3 API endpoint: {'yes' if public_base_url and public_base_url != endpoint else 'check value'}")
    if looks_like_public_base_url(endpoint):
        print("WARNING: S3_ENDPOINT_URL does not look like an R2 S3 API endpoint. Do not put S3_PUBLIC_BASE_URL here.")
    print(f"S3_ACCESS_KEY_ID: {mask_secret(env_value('S3_ACCESS_KEY_ID'))}")
    print(f"S3_SECRET_ACCESS_KEY: {mask_secret(env_value('S3_SECRET_ACCESS_KEY'))}")
    print(f"S3_SECRET_ACCESS_KEY present: {'yes' if env_value('S3_SECRET_ACCESS_KEY') else 'NO'}")
    print(f"CORPUS_AUDIO_OBJECT_PREFIX: {env_value('CORPUS_AUDIO_OBJECT_PREFIX', 'corpus/audio').strip('/') or '(empty)'}")
    print()
    print("Note: this codebase reads S3_* variables. R2_* and AWS_* variables are not used by storage_utils.py.")
    print("Note: S3_PUBLIC_BASE_URL is only used for public redirects; it is not the boto3 S3 API endpoint.")
    print()


def missing_required_env():
    return [name for name in REQUIRED_ENV if not env_value(name)]


def make_client():
    import boto3

    region = env_value("S3_REGION", "auto") or "auto"
    print("boto3 client configuration:")
    print(f"  endpoint_url={mask_endpoint(env_value('S3_ENDPOINT_URL'))}")
    print(f"  aws_access_key_id={mask_secret(env_value('S3_ACCESS_KEY_ID'))}")
    print("  aws_secret_access_key=(masked)")
    print(f"  region_name={region}")
    print()
    return boto3.client(
        "s3",
        endpoint_url=env_value("S3_ENDPOINT_URL"),
        aws_access_key_id=env_value("S3_ACCESS_KEY_ID"),
        aws_secret_access_key=env_value("S3_SECRET_ACCESS_KEY"),
        region_name=region,
    )


def iter_objects(client, bucket, prefix=""):
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            yield item


def print_objects(client, bucket, prefix="", label=None, limit=20):
    title = label or prefix or "(bucket root)"
    print(f"Objects under {title}:")
    try:
        objects = list(islice(iter_objects(client, bucket, prefix), limit))
    except Exception as exc:
        print(f"  ERROR: failed to list objects: {type(exc).__name__}: {exc}")
        print()
        return

    if not objects:
        print("  (none found)")
        print()
        return

    for item in objects:
        size = item.get("Size", "")
        modified = item.get("LastModified", "")
        print(f"  {item.get('Key')}  size={size}  last_modified={modified}")
    print()


def check_list_objects(client, bucket):
    print("Checking list_objects_v2 permission:")
    try:
        response = client.list_objects_v2(Bucket=bucket, MaxKeys=1)
    except Exception as exc:
        print(f"  list_objects_v2: FAILED ({type(exc).__name__}: {exc})")
        print()
        return False
    key_count = response.get("KeyCount", 0)
    print(f"  list_objects_v2: OK (KeyCount={key_count})")
    print()
    return True


def print_prefix_count(client, bucket, prefix, preview_limit=20):
    count = 0
    preview = []
    try:
        for item in iter_objects(client, bucket, prefix):
            count += 1
            if len(preview) < preview_limit:
                preview.append(item)
    except Exception as exc:
        print(f"Prefix {prefix}: ERROR: failed to list objects: {type(exc).__name__}: {exc}")
        print()
        return

    print(f"Prefix {prefix}: count={count}")
    if not preview:
        print("  (none found)")
    else:
        for item in preview:
            size = item.get("Size", "")
            modified = item.get("LastModified", "")
            print(f"  {item.get('Key')}  size={size}  last_modified={modified}")
    print()


def main():
    print_config()
    missing = missing_required_env()
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        print("Set these in the current shell or Render environment before running bucket diagnostics.")
        return 2

    try:
        client = make_client()
    except ImportError:
        print("Missing Python dependency: boto3. Install requirements.txt before running this diagnostic.")
        return 2

    bucket = env_value("S3_BUCKET")
    check_list_objects(client, bucket)
    print_objects(client, bucket, label="bucket root", limit=20)
    for prefix in PREFIXES:
        print_prefix_count(client, bucket, prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
