import os
from contextlib import contextmanager

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row


class ConfigurationError(RuntimeError):
    pass


def connect():
    names = ("HOST", "PORT", "DB", "USER", "PASSWORD")
    missing = [f"POSTGRES_{name}" for name in names if not os.environ.get(f"POSTGRES_{name}")]
    if missing:
        raise ConfigurationError("Missing database settings: " + ", ".join(missing))
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"], port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"], connect_timeout=5,
        options="-c statement_timeout=5000 -c lock_timeout=2000 -c idle_in_transaction_session_timeout=10000",
        row_factory=dict_row,
    )


@contextmanager
def database_errors():
    try:
        yield
    except ConfigurationError:
        raise HTTPException(503, "Database configuration is missing") from None
    except (psycopg.Error, ValueError):
        raise HTTPException(503, "Database unavailable") from None


def get_db():
    with database_errors():
        with connect() as connection:
            yield connection
