from pathlib import Path

from botocore.exceptions import ClientError

from app.services.storage import S3Storage


class FakeS3Client:
    def __init__(self) -> None:
        self.bucket_created = False
        self.uploads: list[tuple[str, str, str, dict[str, str]]] = []
        self.deleted: list[tuple[str, str]] = []

    def head_bucket(self, *, Bucket: str) -> None:
        if not self.bucket_created:
            raise ClientError({"Error": {"Code": "404"}}, "HeadBucket")

    def create_bucket(self, *, Bucket: str) -> None:
        self.bucket_created = True

    def upload_file(self, source: str, bucket: str, key: str, *, ExtraArgs: dict[str, str]) -> None:
        self.uploads.append((source, bucket, key, ExtraArgs))

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.deleted.append((Bucket, Key))


def test_s3_storage_creates_bucket_uploads_and_deletes(tmp_path: Path) -> None:
    client = FakeS3Client()
    storage = S3Storage(client=client)  # type: ignore[arg-type]
    source = tmp_path / "book.pdf"
    source.write_bytes(b"%PDF-")

    storage.upload_file(source, "books/book-id/original.pdf", "application/pdf")
    storage.delete_file("books/book-id/original.pdf")

    assert client.bucket_created is True
    assert client.uploads[0][2:] == (
        "books/book-id/original.pdf",
        {"ContentType": "application/pdf"},
    )
    assert client.deleted == [(storage.bucket_name, "books/book-id/original.pdf")]
