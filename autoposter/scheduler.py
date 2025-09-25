from __future__ import annotations

import json
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Iterable, List

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from zoneinfo import ZoneInfo

from .config import Settings, get_settings
from .content_generator import GeneratedPost
from .poster import XPoster
from .storage import QueueItem, QueueRepository, bootstrap_from_json


@dataclass
class ScheduledPost:
    id: str
    text: str
    scheduled_time: datetime
    topic: str | None = None
    notes: str | None = None
    status: str = "pending"
    result: dict | None = field(default=None)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "scheduled_time": self.scheduled_time.isoformat(),
            "topic": self.topic,
            "notes": self.notes,
            "status": self.status,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScheduledPost":
        return cls(
            id=data["id"],
            text=data["text"],
            scheduled_time=datetime.fromisoformat(data["scheduled_time"]),
            topic=data.get("topic"),
            notes=data.get("notes"),
            status=data.get("status", "pending"),
            result=data.get("result"),
        )


def _export_queue_snapshot(repo: QueueRepository, path: Path) -> None:
    with closing(repo._connect()) as conn:
        rows = conn.execute("SELECT * FROM posts ORDER BY scheduled_at ASC").fetchall()
    items = []
    for row in rows:
        scheduled = datetime.fromisoformat(row["scheduled_at"])  # stored in ISO form
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=ZoneInfo("America/New_York"))
        items.append(
            ScheduledPost(
                id=row["id"],
                text=row["text"],
                scheduled_time=scheduled,
                topic=row["topic"],
                notes=row["notes"],
                status=row["status"],
                result=json.loads(row["result"]) if row["result"] else None,
            ).to_dict()
        )
    path.write_text(json.dumps(items, indent=2), encoding="utf-8")


def _export_sent_history_snapshot(repo: QueueRepository, path: Path) -> None:
    history = repo.list_sent_history()
    path.write_text(json.dumps(history, indent=2), encoding="utf-8")


def _preferred_times(settings: Settings) -> List[time]:
    slots: List[time] = []
    for entry in settings.preferred_posting_times:
        try:
            hour_str, minute_str = entry.split(":", 1)
            slots.append(time(int(hour_str), int(minute_str)))
        except ValueError as exc:
            raise ValueError(f"Invalid preferred posting time: {entry}") from exc
    if not slots:
        raise ValueError("preferred_posting_times must contain at least one value")
    return slots


def _generate_time_slots(settings: Settings, count: int) -> List[datetime]:
    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)
    start = now + timedelta(minutes=settings.post_lead_time_minutes)

    slots: List[datetime] = []
    day_offset = 0
    last_time: datetime | None = None

    while len(slots) < count and day_offset < settings.scheduling_window_days:
        current_date = (start.date() + timedelta(days=day_offset))
        for window_time in _preferred_times(settings):
            candidate = datetime.combine(current_date, window_time, tzinfo=tz)
            if candidate < start:
                continue
            if last_time and (candidate - last_time).total_seconds() < settings.min_hours_between_posts * 3600:
                continue
            slots.append(candidate)
            last_time = candidate
            if len(slots) >= count:
                break
        day_offset += 1

    return slots


def plan_schedule(posts: Iterable[GeneratedPost], settings: Settings | None = None) -> List[ScheduledPost]:
    settings = settings or get_settings()
    repo = QueueRepository(settings.queue_db_path)
    bootstrap_from_json(repo, settings.post_queue_path)

    pending_items = repo.list_pending()
    existing_times = [item.scheduled_at for item in pending_items]
    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)
    soonest_allowed = now + timedelta(minutes=settings.post_lead_time_minutes)
    if existing_times:
        last_existing = max(existing_times)
        soonest_allowed = max(soonest_allowed, last_existing + timedelta(hours=settings.min_hours_between_posts))

    posts_list = list(posts)
    slot_candidates = _generate_time_slots(settings, len(posts_list) + len(existing_times))

    filtered_slots = [slot for slot in slot_candidates if slot >= soonest_allowed]
    if len(filtered_slots) < len(posts_list):
        raise RuntimeError("Not enough slots available within scheduling window.")

    scheduled_records: list[QueueItem] = []
    scheduled: List[ScheduledPost] = []
    for post, slot in zip(posts_list, filtered_slots):
        post_id = str(uuid.uuid4())
        scheduled.append(
            ScheduledPost(
                id=post_id,
                text=post.text,
                scheduled_time=slot,
                topic=post.topic,
                notes=post.notes,
            )
        )
        scheduled_records.append(
            QueueItem(
                id=post_id,
                text=post.text,
                topic=post.topic,
                notes=post.notes,
                scheduled_at=slot,
                status="pending",
                result=None,
                attempt_count=0,
                hash=None,
            )
        )

    repo.upsert_items(scheduled_records)
    _export_queue_snapshot(repo, settings.post_queue_path)
    return scheduled


def _process_queue(settings: Settings, dry_run: bool = False) -> None:
    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)

    repo = QueueRepository(settings.queue_db_path)
    bootstrap_from_json(repo, settings.post_queue_path)

    due_items = repo.list_pending(before=now)
    if not due_items:
        return

    sent_hashes = repo.list_all_sent_hashes()
    poster = XPoster(dry_run=dry_run)
    changes_made = False
    history_updated = False

    for item in due_items:
        text_hash = sha256(item.text.encode("utf-8")).hexdigest()

        if text_hash in sent_hashes:
            repo.mark_duplicate(
                post_id=item.id,
                hash_value=text_hash,
                detected_at=now,
            )
            changes_made = True
            continue

        result = poster.post(item.text)
        changes_made = True
        if result.success:
            posted_at = datetime.now(tz)
            repo.mark_sent(
                post_id=item.id,
                tweet_id=result.tweet_id or "",
                posted_at=posted_at,
                hash_value=text_hash,
            )
            sent_hashes.add(text_hash)
            if not result.dry_run:
                repo.record_sent_history(
                    post_id=item.id,
                    text=item.text,
                    hash_value=text_hash,
                    posted_at=posted_at,
                )
                history_updated = True
        else:
            repo.mark_failed(item.id, error=result.error or "Unknown error")

    if changes_made:
        _export_queue_snapshot(repo, settings.post_queue_path)
    if history_updated:
        _export_sent_history_snapshot(repo, settings.sent_history_path)




def process_queue_once(dry_run: bool = False) -> None:
    settings = get_settings()
    _process_queue(settings, dry_run=dry_run)


def start_scheduler(poll_seconds: int = 60, dry_run: bool = False) -> None:
    settings = get_settings()
    scheduler = BlockingScheduler(timezone=settings.timezone)
    scheduler.add_job(
        lambda: _process_queue(settings, dry_run=dry_run),
        trigger=IntervalTrigger(seconds=poll_seconds),
        max_instances=1,
        coalesce=True,
        id="x-autoposter",
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):  # pragma: no cover - CLI handling
        scheduler.shutdown()
