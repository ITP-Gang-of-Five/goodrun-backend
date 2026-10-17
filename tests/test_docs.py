from fastapi.testclient import TestClient

from app.main import docs_urls


def test_docs_are_served_locally(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200


def test_docs_are_hidden_in_production() -> None:
    assert docs_urls("production") == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }
    assert docs_urls(None) == {}
