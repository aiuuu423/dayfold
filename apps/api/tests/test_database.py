import os
import sqlite3

import pytest

from apps.api.database import (
    DatabaseConfigurationError,
    configure_certificate_store,
    connect_database,
    database_session,
    initialize_schema,
    mapping_row_factory,
)


def test_certificate_store_uses_certifi_when_not_explicit(monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)

    configure_certificate_store(certifi_path="/trusted/cacert.pem")

    assert os.environ["SSL_CERT_FILE"] == "/trusted/cacert.pem"


def test_certificate_store_preserves_explicit_deployment_setting(monkeypatch):
    monkeypatch.setenv("SSL_CERT_FILE", "/platform/ca.pem")

    configure_certificate_store(certifi_path="/trusted/cacert.pem")

    assert os.environ["SSL_CERT_FILE"] == "/platform/ca.pem"


def test_sqlite_backend_creates_parent_and_supports_named_rows(tmp_path, monkeypatch):
    monkeypatch.delenv("DAYFOLD_DATA_BACKEND", raising=False)
    database_path = tmp_path / "nested" / "dayfold.sqlite3"

    with connect_database(database_path) as connection:
        connection.execute("CREATE TABLE sample (id TEXT PRIMARY KEY, value TEXT)")
        connection.execute(
            "INSERT INTO sample (id, value) VALUES (?, ?)",
            ("one", "saved"),
        )
        row = connection.execute(
            "SELECT id, value FROM sample WHERE id = ?",
            ("one",),
        ).fetchone()

    assert database_path.exists()
    assert row["value"] == "saved"


def test_turso_backend_requires_remote_credentials(monkeypatch):
    monkeypatch.setenv("DAYFOLD_DATA_BACKEND", "turso")
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)

    with pytest.raises(DatabaseConfigurationError):
        connect_database("ignored.sqlite3")


def test_turso_backend_passes_server_credentials_to_connector(monkeypatch):
    monkeypatch.setenv("DAYFOLD_DATA_BACKEND", "turso")
    monkeypatch.setenv("TURSO_DATABASE_URL", "https://demo.example.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "test-token")
    captured = {}
    connection = sqlite3.connect(":memory:")

    def connector(url, *, auth_token):
        captured.update(url=url, auth_token=auth_token)
        return connection

    selected = connect_database("ignored.sqlite3", turso_connect=connector)

    assert selected is connection
    assert captured == {
        "url": "https://demo.example.turso.io",
        "auth_token": "test-token",
    }
    selected.close()


def test_mapping_row_factory_supports_non_sqlite_cursor():
    class Cursor:
        description = (("id", None, None, None, None, None, None),)

    assert mapping_row_factory(Cursor(), ("memory-1",)) == {"id": "memory-1"}


def test_database_session_commits_and_closes(monkeypatch):
    calls = []

    class Connection:
        row_factory = None

        def execute(self, statement):
            calls.append(("execute", statement))

        def commit(self):
            calls.append(("commit",))

        def rollback(self):
            calls.append(("rollback",))

        def close(self):
            calls.append(("close",))

    monkeypatch.setenv("DAYFOLD_DATA_BACKEND", "turso")
    monkeypatch.setenv("TURSO_DATABASE_URL", "https://demo.example.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "test-token")

    with database_session(
        "ignored.sqlite3",
        turso_connect=lambda *_args, **_kwargs: Connection(),
    ):
        calls.append(("work",))

    assert ("commit",) in calls
    assert ("rollback",) not in calls
    assert calls[-1] == ("close",)


def test_database_session_rolls_back_and_closes(monkeypatch):
    calls = []

    class Connection:
        row_factory = None

        def execute(self, statement):
            calls.append(("execute", statement))

        def commit(self):
            calls.append(("commit",))

        def rollback(self):
            calls.append(("rollback",))

        def close(self):
            calls.append(("close",))

    monkeypatch.setenv("DAYFOLD_DATA_BACKEND", "turso")
    monkeypatch.setenv("TURSO_DATABASE_URL", "https://demo.example.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "test-token")

    with pytest.raises(RuntimeError):
        with database_session(
            "ignored.sqlite3",
            turso_connect=lambda *_args, **_kwargs: Connection(),
        ):
            raise RuntimeError("failed write")

    assert ("rollback",) in calls
    assert ("commit",) not in calls
    assert calls[-1] == ("close",)


def test_unknown_backend_is_rejected(monkeypatch):
    monkeypatch.setenv("DAYFOLD_DATA_BACKEND", "temporary-disk")

    with pytest.raises(DatabaseConfigurationError):
        connect_database("ignored.sqlite3")


def test_schema_initialization_falls_back_when_executescript_is_unavailable():
    statements = []

    class RemoteConnection:
        def execute(self, statement):
            statements.append(statement.strip())

        def commit(self):
            statements.append("COMMIT")

    initialize_schema(
        RemoteConnection(),
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS sample (
            id TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE INDEX IF NOT EXISTS sample_value_idx
        ON sample (value);
        """,
    )

    assert statements == [
        "PRAGMA foreign_keys = ON;",
        "CREATE TABLE IF NOT EXISTS sample (\n"
        "            id TEXT PRIMARY KEY,\n"
        "            value TEXT\n"
        "        );",
        "CREATE INDEX IF NOT EXISTS sample_value_idx\n"
        "        ON sample (value);",
        "COMMIT",
    ]
