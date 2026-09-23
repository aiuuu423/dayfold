from dataclasses import dataclass

import httpx


class CloudBaseAuthError(Exception):
    """Base error for stable Dayfold auth failure semantics."""


class InvalidToken(CloudBaseAuthError):
    pass


class TokenExpired(CloudBaseAuthError):
    pass


class AuthProviderUnavailable(CloudBaseAuthError):
    pass


@dataclass(frozen=True)
class VerifiedIdentity:
    auth_subject: str
    email: str | None


class CloudBaseAuthAdapter:
    def __init__(
        self,
        environment_id: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = (
            f"https://{environment_id}.api.tcloudbasegateway.com"
        )
        self._transport = transport

    async def verify_access_token(self, token: str) -> VerifiedIdentity:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                transport=self._transport,
                timeout=3.0,
            ) as client:
                response = await client.get(
                    "/auth/v2/user/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.HTTPError as error:
            raise AuthProviderUnavailable from error

        if response.status_code >= 500:
            raise AuthProviderUnavailable

        if response.status_code == 401:
            try:
                error_code = str(response.json().get("code", "")).lower()
            except ValueError:
                error_code = ""
            if error_code == "token_expired":
                raise TokenExpired
            raise InvalidToken
        if response.status_code != 200:
            raise InvalidToken

        try:
            payload = response.json()
        except ValueError as error:
            raise AuthProviderUnavailable from error

        auth_subject = payload.get("sub")
        if not isinstance(auth_subject, str) or not auth_subject:
            raise AuthProviderUnavailable

        return VerifiedIdentity(
            auth_subject=auth_subject,
            email=payload.get("email"),
        )
