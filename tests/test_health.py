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
    for path in ("/library", "/upload", "/settings", "/books/book-id"):
        response = client.get(path)

        assert response.status_code == 200
        assert 'id="app"' in response.text


def test_frontend_assets_are_served() -> None:
    response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert "currentPage" in response.text


def test_books_list_api_is_exposed_in_openapi() -> None:
    schema = app.openapi()

    assert "get" in schema["paths"]["/api/v1/books"]
