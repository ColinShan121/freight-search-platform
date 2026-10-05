import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from freight_search.db import connect, database_errors, get_db
from freight_search.main import app
from freight_search.migrate import apply_schema


@pytest.fixture
def db_client():
    if os.environ.get("RUN_DB_TESTS") != "1":
        pytest.skip("Set RUN_DB_TESTS=1 to run local PostgreSQL integration tests")
    schema = "test_freight_" + uuid4().hex
    with connect() as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    try:
        with connect() as connection:
            connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            apply_schema(connection)

        def test_db():
            with database_errors():
                with connect() as connection:
                    connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
                    yield connection

        app.dependency_overrides[get_db] = test_db
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        with connect() as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
