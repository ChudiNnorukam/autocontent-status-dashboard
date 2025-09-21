from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from zoneinfo import ZoneInfo

from . import data_fetcher
from .config import get_settings
from .content_generator import GeneratedPost, generate_posts
from .scheduler import ScheduledPost, plan_schedule, start_scheduler
from .voice_model import VoiceProfile, build_voice_profile, load_voice_profile, save_voice_profile


def train_voice(limit: int = 500, include_retweets: bool = False, include_replies: bool = False) -> VoiceProfile:
    """Fetch tweets and build a voice profile for the configured username."""

    settings = get_settings()
    tweets = data_fetcher.fetch_user_tweets(
        username=settings.username,
        limit=limit,
        include_retweets=include_retweets,
        include_replies=include_replies,
    )

    df = data_fetcher.tweets_to_dataframe(tweets)
    export_path = Path(settings.data_dir) / f"{settings.username}_tweets.csv"
    data_fetcher.export_tweets_to_csv(tweets, export_path)

    profile = build_voice_profile(df)
    save_voice_profile(profile, settings.voice_profile_path)
    return profile


def load_or_train_voice() -> VoiceProfile:
    settings = get_settings()
    if settings.voice_profile_path.exists():
        return load_voice_profile(settings.voice_profile_path)
    return train_voice()


def generate_content_plan(
    topics: Sequence[str] | None = None,
    count: int = 5,
    prefer_llm: bool = True,
) -> list[GeneratedPost]:
    settings = get_settings()
    profile = load_or_train_voice()
    posts = generate_posts(profile, topics=topics, count=count, prefer_llm=prefer_llm)

    payload = {
        "generated_at": datetime.now(ZoneInfo(settings.timezone)).isoformat(),
        "topics": list(topics or []),
        "posts": [post.__dict__ for post in posts],
    }
    Path(settings.content_plan_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return posts


def schedule_generated_posts(posts: Iterable[GeneratedPost]) -> list[ScheduledPost]:
    settings = get_settings()
    scheduled = plan_schedule(posts, settings)

    queue_snapshot = {
        "scheduled_at": datetime.now(ZoneInfo(settings.timezone)).isoformat(),
        "queued_count": len(scheduled),
        "queue_path": str(settings.post_queue_path),
    }
    Path(settings.data_dir / "last_schedule.json").write_text(
        json.dumps(queue_snapshot, indent=2),
        encoding="utf-8",
    )
    return scheduled


def end_to_end_run(
    topics: Sequence[str] | None = None,
    count: int = 5,
    prefer_llm: bool = True,
    include_retweets: bool = False,
    include_replies: bool = False,
) -> list[ScheduledPost]:
    train_voice(include_retweets=include_retweets, include_replies=include_replies)
    posts = generate_content_plan(topics=topics, count=count, prefer_llm=prefer_llm)
    return schedule_generated_posts(posts)


def launch_scheduler(poll_seconds: int = 60, dry_run: bool = False) -> None:
    start_scheduler(poll_seconds=poll_seconds, dry_run=dry_run)
