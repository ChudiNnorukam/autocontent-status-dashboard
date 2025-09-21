from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Iterable, List

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from zoneinfo import ZoneInfo

from .config import Settings, get_settings
from .content_generator import GeneratedPost
from .poster import XPoster


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


def _load_queue(path: Path) -> List[ScheduledPost]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ScheduledPost.from_dict(item) for item in data]


def _save_queue(path: Path, queue: Iterable[ScheduledPost]) -> None:
    payload = [item.to_dict() for item in queue]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _generate_time_slots(settings: Settings, count: int) -> List[datetime]:
    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)
    start = now + timedelta(minutes=settings.post_lead_time_minutes)

    slots: List[datetime] = []
    day_offset = 0
    last_time: datetime | None = None

    while len(slots) < count and day_offset < settings.scheduling_window_days:
        current_date = (start.date() + timedelta(days=day_offset))
        for hour in settings.preferred_posting_hours:
            candidate = datetime.combine(current_date, time(hour=hour), tzinfo=tz)
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
    queue = _load_queue(settings.post_queue_path)

    existing_times = [item.scheduled_time for item in queue if item.status == "pending"]
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

    scheduled: List[ScheduledPost] = []
    for post, slot in zip(posts_list, filtered_slots):
        scheduled.append(
            ScheduledPost(
                id=str(uuid.uuid4()),
                text=post.text,
                scheduled_time=slot,
                topic=post.topic,
                notes=post.notes,
            )
        )

    queue.extend(scheduled)
    queue.sort(key=lambda item: item.scheduled_time)
    _save_queue(settings.post_queue_path, queue)
    return scheduled


def _process_queue(poster: XPoster, settings: Settings) -> None:
    queue = _load_queue(settings.post_queue_path)
    if not queue:
        return

    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)
    changed = False

    for item in queue:
        if item.status != "pending":
            continue
        if item.scheduled_time.tzinfo is None:
            item.scheduled_time = item.scheduled_time.replace(tzinfo=tz)
        if item.scheduled_time > now:
            continue

        result = poster.post(item.text)
        changed = True
        if result.success:
            item.status = "sent"
            item.result = {
                "tweet_id": result.tweet_id,
                "posted_at": datetime.now(tz).isoformat(),
                "dry_run": result.dry_run,
            }
        else:
            item.status = "failed"
            item.result = {
                "error": result.error,
                "attempted_at": datetime.now(tz).isoformat(),
            }

    if changed:
        _save_queue(settings.post_queue_path, queue)




def process_queue_once(dry_run: bool = False) -> None:
    settings = get_settings()
    poster = XPoster(dry_run=dry_run)
    _process_queue(poster, settings)


def start_scheduler(poll_seconds: int = 60, dry_run: bool = False) -> None:
    settings = get_settings()
    poster = XPoster(dry_run=dry_run)

    scheduler = BlockingScheduler(timezone=settings.timezone)
    scheduler.add_job(
        lambda: _process_queue(poster, settings),
        trigger=IntervalTrigger(seconds=poll_seconds),
        max_instances=1,
        coalesce=True,
        id="x-autoposter",
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):  # pragma: no cover - CLI handling
        scheduler.shutdown()
