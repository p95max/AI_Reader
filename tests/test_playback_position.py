from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.books import PlaybackPositionUpdate


def test_playback_position_accepts_a_non_negative_offset() -> None:
    position = PlaybackPositionUpdate(
        audio_chunk_id=UUID("12345678-1234-5678-1234-567812345678"),
        position_milliseconds=12_345,
    )

    assert position.position_milliseconds == 12_345


def test_playback_position_rejects_a_negative_offset() -> None:
    with pytest.raises(ValidationError):
        PlaybackPositionUpdate(
            audio_chunk_id=UUID("12345678-1234-5678-1234-567812345678"),
            position_milliseconds=-1,
        )
