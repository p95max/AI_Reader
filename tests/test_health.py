from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root() -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/library"


def test_frontend_routes_serve_the_spa_for_deep_links() -> None:
    for path in ("/library", "/upload", "/player", "/settings", "/books/book-id"):
        response = client.get(path)

        assert response.status_code == 200
        assert 'id="app"' in response.text


def test_frontend_assets_are_served() -> None:
    response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert "currentPage" in response.text


def test_frontend_document_declares_english_interface_language() -> None:
    response = client.get("/library")

    assert '<html lang="en">' in response.text


def test_books_list_api_is_exposed_in_openapi() -> None:
    schema = app.openapi()

    assert "get" in schema["paths"]["/api/v1/books"]
    assert "delete" in schema["paths"]["/api/v1/books/{book_id}"]


def test_processing_endpoints_are_exposed_in_openapi() -> None:
    schema = app.openapi()

    assert "get" in schema["paths"]["/api/v1/books/estimate"]
    assert "post" in schema["paths"]["/api/v1/books/{book_id}/process"]


def test_user_preferences_endpoints_are_exposed_in_openapi() -> None:
    schema = app.openapi()

    assert "get" in schema["paths"]["/api/v1/settings/preferences"]
    assert "put" in schema["paths"]["/api/v1/settings/preferences"]


def test_audio_player_endpoints_are_exposed_in_openapi() -> None:
    schema = app.openapi()

    assert "get" in schema["paths"]["/api/v1/books/{book_id}"]
    assert "get" in schema["paths"]["/api/v1/books/{book_id}/audio"]
    assert "get" in schema["paths"]["/api/v1/books/{book_id}/audio/{chunk_id}"]


def test_playback_position_endpoints_are_exposed_in_openapi() -> None:
    schema = app.openapi()

    assert "get" in schema["paths"]["/api/v1/books/{book_id}/playback"]
    assert "put" in schema["paths"]["/api/v1/books/{book_id}/playback"]


def test_book_usage_endpoint_is_exposed_in_openapi() -> None:
    schema = app.openapi()

    assert "get" in schema["paths"]["/api/v1/books/{book_id}/usage"]
