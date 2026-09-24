from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

import certifi


class DatabaseConfigurationError(RuntimeError):
    pass


def configure_certificate_store(
    *,
    certifi_path: str | None = None,
) -> None:
    os.environ.setdefault(
        "SSL_CERT_FILE",
        certifi_path or certifi.where(),
    )


def mapping_row_factory(cursor: Any, row: Any) -> dict[str, Any]:
    return {
        description[0]: row[index]
        for index, description in enumerate(cursor.description)
    }


def connect_database(
    database_path: str | Path,
    *,
    turso_connect: Callable[..., Any] | None = None,
) -> Any:
    backend = os.getenv("DAYFOLD_DATA_BACKEND", "sqlite").strip().lower()
    if backend == "sqlite":
        path = Path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
    elif backend == "turso":
        database_url = os.getenv("TURSO_DATABASE_URL", "").strip()
        auth_token = os.getenv("TURSO_AUTH_TOKEN", "").strip()
        if not database_url or not auth_token:
            raise DatabaseConfigurationError(
                "Turso backend requires TURSO_DATABASE_URL and TURSO_AUTH_TOKEN."
            )
        if turso_connect is None:
            configure_certificate_store()
            try:
                import turso_serverless
            except ImportError as error:
                raise DatabaseConfigurationError(
                    "Turso backend requires the turso_serverless package."
                ) from error
            turso_connect = turso_serverless.connect
        connection = turso_connect(database_url, auth_token=auth_token)
    else:
        raise DatabaseConfigurationError(
            f"Unsupported DAYFOLD_DATA_BACKEND: {backend}"
        )

    connection.row_factory = mapping_row_factory
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def database_session(
    database_path: str | Path,
    *,
    turso_connect: Callable[..., Any] | None = None,
):
    connection = connect_database(
        database_path,
        turso_connect=turso_connect,
    )
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_schema(connection: Any, schema: str) -> None:
    executescript = getattr(connection, "executescript", None)
    if callable(executescript):
        executescript(schema)
        return

    statement = ""
    for line in schema.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            if statement.strip():
                connection.execute(statement.strip())
            statement = ""
    if statement.strip():
        connection.execute(statement.strip())
    connection.commit()
