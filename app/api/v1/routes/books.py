from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.audio_chunk import AudioChunk, AudioChunkStatus
from app.models.book import Book, BookStatus
from app.models.chapter import Chapter, ContentChunk, ProcessingStatus
from app.models.playback_state import PlaybackState
from app.schemas.books import (
    BookAudioChunkRead,
    BookCostRead,
    BookLibraryItemRead,
    BookProcessingEstimateRead,
    BookProgressRead,
    BookRead,
    BookTTSSettingsUpdate,
    PlaybackPositionRead,
    PlaybackPositionUpdate,
)
from app.services.book_cost import BookCostService
from app.services.book_estimate import estimate_book_processing_with_pricing
from app.services.book_library import build_book_library_item
from app.services.book_progress import BookProgressService
from app.services.ownership import get_local_user_id
from app.services.storage import ObjectStorage, ObjectStorageError, get_object_storage
from app.services.uploads import InvalidPDFUpload, UploadTooLarge, persist_pdf_upload

router = APIRouter()


def _normalized_filename(upload: UploadFile) -> str:
    filename = Path(upload.filename or "book.pdf").name.strip()
    return filename[:255] or "book.pdf"


@router.get("/estimate", response_model=BookProcessingEstimateRead)
async def estimate_processing(
    file_size_bytes: Annotated[int, Query(ge=1)],
) -> BookProcessingEstimateRead:
    settings = get_settings()
    if file_size_bytes > settings.max_pdf_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="PDF exceeds the configured size limit",
        )
    pricing = settings.pricing_for_model()
    estimate = estimate_book_processing_with_pricing(file_size_bytes, pricing=pricing)
    return BookProcessingEstimateRead(
        estimated_input_tokens=estimate.estimated_input_tokens,
        estimated_output_tokens=estimate.estimated_output_tokens,
        estimated_total_tokens=estimate.estimated_total_tokens,
        estimated_ai_cost_usd=estimate.estimated_ai_cost_usd,
        estimated_audio_seconds=estimate.estimated_audio_seconds,
        model_name=settings.ai_model,
        pricing_version=pricing.version,
    )


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


