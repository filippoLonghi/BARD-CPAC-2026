from __future__ import annotations

from pathlib import Path


def upload_file_to_gcs(local_path: Path, bucket_name: str, blob_name: str) -> str:
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError("GCS upload requires `pip install -e .[cloud]`.") from exc

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    clean_blob_name = blob_name.strip("/")
    blob = bucket.blob(clean_blob_name)
    blob.upload_from_filename(str(local_path))
    return f"gs://{bucket_name}/{clean_blob_name}"


def upload_directory_to_gcs(local_dir: Path, bucket_name: str, prefix: str) -> str:
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError("GCS upload requires `pip install -e .[cloud]`.") from exc

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    clean_prefix = prefix.strip("/")

    for path in local_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(local_dir).as_posix()
        blob = bucket.blob(f"{clean_prefix}/{relative}")
        blob.upload_from_filename(str(path))

    return f"gs://{bucket_name}/{clean_prefix}"
