from uuid import UUID

import pytest
from pydantic import ValidationError

from app.models.user import User
from app.schemas.auth import RegistrationRequest
from app.services.authentication import (
    create_session_token,
    hash_password,
    verify_password,
)


def test_registration_requires_a_strong_confirmed_password() -> None:
    payload = RegistrationRequest(
        display_name="Reader",
        email="reader@example.com",
        password="SafePassword2026",
        password_confirmation="SafePassword2026",
    )

    assert payload.display_name == "Reader"

    with pytest.raises(ValidationError):
        RegistrationRequest(
            display_name="R",
            email="not-an-email",
            password="weak",
            password_confirmation="different",
        )


def test_password_hash_and_session_token_do_not_contain_the_password() -> None:
    password = "SafePassword2026"
    password_hash = hash_password(password)
    user = User(
        id=UUID("87654321-4321-8765-4321-876543218765"),
        email="reader@example.com",
        password_hash=password_hash,
    )

    token = create_session_token(user)

    assert password not in password_hash
    assert password not in token
    assert verify_password(password, password_hash)
    assert not verify_password("incorrect-password", password_hash)
