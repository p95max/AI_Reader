from functools import lru_cache
from pathlib import Path
from typing import Protocol

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings


class ObjectStorageError(RuntimeError):
    """Raised when an S3-compatible storage operation fails."""


class ObjectStorage(Protocol):
    def upload_file(self, source: Path, key: str, content_type: str) -> None: ...

    def upload_bytes(self, content: bytes, key: str, content_type: str) -> None: ...

    def download_file(self, key: str, destination: Path) -> None: ...

    def download_bytes(self, key: str) -> bytes: ...

    def delete_file(self, key: str) -> None: ...

    def delete_prefix(self, prefix: str) -> None: ...


class S3Storage:
    def __init__(self, client: BaseClient | None = None) -> None:
        settings = get_settings()
        self.bucket_name = settings.s3_bucket_name
        self.client = client or boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region_name,
            config=Config(signature_version="s3v4"),
        )

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "")
            if code not in {"404", "NoSuchBucket", "NotFound"}:
                raise ObjectStorageError("Unable to access the upload bucket") from error
            try:
                self.client.create_bucket(Bucket=self.bucket_name)
            except (ClientError, BotoCoreError) as create_error:
                raise ObjectStorageError("Unable to create the upload bucket") from create_error

    def upload_file(self, source: Path, key: str, content_type: str) -> None:
        try:
            self.ensure_bucket()
            self.client.upload_file(
                str(source),
                self.bucket_name,
                key,
                ExtraArgs={"ContentType": content_type},
            )
        except (ClientError, BotoCoreError) as error:
            raise ObjectStorageError("Unable to store the uploaded PDF") from error

    def upload_bytes(self, content: bytes, key: str, content_type: str) -> None:
        try:
            self.ensure_bucket()
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        except (ClientError, BotoCoreError) as error:
            raise ObjectStorageError("Unable to store generated audio") from error

    def delete_file(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
        except (ClientError, BotoCoreError) as error:
            raise ObjectStorageError("Unable to delete the stored file") from error

    def delete_prefix(self, prefix: str) -> None:
        """Remove every object for one deleted book, including untracked leftovers."""
        try:
            continuation_token: str | None = None
            while True:
                request: dict[str, str] = {"Bucket": self.bucket_name, "Prefix": prefix}
                if continuation_token is not None:
                    request["ContinuationToken"] = continuation_token
                response = self.client.list_objects_v2(**request)
                objects = [{"Key": item["Key"]} for item in response.get("Contents", [])]
                if objects:
                    self.client.delete_objects(
                        Bucket=self.bucket_name,
                        Delete={"Objects": objects, "Quiet": True},
                    )
                if not response.get("IsTruncated"):
                    return
                continuation_token = response.get("NextContinuationToken")
                if not continuation_token:
                    return
        except (ClientError, BotoCoreError) as error:
            raise ObjectStorageError("Unable to remove stored book data") from error

    def download_file(self, key: str, destination: Path) -> None:
        try:
            self.client.download_file(self.bucket_name, key, str(destination))
        except (ClientError, BotoCoreError) as error:
            raise ObjectStorageError("Unable to download the stored PDF") from error

    def download_bytes(self, key: str) -> bytes:
        """Return one stored audio segment for the authenticated player route."""
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read()
        except (ClientError, BotoCoreError) as error:
            raise ObjectStorageError("Unable to retrieve generated audio") from error


@lru_cache
def get_object_storage() -> ObjectStorage:
    return S3Storage()