@router.get("/{book_id}", response_model=BookRead)
async def get_book(
    book_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Book:
    book = await session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    return book


@router.get("/{book_id}/usage", response_model=BookCostRead)
@router.get("/{book_id}/cost", response_model=BookCostRead, include_in_schema=False)
async def get_book_usage(
    book_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BookCostRead:
    try:
        cost = await BookCostService(session).get(book_id)
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Book not found"
        ) from error
    return BookCostRead(**cost.__dict__)


@router.get("/{book_id}/audio", response_model=list[BookAudioChunkRead])
async def list_ready_audio_chunks(
    book_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[BookAudioChunkRead]:
    if await session.get(Book, book_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    chunks = tuple(
        (
            await session.scalars(
                select(AudioChunk)
                .where(AudioChunk.book_id == book_id, AudioChunk.status == AudioChunkStatus.READY)
                .order_by(AudioChunk.chunk_index)
            )
        ).all()
    )
    return [
        BookAudioChunkRead(
            id=chunk.id,
            chunk_index=chunk.chunk_index,
            duration_milliseconds=chunk.duration_milliseconds,
            content_type=chunk.content_type,
            stream_url=f"/api/v1/books/{book_id}/audio/{chunk.id}",
        )
        for chunk in chunks
    ]


@router.get("/{book_id}/audio/{chunk_id}")
async def stream_audio_chunk(
    book_id: UUID,
    chunk_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> Response:
    chunk = await session.scalar(
        select(AudioChunk).where(
            AudioChunk.id == chunk_id,
            AudioChunk.book_id == book_id,
            AudioChunk.status == AudioChunkStatus.READY,
        )
    )
    if chunk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio chunk not found")

    try:
        audio = await run_in_threadpool(storage.download_bytes, chunk.storage_key)
    except ObjectStorageError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    range_header = request.headers.get("range")
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=300"}
    if range_header and range_header.startswith("bytes="):
        try:
            start_text, end_text = range_header.removeprefix("bytes=").split("-", maxsplit=1)
            if start_text:
                start = int(start_text)
                end = int(end_text) if end_text else len(audio) - 1
            else:
                suffix = int(end_text)
                start = max(0, len(audio) - suffix)
                end = len(audio) - 1
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE
            ) from error
        if start < 0 or end < start or start >= len(audio):
            raise HTTPException(status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE)
        end = min(end, len(audio) - 1)
        headers["Content-Range"] = f"bytes {start}-{end}/{len(audio)}"
        return Response(
            content=audio[start : end + 1],
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            media_type=chunk.content_type,
            headers=headers,
        )
    return Response(content=audio, media_type=chunk.content_type, headers=headers)


@router.get("/{book_id}/playback", response_model=PlaybackPositionRead)
async def get_playback_position(
    book_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlaybackPositionRead:
    if await session.get(Book, book_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    playback = await session.get(PlaybackState, book_id)
    if playback is None:
        return PlaybackPositionRead(
            book_id=book_id,
            audio_chunk_id=None,
            position_milliseconds=0,
            updated_at=None,
        )
    return PlaybackPositionRead.model_validate(playback, from_attributes=True)


@router.put("/{book_id}/playback", response_model=PlaybackPositionRead)
async def save_playback_position(
    book_id: UUID,
    payload: PlaybackPositionUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlaybackPositionRead:
    if await session.get(Book, book_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    audio_chunk = await session.scalar(
        select(AudioChunk).where(
            AudioChunk.id == payload.audio_chunk_id,
            AudioChunk.book_id == book_id,
            AudioChunk.status == AudioChunkStatus.READY,
        )
    )
    if audio_chunk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ready audio chunk not found"
        )

    playback = await session.get(PlaybackState, book_id)
    if playback is None:
        playback = PlaybackState(
            book_id=book_id,
            audio_chunk_id=audio_chunk.id,
            position_milliseconds=payload.position_milliseconds,
        )
        session.add(playback)
    else:
        playback.audio_chunk_id = audio_chunk.id
        playback.position_milliseconds = payload.position_milliseconds
    await session.commit()
    await session.refresh(playback)
    return PlaybackPositionRead.model_validate(playback, from_attributes=True)


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
    pricing = settings.pricing_for_model()
    estimate = estimate_book_processing_with_pricing(size_bytes, pricing=pricing)
    book = Book(
        user_id=await get_local_user_id(session),
        title=Path(filename).stem[:255] or "Untitled book",
        author="Unknown author",
        original_filename=filename,
        storage_key="pending",
        content_type="application/pdf",
        size_bytes=size_bytes,
        estimated_input_tokens=estimate.estimated_input_tokens,
        estimated_output_tokens=estimate.estimated_output_tokens,
        estimated_ai_cost_usd=estimate.estimated_ai_cost_usd,
        estimate_model_name=settings.ai_model,
        estimate_pricing_version=pricing.version,
        tts_voice=settings.tts_voice,
        tts_speed="normal",
        tts_style="neutral",
        code_mode="hybrid",
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


@router.post("/{book_id}/process", response_model=BookRead, status_code=status.HTTP_202_ACCEPTED)
async def start_book_processing(
    book_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    payload: BookTTSSettingsUpdate | None = None,
) -> Book:
    """Queue PDF structure extraction after the client confirms processing settings."""
    book = await session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    if book.status == BookStatus.READY:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Book is already ready")
    if book.status == BookStatus.PROCESSING:
        return book

    if payload is not None:
        book.tts_voice = payload.voice
        book.tts_speed = payload.speed.value
        book.tts_style = payload.style.value
        book.code_mode = payload.code_mode.value

    book.status = BookStatus.PROCESSING
    await session.commit()
    await session.refresh(book)
    try:
        from app.workers.tasks import build_book_structure

        build_book_structure.apply_async(args=[str(book.id)], queue="processing")
    except Exception as error:
        book.status = BookStatus.UPLOADED
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Processing queue is unavailable; the uploaded book can be retried",
        ) from error
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
