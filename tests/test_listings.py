from uuid import uuid4

import pytest


pytestmark = pytest.mark.integration


# All listing payloads in this module are fictional test fixtures.
def fictional_listing(**changes):
    data = {"origin": "Fictional North Depot", "destination": "Fictional South Depot",
            "cargo_description": "Fictional copper coils", "equipment_type": "flatbed",
            "status": "available"}
    return data | changes


def create(client, **changes):
    response = client.post("/listings", json=fictional_listing(**changes))
    assert response.status_code == 201
    return response.json()


def test_create_get_and_missing_ids(db_client):
    record = create(db_client)
    assert db_client.get("/listings/" + record["id"]).json() == record
    assert record["origin"] == "Fictional North Depot"
    assert record["created_at"] and record["updated_at"]
    missing = str(uuid4())
    assert db_client.get("/listings/" + missing).status_code == 404
    assert db_client.put("/listings/" + missing, json=fictional_listing()).status_code == 404
    assert db_client.get("/listings/not-a-uuid").status_code == 422


@pytest.mark.parametrize("changes", [
    {"origin": "   "}, {"destination": "\t\n"}, {"cargo_description": ""},
    {"origin": "x" * 121}, {"destination": "x" * 121},
    {"cargo_description": "x" * 2001}, {"equipment_type": "boat"},
    {"status": "unknown"}, {"unexpected": True},
    {"origin": "Depot\x00"}, {"destination": "Depot\x00"},
    {"cargo_description": "Copper\x00"},
])
def test_input_rejection(db_client, changes):
    payload = fictional_listing(**changes)
    assert db_client.post("/listings", json=payload).status_code == 422
    record = create(db_client)
    assert db_client.put("/listings/" + record["id"], json=payload).status_code == 422
    assert db_client.get("/listings/" + record["id"]).json() == record


def test_full_replacement_required(db_client):
    record = create(db_client)
    assert db_client.put("/listings/" + record["id"], json={"status": "booked"}).status_code == 422


def test_search_relevance_filters_and_pagination(db_client):
    low = create(db_client, cargo_description="Fictional copper")
    high = create(db_client, cargo_description="Fictional copper copper copper copper")
    other = create(db_client, cargo_description="Fictional apples", equipment_type="refrigerated",
                   status="booked", origin="Fictional East Depot", destination="Fictional West Depot")
    response = db_client.get("/search", params={"q": "copper"})
    assert response.status_code == 200
    assert [r["id"] for r in response.json()["items"]] == [high["id"], low["id"]]
    assert db_client.get("/search", params={"q": "   "}).json() == db_client.get("/search").json()
    for key in ("origin", "destination", "equipment_type", "status"):
        items = db_client.get("/search", params={key: other[key]}).json()["items"]
        assert [r["id"] for r in items] == [other["id"]]
    assert db_client.get("/search", params={"origin": other["origin"].lower()}).json() == {"items": []}
    combined = {k: other[k] for k in ("origin", "destination", "equipment_type", "status")}
    assert db_client.get("/search", params=combined).json()["items"] == [other]
    all_items = db_client.get("/search").json()["items"]
    pages = [db_client.get("/search", params={"limit": 1, "offset": i}).json()["items"][0] for i in range(3)]
    assert pages == all_items
    assert db_client.get("/search", params={"offset": 3}).json() == {"items": []}


@pytest.mark.parametrize("params", [
    {"q": "x" * 201}, {"limit": 0}, {"limit": 101}, {"offset": -1},
    {"offset": 10001}, {"status": "unknown"}, {"equipment_type": "boat"},
    {"q": "Copper\x00"}, {"origin": "Depot\x00"}, {"destination": "Depot\x00"},
])
def test_search_bounds(db_client, params):
    assert db_client.get("/search", params=params).status_code == 422


