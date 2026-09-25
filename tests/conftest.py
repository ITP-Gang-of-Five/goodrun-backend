from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.main import app
from app.queries import DATABASE_URL, Queries, get_queries


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
