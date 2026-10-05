from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from psycopg import Connection

from freight_search.db import get_db
from freight_search.models import TEXT_PATTERN, Equipment, Listing, ListingInput, SearchResults, Status


app = FastAPI(title="Freight Search")
DB = Annotated[Connection, Depends(get_db, scope="function")]
COLUMNS = "id, origin, destination, cargo_description, equipment_type, status, created_at, updated_at"


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search", response_model=SearchResults)
def search(
    db: DB,
    q: Annotated[str | None, Query(max_length=200, pattern=TEXT_PATTERN)] = None,
    origin: Annotated[str | None, Query(max_length=120, pattern=TEXT_PATTERN)] = None,
    destination: Annotated[str | None, Query(max_length=120, pattern=TEXT_PATTERN)] = None,
    equipment_type: Equipment | None = None,
    status: Status | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
):
    conditions = []
    values = []
    text = q.strip() if q else ""
    if text:
        conditions.append("search_vector @@ websearch_to_tsquery('english', %s)")
        values.append(text)
    for column, value in (("origin", origin), ("destination", destination),
                          ("equipment_type", equipment_type), ("status", status)):
        if value is not None:
            if column in ("origin", "destination"):
                conditions.append(f"lower({column}) = lower(%s)")
            else:
                conditions.append(f"{column} = %s")
            values.append(value)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    order = "created_at DESC, id ASC"
    if text:
        order = "ts_rank(search_vector, websearch_to_tsquery('english', %s)) DESC, " + order
        values.append(text)
    values.extend((limit, offset))
    rows = db.execute(f"SELECT {COLUMNS} FROM listings{where} ORDER BY {order} LIMIT %s OFFSET %s", values).fetchall()
    return {"items": rows}


@app.post("/listings", response_model=Listing, status_code=201)
def create_listing(data: ListingInput, db: DB):
    return db.execute(
        f"INSERT INTO listings (id, origin, destination, cargo_description, equipment_type, status) "
        f"VALUES (%s, %s, %s, %s, %s, %s) RETURNING {COLUMNS}",
        (uuid4(), *data.model_dump().values()),
    ).fetchone()


@app.get("/listings/{listing_id}", response_model=Listing)
def get_listing(listing_id: UUID, db: DB):
    row = db.execute(f"SELECT {COLUMNS} FROM listings WHERE id = %s", (listing_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Listing not found")
    return row


@app.put("/listings/{listing_id}", response_model=Listing)
def replace_listing(listing_id: UUID, data: ListingInput, db: DB):
    row = db.execute(
        "UPDATE listings SET origin=%s, destination=%s, cargo_description=%s, "
        "equipment_type=%s, status=%s, updated_at=clock_timestamp() "
        f"WHERE id=%s RETURNING {COLUMNS}",
        (*data.model_dump().values(), listing_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Listing not found")
    return row
