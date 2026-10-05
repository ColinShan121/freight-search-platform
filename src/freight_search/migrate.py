from pathlib import Path

import psycopg

from freight_search.db import ConfigurationError, connect


SCHEMA_SQL = Path(__file__).resolve().parents[2] / "sql" / "001_listings.sql"


def apply_schema(connection):
    connection.execute(SCHEMA_SQL.read_text())


def main():
    try:
        with connect() as connection:
            apply_schema(connection)
    except ConfigurationError as exc:
        raise SystemExit(str(exc)) from None
    except (psycopg.Error, ValueError):
        raise SystemExit("Schema application failed; check local database configuration and health") from None
    print("Schema applied successfully")


if __name__ == "__main__":
    main()