def test_update_reflected_in_search(db_client):
    before = create(db_client)
    payload = fictional_listing(cargo_description="Fictional bananas", status="delivered",
                               origin="Fictional Changed Depot", equipment_type="dry_van")
    response = db_client.put("/listings/" + before["id"], json=payload)
    assert response.status_code == 200
    after = response.json()
    assert after["id"] == before["id"]
    assert after["created_at"] == before["created_at"]
    assert after["updated_at"] > before["updated_at"]
    assert all(after[key] == value for key, value in payload.items())
    assert db_client.get("/search", params={"q": "copper"}).json() == {"items": []}
    assert db_client.get("/search", params={"q": "bananas", "status": "delivered"}).json()["items"] == [after]


def test_sql_looking_values_are_data(db_client):
    text = "Fictional '); DROP TABLE listings; --"
    record = create(db_client, origin=text, destination=text, cargo_description=text)
    assert db_client.get("/listings/" + record["id"]).json()["cargo_description"] == text
    assert db_client.get("/search", params={"origin": text, "destination": text}).json()["items"] == [record]
    assert db_client.get("/search", params={"q": text}).status_code == 200
    assert db_client.get("/search", params={"origin": "' OR 1=1 --"}).json() == {"items": []}
    assert db_client.put("/listings/" + record["id"], json=fictional_listing(cargo_description=text)).status_code == 200
    assert len(db_client.get("/search").json()["items"]) == 1


@pytest.mark.parametrize("changes", [
    {"origin": " \t"}, {"destination": "x" * 121},
    {"cargo_description": "x" * 2001}, {"equipment_type": "boat"},
    {"status": "unknown"},
])
def test_database_constraints(db_client, changes):
    from contextlib import contextmanager

    import psycopg

    from freight_search.db import get_db
    from freight_search.main import app

    # Use the same real temporary schema, bypassing HTTP validation deliberately.
    with contextmanager(app.dependency_overrides[get_db])() as connection:
        with pytest.raises((psycopg.IntegrityError, psycopg.DataError)):
            with connection.transaction():
                connection.execute(
                    "INSERT INTO listings (id, origin, destination, cargo_description, equipment_type, status) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (uuid4(), *fictional_listing(**changes).values()),
                )


def test_repeatable_migration_preserves_data(db_client):
    from contextlib import contextmanager

    from freight_search.db import get_db
    from freight_search.main import app
    from freight_search.migrate import apply_schema

    record = create(db_client)
    with contextmanager(app.dependency_overrides[get_db])() as connection:
        apply_schema(connection)
        apply_schema(connection)
        index = connection.execute(
            "SELECT indexdef FROM pg_indexes WHERE schemaname = current_schema() "
            "AND indexname = %s", ("listings_search_idx",),
        ).fetchone()
        assert "USING gin (search_vector)" in index["indexdef"]
    assert db_client.get("/listings/" + record["id"]).json() == record
    assert db_client.get("/search", params={"q": "copper"}).json()["items"] == [record]


def test_real_database_error_is_sanitized(db_client):
    from contextlib import contextmanager

    from freight_search.db import get_db
    from freight_search.main import app

    # Drop only the table in this test's dedicated temporary schema.
    with contextmanager(app.dependency_overrides[get_db])() as connection:
        connection.execute("DROP TABLE listings")
    response = db_client.get("/search")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert db_client.get("/health/live").json() == {"status": "ok"}


def test_real_query_timeout_and_schema_isolation(db_client):
    from contextlib import contextmanager

    import psycopg

    from freight_search.db import get_db
    from freight_search.main import app

    with contextmanager(app.dependency_overrides[get_db])() as connection:
        schema = connection.execute("SELECT current_schema() AS name").fetchone()["name"]
        assert schema.startswith("test_freight_")
        assert connection.execute("SHOW search_path").fetchone()["search_path"] == schema
        assert connection.execute("SHOW statement_timeout").fetchone()["statement_timeout"] == "5s"
        assert connection.execute("SHOW lock_timeout").fetchone()["lock_timeout"] == "2s"
        assert connection.execute("SHOW idle_in_transaction_session_timeout").fetchone()["idle_in_transaction_session_timeout"] == "10s"
        # Shorten only this test transaction's real timeout to keep verification quick.
        with pytest.raises(psycopg.errors.QueryCanceled):
            with connection.transaction():
                connection.execute("SET LOCAL statement_timeout = '10ms'")
                connection.execute("SELECT pg_sleep(%s)", (0.1,))
