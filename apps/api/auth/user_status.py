from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import httpx


class UserStatusStoreUnavailable(Exception):
    pass


class UserStatusStore(Protocol):
    async def get_status(
        self,
        auth_subject: str,
        access_token: str,
    ) -> str | None:
        ...


class PostgresUserStatusStore:
    def __init__(
        self,
        database_url: str,
        connect: Callable[..., Awaitable[Any]] | None = None,
    ) -> None:
        self._database_url = database_url
        self._connect = connect

    async def get_status(
        self,
        auth_subject: str,
        access_token: str,
    ) -> str | None:
        connect = self._connect
        if connect is None:
            from psycopg import AsyncConnection

            connect = AsyncConnection.connect

        try:
            connection = await connect(
                self._database_url,
                connect_timeout=3.0,
            )
            async with connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT status
                        FROM users
                        WHERE auth_subject = %s
                          AND deleted_at IS NULL
                        """,
                        (auth_subject,),
                    )
                    row = await cursor.fetchone()
        except Exception as error:
            raise UserStatusStoreUnavailable from error

        if row is None or not isinstance(row[0], str):
            return None
        return row[0]


class CloudBaseHttpUserStatusStore:
    _VALID_STATUSES = frozenset(
        {"active", "deletion_pending", "disabled"}
    )

    def __init__(
        self,
        environment_id: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = (
            f"https://{environment_id}.api.tcloudbasegateway.com"
        )
        self._transport = transport

    async def get_status(
        self,
        auth_subject: str,
        access_token: str,
    ) -> str | None:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                transport=self._transport,
                timeout=3.0,
            ) as client:
                response = await client.get(
                    "/v1/rdb/rest/users",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                    },
                    params={
                        "select": "status",
                        "auth_subject": f"eq.{auth_subject}",
                        "deleted_at": "is.null",
                        "limit": "1",
                    },
                )
        except httpx.HTTPError as error:
            raise UserStatusStoreUnavailable from error

        if response.status_code in (401, 403):
            return None
        if response.status_code != 200:
            raise UserStatusStoreUnavailable

        try:
            payload = response.json()
        except ValueError as error:
            raise UserStatusStoreUnavailable from error

        if not isinstance(payload, list) or len(payload) > 1:
            raise UserStatusStoreUnavailable
        if not payload:
            return None

        row = payload[0]
        if not isinstance(row, dict):
            raise UserStatusStoreUnavailable
        status = row.get("status")
        if status not in self._VALID_STATUSES:
            raise UserStatusStoreUnavailable
        return status
