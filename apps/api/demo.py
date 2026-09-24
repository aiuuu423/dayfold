from dataclasses import dataclass


DEFAULT_DEMO_USER_ID = "00000000-0000-4000-8000-000000000001"
DEMO_PRIVACY_NOTICE = "Demo only. Do not enter sensitive personal information."


@dataclass(frozen=True)
class DemoSettings:
    user_id: str = DEFAULT_DEMO_USER_ID

    def public_contract(self) -> dict[str, object]:
        return {
            "mode": "demo",
            "user": {"id": self.user_id, "synthetic": True},
            "privacy_notice": DEMO_PRIVACY_NOTICE,
            "memory_types": ["event", "interest", "goal"],
        }
