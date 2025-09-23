from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo


@dataclass(slots=True)
class QueueItem:
    id: str
    text: str
    topic: str | None
    notes: str | None
    scheduled_at: datetime
    status: str
    result: dict | None
    attempt_count: int
    hash: str | None


def _serialize_datetime(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat()


def _deserialize_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid ISO timestamp stored in queue: {value!r}") from exc


class QueueRepository:
    """SQLite-backed queue store for scheduled posts."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    topic TEXT,
                    notes TEXT,
                    scheduled_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    hash TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_posts_status_scheduled
                    ON posts(status, scheduled_at)
                """
            )

    def list_pending(self, *, before: datetime | None = None) -> list[QueueItem]:
        query = "SELECT * FROM posts WHERE status = 'pending'"
        params: list[str] = []
        if before is not None:
            query += " AND scheduled_at <= ?"
            params.append(_serialize_datetime(before))
        query += " ORDER BY scheduled_at ASC"

        with closing(self._connect()) as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_item(row) for row in rows]

    def upsert_items(self, items: Iterable[QueueItem]) -> None:
        payload = [self._item_to_row(item) for item in items]
        now_iso = _serialize_datetime(datetime.utcnow())
        with closing(self._connect()) as conn, conn:
            conn.executemany(
                """
                INSERT INTO posts (id, text, topic, notes, scheduled_at, status, result, attempt_count, hash, created_at, updated_at)
                VALUES (:id, :text, :topic, :notes, :scheduled_at, :status, :result, :attempt_count, :hash, :created_at, :updated_at)
                ON CONFLICT(id) DO UPDATE SET
                    text = excluded.text,
                    topic = excluded.topic,
                    notes = excluded.notes,
                    scheduled_at = excluded.scheduled_at,
                    status = excluded.status,
                    result = excluded.result,
                    attempt_count = excluded.attempt_count,
                    hash = excluded.hash,
                    updated_at = :updated_at_conflict
                """,
                [dict(row, updated_at_conflict=now_iso) for row in payload],
            )

    def mark_sent(self, post_id: str, *, tweet_id: str, posted_at: datetime, hash_value: str | None = None) -> None:
        result_payload = json.dumps({"tweet_id": tweet_id, "posted_at": _serialize_datetime(posted_at)})
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE posts
                   SET status = 'sent',
                       result = ?,
                       hash = COALESCE(?, hash),
                       updated_at = ?
                 WHERE id = ?
                """,
                (result_payload, hash_value, _serialize_datetime(datetime.utcnow()), post_id),
            )

    def mark_failed(self, post_id: str, *, error: str) -> None:
        payload = json.dumps({"error": error, "failed_at": _serialize_datetime(datetime.utcnow())})
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE posts
                   SET status = 'failed',
                       result = ?,
                       attempt_count = attempt_count + 1,
                       updated_at = ?
                 WHERE id = ?
                """,
                (payload, _serialize_datetime(datetime.utcnow()), post_id),
            )

    def reset_failed(self, post_id: str, *, schedule_at: datetime) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE posts
                   SET status = 'pending',
                       scheduled_at = ?,
                       updated_at = ?
                 WHERE id = ?
                """,
                (
                    _serialize_datetime(schedule_at),
                    _serialize_datetime(datetime.utcnow()),
                    post_id,
                ),
            )

    def list_recent_hashes(self, *, since: datetime) -> set[str]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT hash FROM posts WHERE hash IS NOT NULL AND updated_at >= ?",
                (_serialize_datetime(since),),
            ).fetchall()
        return {row["hash"] for row in rows}

    def remove(self, ids: Sequence[str]) -> None:
        if not ids:
            return
        with closing(self._connect()) as conn, conn:
            conn.executemany("DELETE FROM posts WHERE id = ?", [(post_id,) for post_id in ids])

    def _row_to_item(self, row: sqlite3.Row) -> QueueItem:
        result_payload = json.loads(row["result"]) if row["result"] else None
        return QueueItem(
            id=row["id"],
            text=row["text"],
            topic=row["topic"],
            notes=row["notes"],
            scheduled_at=_deserialize_datetime(row["scheduled_at"]),
            status=row["status"],
            result=result_payload,
            attempt_count=row["attempt_count"],
            hash=row["hash"],
        )

    def _item_to_row(self, item: QueueItem) -> dict[str, str | int | None]:
        now_iso = _serialize_datetime(datetime.utcnow())
        return {
            "id": item.id,
            "text": item.text,
            "topic": item.topic,
            "notes": item.notes,
            "scheduled_at": _serialize_datetime(item.scheduled_at),
            "status": item.status,
            "result": json.dumps(item.result) if item.result else None,
            "attempt_count": item.attempt_count,
            "hash": item.hash,
            "created_at": now_iso,
            "updated_at": now_iso,
        }


def bootstrap_from_json(repo: QueueRepository, queue_json: Path) -> None:
    """Seed the SQLite queue from a legacy JSON file if the DB is empty."""

    if not queue_json.exists():
        return

    with closing(repo._connect()) as conn:
        count = conn.execute("SELECT COUNT(1) FROM posts").fetchone()[0]
        if count:
            return

    data = json.loads(queue_json.read_text(encoding="utf-8"))
    tz = ZoneInfo("America/New_York")
    items: list[QueueItem] = []
    for entry in data:
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

    if items:
        repo.upsert_items(items)
