from dataclasses import dataclass


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    auth_subject: str
    email: str | None
