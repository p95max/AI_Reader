from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.book import Book, BookStatus
from app.models.chapter import Chapter, ContentChunk, ProcessingStatus
from app.schemas.books import BookLibraryItemRead, BookProgressRead, BookRead
from app.services.book_library import build_book_library_item
from app.services.book_progress import BookProgressService
from app.services.storage import ObjectStorage, ObjectStorageError, get_object_storage
from app.services.uploads import InvalidPDFUpload, UploadTooLarge, persist_pdf_upload

router = APIRouter()


def _normalized_filename(upload: UploadFile) -> str:
    filename = Path(upload.filename or "book.pdf").name.strip()
    return filename[:255] or "book.pdf"


@router.get("", response_model=list[BookLibraryItemRead])
async def list_books(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    query: Annotated[str | None, Query(max_length=255)] = None,
    filter: Annotated[BookStatus | None, Query()] = None,
) -> list[BookLibraryItemRead]:
    books_query = select(Book).order_by(Book.created_at.desc())
    if query:
        books_query = books_query.where(Book.title.ilike(f"%{query.strip()}%"))
    if filter in (BookStatus.PROCESSING, BookStatus.READY):
        books_query = books_query.where(Book.status == filter)

    books = tuple((await session.scalars(books_query)).all())
    if not books:
        return []

    stats = await session.execute(
        select(
            Chapter.book_id,
            func.count(ContentChunk.id).label("total_chunks"),
            func.coalesce(
                func.sum(case((ContentChunk.status == ProcessingStatus.READY, 1), else_=0)), 0
            ).label("ready_chunks"),
        )
        .outerjoin(ContentChunk, ContentChunk.chapter_id == Chapter.id)
        .where(Chapter.book_id.in_(book.id for book in books))
        .group_by(Chapter.book_id)
    )
    counts = {book_id: (int(total), int(ready)) for book_id, total, ready in stats.tuples()}
    return [
        BookLibraryItemRead.model_validate(
            build_book_library_item(
                book,
                total_chunks=counts.get(book.id, (0, 0))[0],
                ready_chunks=counts.get(book.id, (0, 0))[1],
            )
        )
        for book in books
    ]


@router.get("/{book_id}/progress", response_model=BookProgressRead)
async def get_book_progress(
    book_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BookProgressRead:
    if await session.get(Book, book_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    progress = await BookProgressService(session).get(book_id)
    return BookProgressRead.model_validate(progress)


@router.post("", response_model=BookRead, status_code=status.HTTP_201_CREATED)
async def create_book(
    file: Annotated[UploadFile, File(description="Technical PDF to process")],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> Book:
    if file.content_type != "application/pdf":
        await file.close()
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are supported",
        )

    settings = get_settings()
    try:
        temporary_path, size_bytes = await persist_pdf_upload(file, settings.max_pdf_size_bytes)
    except InvalidPDFUpload as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid PDF file",
        ) from error
    except UploadTooLarge as error:
        limit_mb = settings.max_pdf_size_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"PDF exceeds the {limit_mb} MB limit",
        ) from error

    filename = _normalized_filename(file)
    book = Book(
        title=Path(filename).stem[:255] or "Untitled book",
        author="Unknown author",
        original_filename=filename,
        storage_key="pending",
        content_type="application/pdf",
        size_bytes=size_bytes,
        status=BookStatus.UPLOADED,
    )
    session.add(book)

    try:
        await session.flush()
        storage_key = f"books/{book.id}/original.pdf"
        await run_in_threadpool(storage.upload_file, temporary_path, storage_key, "application/pdf")
        book.storage_key = storage_key
        await session.commit()
        await session.refresh(book)
    except ObjectStorageError as error:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    except Exception:
        await session.rollback()
        raise
    finally:
        temporary_path.unlink(missing_ok=True)

    return book


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> Response:
    book = await session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    try:
        await run_in_threadpool(storage.delete_file, book.storage_key)
    except ObjectStorageError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error

    await session.delete(book)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
