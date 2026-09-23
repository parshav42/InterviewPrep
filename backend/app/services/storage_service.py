from pathlib import Path
from uuid import UUID, uuid4

import boto3

from app.core.config import get_settings


class PrivateStorage:
    """Private object storage with an S3-compatible adapter and local fallback."""

    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.storage_bucket
        self.client = None
        if settings.storage_endpoint and settings.storage_access_key and settings.storage_secret_key:
            self.client = boto3.client("s3", endpoint_url=settings.storage_endpoint, aws_access_key_id=settings.storage_access_key, aws_secret_access_key=settings.storage_secret_key, region_name="us-east-1")
        else:
            self.root = Path(settings.storage_local_root or ".private_uploads")
            self.root.mkdir(parents=True, exist_ok=True)

    def create_key(self, user_id: UUID, extension: str) -> str:
        return f"uploads/{user_id}/{uuid4()}{extension.lower()}"

    def put(self, key: str, content: bytes) -> None:
        if self.client:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=content)
            return
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    def get(self, key: str) -> bytes:
        if self.client:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        return (self.root / key).read_bytes()

    def delete(self, key: str) -> None:
        if self.client:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            return
        destination = self.root / key
        if destination.exists():
            destination.unlink()
