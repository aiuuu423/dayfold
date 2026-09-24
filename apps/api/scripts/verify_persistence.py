import asyncio
import json
import os
from datetime import datetime, timezone

from apps.api.entries import SqliteEntryRepository


DEMO_USER_ID = "00000000-0000-4000-8000-000000000001"


async def main() -> int:
    if os.getenv("DAYFOLD_DATA_BACKEND", "").strip().lower() != "turso":
        print(json.dumps({"status": "failed", "reason": "turso_backend_required"}))
        return 1

    marker = f"synthetic-persistence-check-{datetime.now(timezone.utc).isoformat()}"
    first_repository = SqliteEntryRepository("unused-when-turso-is-enabled")
    entry = await first_repository.create(
        DEMO_USER_ID,
        marker,
        datetime.now(timezone.utc).isoformat(),
    )

    second_repository = SqliteEntryRepository("unused-when-turso-is-enabled")
    persisted = await second_repository.get(DEMO_USER_ID, entry.id)
    deleted = await second_repository.delete(DEMO_USER_ID, entry.id)
    passed = (
        persisted is not None
        and persisted.content == marker
        and deleted
        and await second_repository.get(DEMO_USER_ID, entry.id) is None
    )
    print(
        json.dumps(
            {
                "status": "passed" if passed else "failed",
                "cross_connection_read": persisted is not None,
                "cleanup_completed": deleted,
            }
        )
    )
    return 0 if passed else 1


raise SystemExit(asyncio.run(main()))
