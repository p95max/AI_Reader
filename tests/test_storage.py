from pathlib import Path

from botocore.exceptions import ClientError

from app.services.storage import S3Storage


class FakeS3Client:
    def __init__(self) -> None:
        self.bucket_created = False
        self.uploads: list[tuple[str, str, str, dict[str, str]]] = []
        self.deleted: list[tuple[str, str]] = []
        self.downloads: list[tuple[str, str, str]] = []
        self.puts: list[tuple[str, str, bytes, str]] = []

    def head_bucket(self, *, Bucket: str) -> None:
        if not self.bucket_created:
            raise ClientError({"Error": {"Code": "404"}}, "HeadBucket")

    def create_bucket(self, *, Bucket: str) -> None:
        self.bucket_created = True

    def upload_file(self, source: str, bucket: str, key: str, *, ExtraArgs: dict[str, str]) -> None:
        self.uploads.append((source, bucket, key, ExtraArgs))

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.deleted.append((Bucket, Key))

    def download_file(self, bucket: str, key: str, destination: str) -> None:
        self.downloads.append((bucket, key, destination))
        Path(destination).write_bytes(b"%PDF-")

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:
        self.puts.append((Bucket, Key, Body, ContentType))

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        return {"Body": FakeBody(b"audio")}


class FakeBody:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def read(self) -> bytes:
        return self.content


def test_s3_storage_creates_bucket_uploads_and_deletes(tmp_path: Path) -> None:
    client = FakeS3Client()
    storage = S3Storage(client=client)  # type: ignore[arg-type]
    source = tmp_path / "book.pdf"
    source.write_bytes(b"%PDF-")

    storage.upload_file(source, "books/book-id/original.pdf", "application/pdf")
    storage.download_file("books/book-id/original.pdf", tmp_path / "downloaded.pdf")
    storage.delete_file("books/book-id/original.pdf")

    assert client.bucket_created is True
    assert client.uploads[0][2:] == (
        "books/book-id/original.pdf",
        {"ContentType": "application/pdf"},
    )
    assert client.deleted == [(storage.bucket_name, "books/book-id/original.pdf")]
    assert client.downloads[0][:2] == (storage.bucket_name, "books/book-id/original.pdf")


def test_s3_storage_uploads_generated_audio_bytes() -> None:
    client = FakeS3Client()
    storage = S3Storage(client=client)  # type: ignore[arg-type]

    storage.upload_bytes(b"audio", "books/book-id/audio/000000.wav", "audio/wav")

    assert client.puts == [
        (storage.bucket_name, "books/book-id/audio/000000.wav", b"audio", "audio/wav")
    ]


def test_s3_storage_downloads_audio_bytes() -> None:
    storage = S3Storage(client=FakeS3Client())  # type: ignore[arg-type]

    assert storage.download_bytes("books/book-id/audio/000000.wav") == b"audio"
