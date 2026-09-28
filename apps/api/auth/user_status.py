from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import httpx


class UserStatusStoreUnavailable(Exception):
    pass


@dataclass(frozen=True)
class InternalUser:
    id: str
    auth_subject: str
    status: str


class UserStatusStore(Protocol):
    async def get_user(
        self,
        auth_subject: str,
        access_token: str,
    ) -> InternalUser | None:
        ...


def _validated_user(
    user_id: object,
    returned_subject: object,
    status: object,
    expected_subject: str,
) -> InternalUser:
    if not isinstance(returned_subject, str) or returned_subject != expected_subject:
        raise UserStatusStoreUnavailable
    if status not in {"active", "deletion_pending", "disabled"}:
        raise UserStatusStoreUnavailable
    try:
        normalized_id = str(UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError) as error:
        raise UserStatusStoreUnavailable from error
    return InternalUser(
        id=normalized_id,
        auth_subject=returned_subject,
        status=status,
    )


class PostgresUserStatusStore:
    def __init__(
        self,
        database_url: str,
        connect: Callable[..., Awaitable[Any]] | None = None,
    ) -> None:
        self._database_url = database_url
        self._connect = connect

    async def get_user(
        self,
        auth_subject: str,
        access_token: str,
    ) -> InternalUser | None:
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
                        SELECT id, auth_subject, status
                        FROM users
                        WHERE auth_subject = %s
                          AND deleted_at IS NULL
                        """,
                        (auth_subject,),
                    )
                    rows = await cursor.fetchall()
        except Exception as error:
            raise UserStatusStoreUnavailable from error

        if not rows:
            return None
        if len(rows) != 1 or len(rows[0]) != 3:
            raise UserStatusStoreUnavailable
        return _validated_user(*rows[0], auth_subject)


class CloudBaseHttpUserStatusStore:
    def __init__(
        self,
        environment_id: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = (
            f"https://{environment_id}.api.tcloudbasegateway.com"
        )
        self._transport = transport

    async def get_user(
        self,
        auth_subject: str,
        access_token: str,
    ) -> InternalUser | None:
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
                        "select": "id,auth_subject,status",
                        "auth_subject": f"eq.{auth_subject}",
                        "deleted_at": "is.null",
                        "limit": "2",
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
        return _validated_user(
            row.get("id"),
            row.get("auth_subject"),
            row.get("status"),
            auth_subject,
        )
