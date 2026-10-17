from collections.abc import Iterator
from typing import Any, NoReturn

import psycopg
import pytest
import requests
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.auth.limits import login_attempts
from app.common import mail
from app.main import app
from app.queries import DATABASE_URL, Queries, get_queries
from tests.accounts import sent_emails


@pytest.fixture(autouse=True)
def forget_failed_logins() -> Iterator[None]:
    # failed logins are counted in memory for the life of the server, which in tests is the
    # whole run, so without this a test's wrong passwords could lock out a later test
    login_attempts.reset()
    yield
    login_attempts.reset()


@pytest.fixture(autouse=True)
def catch_emails(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # no test sends a real email, they're kept in sent_emails for the test to read instead
    sent_emails.clear()
    monkeypatch.setattr(mail, "deliver", sent_emails.append)
    yield
    sent_emails.clear()


@pytest.fixture(autouse=True)
def no_real_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Stops any test from actually calling out to AWS, which costs money per request.

    Tests that need a location response fake it with _fake_aws in test_locations.py.
    If you see this error, that is what you are missing.
    """

    def refuse(*args: Any, **kwargs: Any) -> NoReturn:
        raise RuntimeError(
            "this test tried to make a real http request, use _fake_aws instead"
        )

    monkeypatch.setattr(requests.Session, "request", refuse)


@pytest.fixture
def queries() -> Iterator[Queries]:
    """
    One connection per test, inside a transaction that is always rolled back.

    Nothing a test writes survives it, so tests cannot affect each other and the
    seed data never changes. This connects directly rather than through the pool,
    because the pool is only opened by the application's lifespan.
    """
    with (
        psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection,
        connection.transaction(force_rollback=True),
    ):
        yield Queries(connection)


@pytest.fixture
def client(queries: Queries) -> Iterator[TestClient]:
    # hand every endpoint the rolled back transaction instead of a pooled connection
    app.dependency_overrides[get_queries] = lambda: queries
    yield TestClient(app)
    app.dependency_overrides.clear()
