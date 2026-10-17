import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from scripts.create_admin import create_admin

from app.errors import ApiError
from app.queries import Queries
from app.storage import Role

LOGIN = "/api/v0/auth/login"


def test_creates_an_admin_that_can_log_in(client: TestClient, queries: Queries) -> None:
    admin = create_admin(queries, "New Admin", "New.Admin@example.com", "hunter22")

    assert admin.role == Role.ADMIN
    # stored the same way as any other account, lower cased and hashed
    assert admin.email == "new.admin@example.com"
    assert admin.password_hash != "hunter22"
    response = client.post(
        LOGIN, json={"email": "new.admin@example.com", "password": "hunter22"}
    )
    assert response.json()["user"]["role"] == "ADMIN"


def test_refuses_an_email_that_is_already_used(queries: Queries) -> None:
    with pytest.raises(ApiError):
        create_admin(queries, "Copy", "tara@example.com", "hunter22")


def test_refuses_a_short_password(queries: Queries) -> None:
    with pytest.raises(ValidationError):
        create_admin(queries, "New Admin", "new.admin@example.com", "short")
