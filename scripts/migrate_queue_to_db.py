"""Migrate JSON queue into the SQLite-backed repository."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from autoposter.storage import QueueItem, QueueRepository

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
QUEUE_JSON = DATA_DIR / "post_queue.json"
DB_PATH = DATA_DIR / "queue.db"


def load_items() -> list[QueueItem]:
    queue_data = json.loads(QUEUE_JSON.read_text(encoding="utf-8"))
    tz = ZoneInfo("America/New_York")
    items: list[QueueItem] = []
    for entry in queue_data:
        scheduled = datetime.fromisoformat(entry["scheduled_time"])
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=tz)
        items.append(
            QueueItem(
                id=entry["id"],
                text=entry["text"],
                topic=entry.get("topic"),
                notes=entry.get("notes"),
                scheduled_at=scheduled,
                status=entry.get("status", "pending"),
                result=entry.get("result"),
                attempt_count=entry.get("attempt_count", 0),
                hash=entry.get("hash"),
            )
        )
    return items


def main() -> None:
    if not QUEUE_JSON.exists():
        raise SystemExit("queue JSON not found; nothing to migrate")

    repo = QueueRepository(DB_PATH)
    items = load_items()
    repo.upsert_items(items)
    print(f"Migrated {len(items)} queue entries into {DB_PATH}.")


if __name__ == "__main__":
    main()
